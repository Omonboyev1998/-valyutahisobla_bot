"""Offline tests for the durable forward journal (no Telegram, no Turso).

The journal exists for exactly one reason: with batched inserts, a crash
between ``forward_messages`` and the batch commit would otherwise re-forward
those messages on the next pass and duplicate them in the storage channel.
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


def load_journal():
    spec = importlib.util.spec_from_file_location(
        'offline_book_journal',
        Path(__file__).resolve().parents[1] / 'src/services/book_journal.py',
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class JournalDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_journal()
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'nested', 'book_copy_journal.jsonl')

    def test_forwarded_entry_survives_a_process_restart(self):
        journal = self.mod.ForwardJournal(self.path)
        journal.record_forwarded(
            source_chat_id='777000', source_message_id=11,
            file_name='Kitob.pdf', file_size=4242, storage_message_id=500011,
        )

        # A brand-new object, as if the process had been killed and restarted.
        reopened = self.mod.ForwardJournal(self.path)
        entries = reopened.pending()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['source_message_id'], 11)
        self.assertEqual(entries[0]['storage_message_id'], 500011)
        self.assertEqual(entries[0]['file_name'], 'Kitob.pdf')
        self.assertEqual(entries[0]['file_size'], 4242)

    def test_clearing_after_a_committed_batch_leaves_nothing_pending(self):
        journal = self.mod.ForwardJournal(self.path)
        for i in (1, 2, 3):
            journal.record_forwarded('777000', i, f'k{i}.pdf', i, 500000 + i)

        journal.clear()

        self.assertEqual(self.mod.ForwardJournal(self.path).pending(), [],
                         'committed entries were not cleared')

    def test_a_truncated_last_line_is_ignored_not_fatal(self):
        journal = self.mod.ForwardJournal(self.path)
        journal.record_forwarded('777000', 5, 'ok.pdf', 5, 500005)
        with open(self.path, 'a', encoding='utf-8') as fh:
            fh.write('{"source_message_id": 6, "file_na')  # killed mid-write

        entries = self.mod.ForwardJournal(self.path).pending()

        self.assertEqual([e['source_message_id'] for e in entries], [5])

    def test_repeated_entries_for_one_message_collapse_to_the_latest(self):
        # The copier writes once BEFORE forwarding (no storage id yet) and once
        # after (with the storage id). Reconciliation must see ONE row, not two,
        # otherwise a crashed batch would be inserted twice.
        journal = self.mod.ForwardJournal(self.path)
        journal.record_forwarded('777000', 11, 'Kitob.pdf', 4242)
        journal.record_forwarded('777000', 11, 'Kitob.pdf', 4242, storage_message_id=500011)

        entries = self.mod.ForwardJournal(self.path).pending()

        self.assertEqual(len(entries), 1, f'journal did not collapse duplicates: {entries}')
        self.assertEqual(entries[0]['storage_message_id'], 500011,
                         'the latest (complete) entry must win')

    def test_only_entries_with_a_storage_id_count_as_definitely_forwarded(self):
        # An entry written BEFORE the forward (no storage id) is ambiguous: the
        # forward may have failed. Only a post-forward entry proves delivery,
        # so only those may be reconciled / block a re-forward.
        journal = self.mod.ForwardJournal(self.path)
        journal.record_forwarded('777000', 7, 'ambiguous.pdf', 10)
        journal.record_forwarded('777000', 8, 'done.pdf', 20)
        journal.record_forwarded('777000', 8, 'done.pdf', 20, storage_message_id=500008)

        reopened = self.mod.ForwardJournal(self.path)

        self.assertEqual(
            [e['source_message_id'] for e in reopened.forwarded_entries()], [8],
            'an un-forwarded (ambiguous) entry must not be treated as forwarded',
        )
        self.assertEqual(len(reopened.pending()), 2)


if __name__ == '__main__':
    unittest.main()
