"""Offline throughput tests for the book copier.

No Telegram, no Turso: every dependency is a fake from ``tests/_book_stubs``.
Assertions are on *database round-trip counts* and *connection acquisitions*,
never on wall-clock timing.
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _book_stubs as bs  # noqa: E402


class CopierTestCase(unittest.TestCase):
    """Loads a fresh book_service on fakes for every test."""

    config_overrides: dict = {}

    def setUp(self):
        self.db = bs.FakeDatabase()
        self.book_service = bs.install(self.db, self.config_overrides)
        self.addCleanup(bs.restore)

    def drive(self, messages, limit_total=50000, forward_error=None, on_message=None, timeout=5.0):
        """Run one copier pass over ``messages`` and stop it like production would."""
        client = bs.FakeClient(messages, forward_error=forward_error)
        client.on_message = on_message
        listener = sys.modules["src.userbot.listener"]

        async def fake_get_or_create_client():
            return client

        listener.get_or_create_client = fake_get_or_create_client

        async def runner():
            task = asyncio.create_task(self.book_service.run_book_copier(limit_total=limit_total))
            waited = 0.0
            while not client.iteration_finished and not task.done() and waited < timeout:
                await asyncio.sleep(0.01)
                waited += 0.01
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            return client

        return asyncio.run(runner())


class ProgressWriteTests(CopierTestCase):
    def test_non_book_messages_do_not_write_progress_per_message(self):
        messages = [bs.junk_message(i) for i in range(1, 11)]

        self.drive(messages)

        writes = self.db.setting_writes("last_scanned_book_msg_id")
        self.assertLessEqual(
            len(writes),
            1,
            f"10 non-book messages caused {len(writes)} progress writes: {writes}",
        )

    def test_progress_is_flushed_when_the_loop_is_stopped(self):
        messages = [bs.junk_message(i) for i in range(1, 6)]

        def stop_after_third(msg):
            if msg.id == 3:
                self.book_service.stop_indexing()

        self.drive(messages, on_message=stop_after_third)

        self.assertEqual(self.db.settings.get("last_book_offset_id"), "3")
        self.assertEqual(self.db.settings.get("last_scanned_book_msg_id"), "3")

    def test_progress_written_at_most_once_per_flush_interval(self):
        # 100 scanned messages with flush interval 25 => at most 4 periodic writes
        messages = [bs.junk_message(i) for i in range(1, 101)]

        self.drive(messages)

        offset_writes = self.db.setting_writes("last_book_offset_id")
        self.assertLessEqual(
            len(offset_writes),
            5,
            f"100 messages caused {len(offset_writes)} offset writes (flush_every=25)",
        )
        self.assertGreaterEqual(
            len(offset_writes), 1, "progress must still be persisted periodically"
        )

    def test_progress_never_lags_more_than_flush_interval(self):
        messages = [bs.junk_message(i) for i in range(1, 76)]

        self.drive(messages)

        persisted = int(self.db.settings.get("last_scanned_book_msg_id", "0"))
        self.assertGreaterEqual(
            persisted, 75 - 25, f"progress lagged too far behind: persisted={persisted}"
        )

class FlushOnExitTests(CopierTestCase):
    def test_progress_is_flushed_when_a_scan_pass_finishes_the_batch(self):
        # 10 messages, flush interval 25 => no periodic flush happens mid-loop
        messages = [bs.junk_message(i) for i in range(1, 11)]

        self.drive(messages)

        self.assertEqual(self.db.settings.get("last_scanned_book_msg_id"), "10")

    def test_progress_is_flushed_when_the_pass_raises(self):
        messages = [bs.junk_message(i) for i in range(1, 8)]
        boom = RuntimeError("synthetic iteration failure")

        client = bs.FakeClient(messages)
        listener = sys.modules["src.userbot.listener"]

        async def fake_get_or_create_client():
            return client

        listener.get_or_create_client = fake_get_or_create_client

        original = client.forward_messages

        def exploding_iter(entity, offset_id=0, filter=None):
            async def gen():
                for msg in messages:
                    yield msg
                raise boom

            return gen()

        client.iter_messages = exploding_iter

        async def runner():
            task = asyncio.create_task(self.book_service.run_book_copier())
            await asyncio.sleep(0.2)
            self.book_service.stop_indexing()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        asyncio.run(runner())

        self.assertEqual(
            self.db.settings.get("last_scanned_book_msg_id"),
            "7",
            "progress must be flushed even when the scan pass raises",
        )

    def test_progress_is_flushed_when_the_task_is_cancelled(self):
        messages = [bs.junk_message(i) for i in range(1, 500)]

        client = bs.FakeClient(messages)
        listener = sys.modules["src.userbot.listener"]

        async def fake_get_or_create_client():
            return client

        listener.get_or_create_client = fake_get_or_create_client

        seen = []

        def slow_iter(entity, offset_id=0, filter=None):
            async def gen():
                for msg in messages:
                    yield msg
                    seen.append(msg.id)
                    await asyncio.sleep(0.01)

            return gen()

        client.iter_messages = slow_iter

        async def runner():
            task = asyncio.create_task(self.book_service.run_book_copier())
            await asyncio.sleep(0.1)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        asyncio.run(runner())

        persisted = int(self.db.settings.get("last_scanned_book_msg_id", "0"))
        self.assertGreater(persisted, 0, "cancellation must not lose all progress")
        self.assertGreaterEqual(
            persisted, max(seen) - 25, f"cancellation lost too much progress: {persisted} of {max(seen)}"
        )

class SharedConnectionTests(CopierTestCase):
    def test_scan_pass_reuses_one_connection_instead_of_one_per_operation(self):
        # 20 real books => today: 1 offset read + 20 is_book_indexed + 20 add_book
        # + progress writes, each on its own connection.
        messages = [bs.book_message(i, f"Kitob{i}.pdf") for i in range(1, 21)]

        # Keep real 0.4s pacing: 20 books need 8s, beyond the default 5s
        # guard on Linux (Windows timer granularity masked this previously).
        self.drive(messages, timeout=12.0)

        self.assertEqual(len(self.db.names("add_book")), 20, "all 20 books must be copied")
        self.assertLessEqual(
            self.db.acquisitions,
            5,
            f"scan pass opened {self.db.acquisitions} connections for 20 books",
        )

    def test_get_db_api_is_unchanged_for_other_callers(self):
        import src.database as database

        with database.get_db() as conn:
            self.assertIsNotNone(conn)
        # a bare get_db() call still acquires exactly one connection
        self.assertEqual(self.db.acquisitions, 1)

    def test_connection_is_released_before_the_idle_wait(self):
        # An empty batch makes the copier go idle for 60s; it must not hold a
        # Turso connection open for that whole wait.
        client = bs.FakeClient([])
        listener = sys.modules["src.userbot.listener"]

        async def fake_get_or_create_client():
            return client

        listener.get_or_create_client = fake_get_or_create_client

        async def runner():
            task = asyncio.create_task(self.book_service.run_book_copier())
            waited = 0.0
            while not client.iteration_finished and waited < 5.0:
                await asyncio.sleep(0.01)
                waited += 0.01
            await asyncio.sleep(0.2)  # inside the idle wait now
            open_conns = [c for c in self.db.live_connections() if not c.closed]
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            return open_conns

        open_conns = asyncio.run(runner())
        self.assertEqual(
            open_conns, [], "a connection was still open during the 60s idle wait"
        )

class DuplicateProtectionTests(CopierTestCase):
    def test_duplicate_check_uses_source_chat_and_message_id(self):
        msg = bs.book_message(42, "Alisher.pdf", size=5555)
        self.db.books.append(
            {
                "source_chat_id": "777000",
                "source_message_id": 42,
                "file_name": "butunlay-boshqa-nom.pdf",
                "file_size": 1,
            }
        )

        client = self.drive([msg])

        self.assertEqual(client.forwarded, [], "already-indexed source msg was re-copied")
        self.assertEqual(len(self.db.names("add_book")), 0)

    def test_duplicate_check_uses_file_name_and_file_size(self):
        msg = bs.book_message(99, "Alisher.pdf", size=5555)
        self.db.books.append(
            {
                "source_chat_id": "999999",
                "source_message_id": 1,
                "file_name": "Alisher.pdf",
                "file_size": 5555,
            }
        )

        client = self.drive([msg])

        self.assertEqual(client.forwarded, [], "same file_name+file_size was re-copied")
        self.assertEqual(len(self.db.names("add_book")), 0)

    def test_duplicate_check_arguments_are_unchanged(self):
        msg = bs.book_message(7, "Yangi.pdf", size=4242)

        self.drive([msg])

        # The dedupe check now runs against the in-memory index, but it must be
        # consulted with exactly the same four normalized values as before.
        calls = self.db.names("index_contains") or self.db.names("is_book_indexed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["source_chat_id"], "777000")
        self.assertEqual(calls[0]["source_message_id"], 7)
        self.assertEqual(calls[0]["file_name"], "Yangi.pdf")
        self.assertEqual(calls[0]["file_size"], 4242)

    def test_new_book_is_copied_and_stored_with_storage_chat_id(self):
        msg = bs.book_message(11, "Toza.pdf", size=1234)

        client = self.drive([msg])

        self.assertEqual(client.forwarded, [11])
        rows = self.db.names("add_book")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["storage_chat_id"], "-1004326786240")
        self.assertEqual(rows[0]["source_message_id"], 11)

    def test_a_book_scanned_twice_in_one_pass_is_only_copied_once(self):
        msgs = [bs.book_message(5, "Bir.pdf", size=321), bs.book_message(5, "Bir.pdf", size=321)]

        client = self.drive(msgs)

        self.assertEqual(client.forwarded, [5], "shared connection broke duplicate protection")
        self.assertEqual(len(self.db.names("add_book")), 1)

    def test_non_book_extensions_are_skipped_without_db_lookup(self):
        msgs = [bs.wrong_ext_message(i) for i in range(1, 6)]

        client = self.drive(msgs)

        self.assertEqual(client.forwarded, [])
        self.assertEqual(len(self.db.names("is_book_indexed")), 0)

class InMemoryDedupeIndexTests(CopierTestCase):
    def test_scan_pass_does_not_query_the_db_once_per_candidate_book(self):
        messages = [bs.book_message(i, f"Kitob{i}.pdf") for i in range(1, 21)]

        self.drive(messages, timeout=12.0)

        per_book = self.db.names("is_book_indexed")
        self.assertEqual(len(self.db.names("add_book")), 20, "all 20 books must be copied")
        self.assertEqual(
            len(per_book),
            0,
            f"{len(per_book)} per-book is_book_indexed queries remain; index must be loaded once",
        )
        self.assertEqual(
            len(self.db.names("load_book_dedupe_index")),
            1,
            "the dedupe index must be bulk-loaded exactly once per scan pass",
        )

    def test_duplicate_inside_the_same_run_is_caught_by_the_in_memory_index(self):
        # Same file_name+file_size, different message ids: the second one must be
        # rejected by keys added during THIS run, with no DB query.
        messages = [
            bs.book_message(11, "Takror.pdf", size=777),
            bs.book_message(12, "Takror.pdf", size=777),
        ]

        client = self.drive(messages)

        self.assertEqual(client.forwarded, [11], "same-run duplicate was forwarded twice")
        self.assertEqual(len(self.db.names("add_book")), 1)
        self.assertEqual(len(self.db.names("is_book_indexed")), 0)

    def test_preexisting_rows_still_block_a_copy_without_any_per_book_query(self):
        self.db.books.append(
            {
                "source_chat_id": "777000",
                "source_message_id": 50,
                "file_name": "boshqa.pdf",
                "file_size": 1,
            }
        )
        client = self.drive([bs.book_message(50, "Yangi.pdf", size=9999)])

        self.assertEqual(client.forwarded, [], "pre-indexed source msg was re-copied")
        self.assertEqual(len(self.db.names("is_book_indexed")), 0)


class BatchedInsertTests(CopierTestCase):
    config_overrides = {"BOOK_INSERT_BATCH_SIZE": 5}

    def test_inserts_are_batched_instead_of_one_remote_write_per_book(self):
        messages = [bs.book_message(i, f"Kitob{i}.pdf") for i in range(1, 11)]

        self.drive(messages, timeout=12.0)

        self.assertEqual(len(self.db.books), 10, "all 10 books must reach the database")
        batches = self.db.names("add_books_batch")
        self.assertEqual(
            len(batches),
            2,
            f"10 books with batch size 5 must be 2 batched writes, got {len(batches)}",
        )

    def test_batch_is_flushed_when_the_loop_is_stopped_mid_batch(self):
        # 3 books with batch size 5: the batch never fills, so only the stop
        # path can persist them.
        messages = [bs.book_message(i, f"K{i}.pdf") for i in (3, 2, 1)]

        def stop_after_second(msg):
            if msg.id == 2:
                self.book_service.stop_indexing()

        self.drive(messages, on_message=stop_after_second, timeout=12.0)

        persisted = sorted(b["source_message_id"] for b in self.db.books)
        self.assertEqual(persisted, [2, 3], f"stop lost the pending batch: {persisted}")
        self.assertEqual(self.db.settings.get("last_book_offset_id"), "2")

    def test_batch_is_flushed_when_the_limit_is_reached(self):
        messages = [bs.book_message(i, f"K{i}.pdf") for i in (3, 2, 1)]

        self.drive(messages, limit_total=2, timeout=12.0)

        persisted = sorted(b["source_message_id"] for b in self.db.books)
        self.assertEqual(persisted, [2, 3], f"limit lost the pending batch: {persisted}")
        self.assertEqual(self.db.settings.get("last_book_offset_id"), "2")

    def test_checkpoint_never_advances_past_an_uncommitted_book(self):
        # Batch size 5, 3 books, the batch write always fails: the checkpoint
        # must stay behind every one of them.
        messages = [bs.book_message(i, f"K{i}.pdf") for i in (3, 2, 1)]
        self.db.batch_error = RuntimeError("synthetic batch commit failure")

        self.drive(messages, timeout=12.0)

        self.assertEqual(len(self.db.books), 0)
        self.assertIn(
            self.db.settings.get("last_book_offset_id", "0"), ("0", None),
            "checkpoint advanced past books whose rows were never committed",
        )


class BatchSizeConfigTests(CopierTestCase):
    def test_batch_size_defaults_to_ten_in_production_config(self):
        import importlib.util
        import os
        from pathlib import Path
        from unittest.mock import patch

        spec = importlib.util.spec_from_file_location(
            "offline_real_config", Path(__file__).resolve().parents[1] / "src/config.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"BOT_TOKEN": "offline-test-placeholder"}, clear=True):
            spec.loader.exec_module(module)

        self.assertEqual(module.BOOK_INSERT_BATCH_SIZE, 10)
        self.assertEqual(module.BOOK_COPY_PAUSE_SECONDS, 0.4)
        self.assertEqual(module.BOOK_PROGRESS_FLUSH_EVERY, 25)

    def test_journal_path_defaults_into_the_writable_data_dir(self):
        import importlib.util
        import os
        from pathlib import Path
        from unittest.mock import patch

        spec = importlib.util.spec_from_file_location(
            "offline_real_config3", Path(__file__).resolve().parents[1] / "src/config.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"BOT_TOKEN": "offline-test-placeholder"}, clear=True):
            spec.loader.exec_module(module)

        self.assertTrue(module.BOOK_JOURNAL_PATH, "BOOK_JOURNAL_PATH is not configured")
        self.assertIn("data", module.BOOK_JOURNAL_PATH.replace("\\", "/"))
        self.assertTrue(module.BOOK_JOURNAL_PATH.endswith(".jsonl"))

    def test_batch_size_is_read_from_the_environment(self):
        import importlib.util
        import os
        from pathlib import Path
        from unittest.mock import patch

        spec = importlib.util.spec_from_file_location(
            "offline_real_config2", Path(__file__).resolve().parents[1] / "src/config.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"BOT_TOKEN": "offline-test-placeholder",
                                     "BOOK_INSERT_BATCH_SIZE": "7"}, clear=True):
            spec.loader.exec_module(module)

        self.assertEqual(module.BOOK_INSERT_BATCH_SIZE, 7)


class CrashBetweenForwardAndCommitTests(CopierTestCase):
    """The journal must stop a crashed batch from re-forwarding books."""

    config_overrides = {"BOOK_INSERT_BATCH_SIZE": 5}

    def test_restart_after_a_failed_batch_commit_does_not_forward_again(self):
        messages = [bs.book_message(i, f"Kitob{i}.pdf") for i in (3, 2, 1)]

        # --- pass 1: forwards succeed, the batch commit "crashes" -----------
        self.db.batch_error = RuntimeError("synthetic crash before batch commit")
        first = self.drive(messages, timeout=12.0)
        self.assertEqual(first.forwarded, [3, 2, 1], "pass 1 must forward all three")
        self.assertEqual(len(self.db.books), 0, "the crashed batch must not be committed")

        journal_file = bs.journal_path()

        # --- pass 2: brand new process, SAME journal file -------------------
        bs.restore()
        db2 = bs.FakeDatabase()
        self.book_service = bs.install(
            db2,
            {"BOOK_INSERT_BATCH_SIZE": 5, "BOOK_JOURNAL_PATH": journal_file},
        )
        self.db = db2
        second = self.drive(messages, timeout=12.0)

        self.assertEqual(
            second.forwarded,
            [],
            f"books were forwarded a SECOND time after the crash: {second.forwarded}",
        )

    def test_the_crashed_batch_is_reconciled_into_the_database_on_restart(self):
        messages = [bs.book_message(i, f"Kitob{i}.pdf") for i in (3, 2, 1)]

        self.db.batch_error = RuntimeError("synthetic crash before batch commit")
        self.drive(messages, timeout=12.0)
        journal_file = bs.journal_path()

        bs.restore()
        db2 = bs.FakeDatabase()
        self.book_service = bs.install(
            db2,
            {"BOOK_INSERT_BATCH_SIZE": 5, "BOOK_JOURNAL_PATH": journal_file},
        )
        self.db = db2
        self.drive(messages, timeout=12.0)

        recovered = sorted(b["source_message_id"] for b in db2.books)
        self.assertEqual(
            recovered, [1, 2, 3],
            f"forwarded-but-uncommitted books were lost: {recovered}",
        )
        for book in db2.books:
            self.assertEqual(book["storage_chat_id"], "-1004326786240")
            self.assertEqual(book["storage_message_id"], 500000 + book["source_message_id"])


class PauseAndFloodWaitTests(CopierTestCase):
    def patch_sleep(self):
        """Install a recording sleeper on book_service's asyncio, restoring after."""
        import asyncio as real_asyncio

        recorder = bs.SleepRecorder()
        original = real_asyncio.sleep
        real_asyncio.sleep = recorder
        self.addCleanup(setattr, real_asyncio, "sleep", original)
        return recorder

    def test_inter_copy_pause_defaults_to_point_four_seconds(self):
        sleeper = self.patch_sleep()

        self.drive([bs.book_message(3, "A.pdf")])

        self.assertIn(0.4, sleeper.durations)

    def test_inter_copy_pause_is_read_from_config(self):
        bs.restore()
        self.db = bs.FakeDatabase()
        self.book_service = bs.install(self.db, {"BOOK_COPY_PAUSE_SECONDS": 1.75})
        sleeper = self.patch_sleep()

        self.drive([bs.book_message(3, "A.pdf")])

        self.assertIn(1.75, sleeper.durations, "pause is not read from config")
        self.assertNotIn(0.4, sleeper.durations, "hard-coded 0.4 still present")

    def test_floodwait_is_still_honoured_with_the_seconds_plus_five_backoff(self):
        sleeper = self.patch_sleep()

        client = self.drive(
            [bs.book_message(4, "B.pdf")], forward_error=bs.FakeFloodWaitError(seconds=11),
            timeout=0.01
        )

        self.assertEqual(client.forwarded, [])
        self.assertIn(16, sleeper.durations, "FloodWait backoff was removed")
        self.assertEqual(len(self.db.names("add_book")), 0)


if __name__ == "__main__":
    unittest.main()
