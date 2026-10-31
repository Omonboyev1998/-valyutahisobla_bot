"""Real database helpers on in-memory SQLite; no config/.env or remote driver."""
import importlib.util
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch


class _OfflineBookDb:
    """Loads the real src/database.py with no env and an in-memory books schema."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location('offline_real_database', Path(__file__).resolve().parents[1] / 'src/database.py')
        assert spec is not None and spec.loader is not None
        self.db = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {}, clear=True):
            spec.loader.exec_module(self.db)
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE userbot_settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT,
                file_name TEXT, file_size INTEGER, file_extension TEXT, mime_type TEXT,
                storage_chat_id TEXT, storage_message_id INTEGER,
                source_chat_id TEXT, source_message_id INTEGER, caption TEXT);
        ''')
        self.book = dict(title='Book', author='', file_name='book.pdf', file_size=123,
                         file_extension='pdf', mime_type='application/pdf',
                         storage_chat_id='-1001', storage_message_id=7,
                         source_chat_id='42', source_message_id=30)


class DatabaseSessionTests(_OfflineBookDb, unittest.TestCase):

    def test_shared_helpers_commit_and_preserve_both_dedupe_keys(self):
        self.db.add_book(**self.book, conn=self.conn)
        self.assertFalse(self.conn.in_transaction)
        self.assertTrue(self.db.is_book_indexed('42', 30, 'other', 1, conn=self.conn))
        self.assertTrue(self.db.is_book_indexed('99', 99, 'book.pdf', 123, conn=self.conn))
        self.db.set_userbot_setting('offset', '30', conn=self.conn)
        self.assertEqual(self.db.get_userbot_setting('offset', conn=self.conn), '30')
        self.assertFalse(self.conn.in_transaction)

    def test_failed_commit_is_rolled_back_before_connection_reuse(self):
        real = self.conn
        class FailCommitOnce:
            def __init__(self):
                self.failed = False
            def cursor(self):
                return real.cursor()
            def commit(self):
                if not self.failed:
                    self.failed = True
                    raise RuntimeError('synthetic commit failure')
                real.commit()
            def rollback(self):
                real.rollback()
        conn = FailCommitOnce()
        with self.assertRaisesRegex(RuntimeError, 'synthetic commit'):
            self.db.add_book(**self.book, conn=conn)
        self.assertFalse(real.in_transaction, 'failed write retained a transaction/lock')
        self.db.set_userbot_setting('offset', '40', conn=conn)
        self.assertEqual(real.execute('SELECT COUNT(*) FROM books').fetchone()[0], 0)

    def test_session_closes_on_exception_and_can_reconnect(self):
        connections = []
        def connect(*args, **kwargs):
            conn = sqlite3.Connection(':memory:')
            connections.append(conn)
            return conn
        with patch.object(self.db.sqlite3, 'connect', side_effect=connect):
            with self.assertRaisesRegex(RuntimeError, 'abort'):
                with self.db.db_session() as conn:
                    conn.execute('CREATE TABLE example (id INTEGER)')
                    raise RuntimeError('abort')
            with self.db.db_session() as conn:
                self.assertEqual(conn.execute('SELECT 1').fetchone(), (1,))
        self.assertEqual(len(connections), 2)
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute('SELECT 1')


class DedupeIndexTests(_OfflineBookDb, unittest.TestCase):
    """The in-memory dedupe index must mirror is_book_indexed byte-for-byte."""

    def test_index_matches_existing_source_chat_and_message_id(self):
        self.db.add_book(**self.book, conn=self.conn)
        index = self.db.load_book_dedupe_index('42', conn=self.conn)
        self.assertTrue(index.contains('42', 30, 'butunlay-boshqa.pdf', 1))

    def test_index_matches_file_name_and_size_from_any_source_chat(self):
        other = dict(self.book, source_chat_id='999', source_message_id=1)
        self.db.add_book(**other, conn=self.conn)
        index = self.db.load_book_dedupe_index('42', conn=self.conn)
        self.assertTrue(index.contains('42', 77, 'book.pdf', 123),
                        'file_name+file_size dedupe key was not loaded')

    def test_bulk_load_pages_instead_of_one_query_per_book(self):
        for i in range(1, 26):
            self.db.add_book(**dict(self.book, file_name=f'b{i}.pdf', file_size=i,
                                    source_message_id=i), conn=self.conn)
        queries = []
        real_cursor = self.conn.cursor
        class Spy:
            def __init__(self, cur): self._cur = cur
            def execute(self, sql, params=()):
                queries.append(sql)
                return self._cur.execute(sql, params)
            def fetchall(self): return self._cur.fetchall()
            def fetchone(self): return self._cur.fetchone()
        class SpyConn:
            def cursor(_self): return Spy(real_cursor())
            def commit(_self): pass
            def rollback(_self): pass
        index = self.db.load_book_dedupe_index('42', conn=SpyConn(), page_size=10)
        self.assertLessEqual(len(queries), 6,
                             f'25 books needed {len(queries)} queries: {queries}')
        for i in range(1, 26):
            self.assertTrue(index.contains(None, None, f'b{i}.pdf', i),
                            f'paginated load dropped row {i}')
            self.assertTrue(index.contains('42', i, 'x', 1))

    def test_index_agrees_with_is_book_indexed_on_every_combination(self):
        self.db.add_book(**self.book, conn=self.conn)
        index = self.db.load_book_dedupe_index('42', conn=self.conn)
        cases = [
            ('42', 30, 'book.pdf', 123),
            ('42', 30, '', 0),
            ('42', 31, 'book.pdf', 123),
            ('42', 31, 'book.pdf', 124),
            ('42', 31, 'other.pdf', 123),
            (42, 30, 'x', 1),            # int source_chat_id must normalize to str
            ('99', 30, 'x', 1),
            (None, None, 'book.pdf', 123),
            (None, None, 'book.pdf', 0),
            ('42', None, 'nope.pdf', 9),
            ('', 0, '', 0),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(
                    index.contains(*case),
                    self.db.is_book_indexed(*case, conn=self.conn),
                    f'index diverged from is_book_indexed for {case}',
                )

    def test_keys_added_during_the_run_normalize_source_chat_id_like_the_sql(self):
        # add_book() stores str(source_chat_id); the index must match that so a
        # duplicate inside the same run is still caught regardless of int/str.
        index = self.db.BookDedupeIndex()
        index.add(42, 30, 'run.pdf', 55)
        self.assertTrue(index.contains('42', 30, 'x', 1),
                        'int source_chat_id was not normalized to str on add()')
        self.assertTrue(index.contains(42, 30, 'x', 1))


if __name__ == '__main__':
    unittest.main()
