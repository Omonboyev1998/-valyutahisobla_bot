"""Deterministic checkpoint regression tests, without Telegram or a database."""
import asyncio
import contextlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _book_stubs as bs


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.db = bs.FakeDatabase()
        self.service = bs.install(self.db, {"BOOK_PROGRESS_FLUSH_EVERY": 1})
        self.addCleanup(bs.restore)
        self.client = bs.FakeClient([bs.junk_message(30), bs.book_message(20), bs.book_message(10)])
        self.sleeps = []

    def run_pass(self, forward=None):
        if forward:
            self.client.forward_messages = forward
        async def get_client():
            return self.client
        setattr(sys.modules['src.userbot.listener'], 'get_or_create_client', get_client)
        async def sleep(seconds):
            self.sleeps.append(seconds)
            # End on retry/idle; successful-copy pauses remain instantaneous.
            if seconds in (15, 16, 60):
                raise asyncio.CancelledError()
        with patch.object(self.service, 'asyncio', types.SimpleNamespace(sleep=sleep)):
            with contextlib.suppress(asyncio.CancelledError):
                asyncio.run(self.service.run_book_copier())
        self.assertTrue(all(c.closed for c in self.db.conns))

    def assert_safe(self):
        self.assertEqual(self.db.settings.get('last_book_offset_id'), '30')
        self.assertEqual(self.db.settings.get('last_scanned_book_msg_id'), '30')
        self.assertNotIn(10, self.client.forwarded)

    def test_forward_failure_does_not_cross_checkpoint(self):
        async def fail(dest, msg):
            raise RuntimeError('synthetic forward failure')
        self.run_pass(fail)
        self.assert_safe()

    def test_empty_forward_does_not_cross_checkpoint(self):
        async def empty(dest, msg):
            return []
        self.run_pass(empty)
        self.assert_safe()

    def test_failed_db_commit_does_not_cross_checkpoint(self):
        # The copier now writes through add_books_batch(); the invariant is
        # unchanged: a failed DB write must never advance the checkpoint.
        self.db.batch_error = RuntimeError('synthetic commit failure')
        self.run_pass()
        self.assert_safe()

    def test_failed_single_insert_path_does_not_cross_checkpoint(self):
        def fail(conn=None, **kwargs):
            raise RuntimeError('synthetic commit failure')
        self.db.add_book = fail
        self.db.add_books_batch = lambda books, conn=None: fail(conn=conn)
        self.run_pass()
        self.assert_safe()

    def test_cancel_during_forward_flushes_only_processed_messages(self):
        async def cancel(dest, msg):
            raise asyncio.CancelledError()
        self.run_pass(cancel)
        self.assert_safe()

    def test_floodwait_does_not_skip_failed_message(self):
        async def flood(dest, msg):
            raise bs.FakeFloodWaitError(11)
        self.run_pass(flood)
        self.assert_safe()
        self.assertIn(16, self.sleeps)

    def test_cancel_before_batch_flush_keeps_only_completed_prefix(self):
        self.service.BOOK_PROGRESS_FLUSH_EVERY = 25
        async def cancel(dest, msg):
            raise asyncio.CancelledError()
        self.run_pass(cancel)
        self.assert_safe()

    def test_retry_reopens_connection_and_resumes_failed_message(self):
        offsets = []
        original_forward = self.client.forward_messages
        failed = False
        def iterate(entity, offset_id=0, filter=None):
            offsets.append(offset_id)
            async def gen():
                for msg in self.client._messages:
                    if not offset_id or msg.id < offset_id:
                        yield msg
            return gen()
        async def forward(dest, msg):
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError('synthetic transient error')
            return await original_forward(dest, msg)
        async def get_client():
            return self.client
        async def sleep(seconds):
            if seconds in (15, 60):
                self.assertTrue(all(c.closed for c in self.db.conns))
            if seconds == 60:
                raise asyncio.CancelledError()
        self.client.iter_messages = iterate
        self.client.forward_messages = forward
        setattr(sys.modules['src.userbot.listener'], 'get_or_create_client', get_client)
        with patch.object(self.service, 'asyncio', types.SimpleNamespace(sleep=sleep)):
            with contextlib.suppress(asyncio.CancelledError):
                asyncio.run(self.service.run_book_copier())
        self.assertEqual(offsets, [0, 30])
        self.assertEqual(self.client.forwarded, [20, 10])
        self.assertEqual(self.db.acquisitions, 2)

    def test_success_is_checkpointed_before_pause_cancellation(self):
        async def sleep(seconds):
            raise asyncio.CancelledError()
        async def get_client():
            return self.client
        setattr(sys.modules['src.userbot.listener'], 'get_or_create_client', get_client)
        with patch.object(self.service, 'asyncio', types.SimpleNamespace(sleep=sleep)):
            with contextlib.suppress(asyncio.CancelledError):
                asyncio.run(self.service.run_book_copier())
        self.assertEqual(self.db.settings.get('last_book_offset_id'), '20')
        self.assertEqual(len(self.db.books), 1)


if __name__ == '__main__':
    unittest.main()
