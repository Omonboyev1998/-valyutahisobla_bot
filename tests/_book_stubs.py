"""Offline stubs for exercising ``src.services.book_service`` with no network.

Installs fake ``telethon``, ``aiogram``, ``src.config``, ``src.database`` and
``src.userbot.listener`` modules, then loads the REAL book_service module on top
of them.  Nothing here talks to Telegram or Turso; every database call is
recorded in :class:`FakeDatabase` so tests can assert on round-trip counts
instead of on timing.

``install()`` snapshots ``sys.modules`` and ``restore()`` puts it back, so this
module cannot leak state into the rest of the suite.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
BOOK_SERVICE_SOURCE = ROOT / "src" / "services" / "book_service.py"


def _load_real_dedupe_index_class():
    """Loads the REAL BookDedupeIndex out of src/database.py (no env, no driver).

    The copier tests then exercise the production dedupe semantics instead of a
    re-implementation that could silently drift from ``is_book_indexed``.
    """
    import os
    from unittest.mock import patch as _patch

    spec = importlib.util.spec_from_file_location(
        "_book_stubs_real_database", ROOT / "src" / "database.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with _patch.dict(os.environ, {}, clear=True):
        spec.loader.exec_module(module)
    return module.BookDedupeIndex


_RealBookDedupeIndex = _load_real_dedupe_index_class()


class REAL_BookDedupeIndex(_RealBookDedupeIndex):  # type: ignore[misc,valid-type]
    """Same production class, but with a ``__dict__`` so tests can wrap methods."""


_journal_dirs: List[Any] = []


def _journal_dir():
    """A fresh temp dir per install(); kept alive so the path stays valid."""
    import tempfile

    d = tempfile.mkdtemp(prefix="book_journal_")
    _journal_dirs.append(d)
    return Path(d)


def journal_path() -> str:
    """Path of the journal used by the most recently installed book_service."""
    return str(Path(_journal_dirs[-1]) / "book_copy_journal.jsonl")

_TOUCHED = (
    "src",
    "src.config",
    "src.database",
    "src.services",
    "src.userbot",
    "src.userbot.listener",
    "src.services.book_service",
    "src.services.book_journal",
    "telethon",
    "telethon.errors",
    "telethon.tl",
    "telethon.tl.types",
    "aiogram",
    "aiogram.types",
)

_snapshot: Dict[str, Any] = {}


class FakeFloodWaitError(Exception):
    def __init__(self, seconds: int = 7):
        super().__init__(f"flood wait {seconds}")
        self.seconds = seconds


class FakeConnection:
    """Stand-in for a libsql/sqlite connection handed out by ``db_session``."""

    def __init__(self, index: int):
        self.index = index
        self.closed = False


class FakeDatabase:
    """Records every database interaction made by the copier."""

    def __init__(self, flush_every_default: int = 25):
        self.calls: List[Dict[str, Any]] = []
        self.acquisitions = 0
        self.conns: List[FakeConnection] = []
        self.settings: Dict[str, str] = {}
        # (source_chat_id, source_message_id) and (file_name, file_size) indexes
        self.books: List[Dict[str, Any]] = []
        self.flush_every_default = flush_every_default
        self.batch_error: Optional[BaseException] = None

    # -- connection handling -------------------------------------------------
    def _new_conn(self) -> FakeConnection:
        self.acquisitions += 1
        conn = FakeConnection(self.acquisitions)
        self.conns.append(conn)
        return conn

    def live_connections(self) -> List[FakeConnection]:
        return list(self.conns)

    @contextmanager
    def get_db(self):
        conn = self._new_conn()
        try:
            yield conn
        finally:
            conn.closed = True

    @contextmanager
    def db_session(self):
        conn = self._new_conn()
        try:
            yield conn
        finally:
            conn.closed = True

    # -- recorded helpers ----------------------------------------------------
    def _record(self, name: str, conn: Optional[FakeConnection], **fields: Any) -> None:
        if conn is None:
            self.acquisitions += 1
        self.calls.append({"name": name, "shared_conn": conn is not None, **fields})

    def get_userbot_setting(self, key: str, default: str = "", conn: Optional[FakeConnection] = None) -> str:
        self._record("get_userbot_setting", conn, key=key)
        return self.settings.get(key, default)

    def set_userbot_setting(self, key: str, value: str, conn: Optional[FakeConnection] = None) -> bool:
        self._record("set_userbot_setting", conn, key=key, value=str(value))
        self.settings[key] = str(value)
        return True

    def is_book_indexed(
        self,
        source_chat_id: Optional[str],
        source_message_id: Optional[int],
        file_name: str,
        file_size: int,
        conn: Optional[FakeConnection] = None,
    ) -> bool:
        self._record(
            "is_book_indexed",
            conn,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            file_name=file_name,
            file_size=file_size,
        )
        for book in self.books:
            if source_chat_id and source_message_id:
                if (
                    book.get("source_chat_id") == str(source_chat_id)
                    and book.get("source_message_id") == source_message_id
                ):
                    return True
            if file_name and file_size:
                if book.get("file_name") == file_name and book.get("file_size") == file_size:
                    return True
        return False

    def add_book(self, conn: Optional[FakeConnection] = None, **kwargs: Any) -> int:
        self._record("add_book", conn, **kwargs)
        row = dict(kwargs)
        row["source_chat_id"] = str(row.get("source_chat_id")) if row.get("source_chat_id") else None
        self.books.append(row)
        return len(self.books)

    def add_books_batch(self, books, conn: Optional[FakeConnection] = None) -> int:
        """Batched insert: ONE round-trip, but still one recorded row per book.

        The per-book ``add_book`` records are kept so the pre-existing
        assertions ("all 20 books must be copied", storage_chat_id, ...) keep
        their exact meaning; ``add_books_batch`` records the round-trip itself.
        """
        self._record("add_books_batch", conn, size=len(books),
                     source_message_ids=[b.get("source_message_id") for b in books])
        if self.batch_error is not None:
            raise self.batch_error
        for kwargs in books:
            self.calls.append({"name": "add_book", "shared_conn": conn is not None,
                               "batched": True, **kwargs})
            row = dict(kwargs)
            row["source_chat_id"] = str(row.get("source_chat_id")) if row.get("source_chat_id") else None
            self.books.append(row)
        return len(books)

    def load_book_dedupe_index(
        self,
        source_chat_id: Optional[str],
        conn: Optional[FakeConnection] = None,
        page_size: int = 5000,
    ):
        """Builds a REAL BookDedupeIndex from the fake rows, recording lookups."""
        self._record("load_book_dedupe_index", conn, source_chat_id=source_chat_id)
        index = REAL_BookDedupeIndex()
        for book in self.books:
            if source_chat_id and book.get("source_chat_id") == str(source_chat_id):
                index.add_source(source_chat_id, book.get("source_message_id"))
            index.add_file(book.get("file_name"), book.get("file_size"))
        db = self

        real_contains = index.contains

        def recording_contains(source_chat_id, source_message_id, file_name, file_size):
            db.calls.append(
                {
                    "name": "index_contains",
                    "shared_conn": True,
                    "source_chat_id": source_chat_id,
                    "source_message_id": source_message_id,
                    "file_name": file_name,
                    "file_size": file_size,
                }
            )
            return real_contains(source_chat_id, source_message_id, file_name, file_size)

        index.contains = recording_contains  # type: ignore[method-assign]
        return index

    # -- assertions helpers --------------------------------------------------
    def names(self, name: str) -> List[Dict[str, Any]]:
        return [c for c in self.calls if c["name"] == name]

    def setting_writes(self, key: str) -> List[Dict[str, Any]]:
        return [c for c in self.names("set_userbot_setting") if c["key"] == key]


# ---------------------------------------------------------------------------
# Fake telethon message / client
# ---------------------------------------------------------------------------
class FakeFile:
    def __init__(self, name: str, ext: str, size: int = 1024, mime_type: str = "application/pdf"):
        self.name = name
        self.ext = ext
        self.size = size
        self.mime_type = mime_type


class FakeMessage:
    def __init__(self, msg_id: int, file: Optional[FakeFile] = None, media: bool = True, message: str = ""):
        self.id = msg_id
        self.file = file
        self.media = media if file is not None else False
        self.message = message


def book_message(msg_id: int, name: str = "Kitob.pdf", ext: str = "pdf", size: Optional[int] = None) -> FakeMessage:
    return FakeMessage(msg_id, FakeFile(name, ext, size if size is not None else 1000 + msg_id))


def junk_message(msg_id: int) -> FakeMessage:
    """A scanned message that is not a book (no media at all)."""
    return FakeMessage(msg_id, None, media=False)


def wrong_ext_message(msg_id: int) -> FakeMessage:
    return FakeMessage(msg_id, FakeFile(f"video{msg_id}.mp4", "mp4", 999, "video/mp4"))


class FakeEntity:
    def __init__(self, entity_id: int, username: str = ""):
        self.id = entity_id
        self.username = username


class FakeCopiedMessage:
    def __init__(self, msg_id: int):
        self.id = msg_id


class FakeClient:
    """Minimal Telethon client covering only what the copier calls."""

    def __init__(self, messages: List[FakeMessage], forward_error: Optional[Exception] = None):
        self._messages = messages
        self.forwarded: List[int] = []
        self.forward_error = forward_error
        self.iteration_finished = False
        self.on_message = None

    async def get_dialogs(self, limit: int = 50):
        return []

    async def get_entity(self, target: Any):
        # the copier asks for the source chat first, then the storage target
        text = str(target)
        if "4326786240" in text or "fakestorage" in text or "dunyokitoblari" in text:
            return FakeEntity(4326786240, "fakestorage")
        return FakeEntity(777000, "source")

    def iter_messages(self, entity: Any, offset_id: int = 0, filter: Any = None):
        messages = self._messages

        async def gen():
            for msg in messages:
                yield msg
                # fires once the consumer has finished processing ``msg``
                if self.on_message is not None:
                    self.on_message(msg)
            self.iteration_finished = True

        return gen()

    async def forward_messages(self, dest: Any, msg: FakeMessage):
        if self.forward_error is not None:
            raise self.forward_error
        self.forwarded.append(msg.id)
        return [FakeCopiedMessage(500000 + msg.id)]


class SleepRecorder:
    """Records sleep durations; actually yields only a tick, so tests stay fast.

    Delegates to the real ``asyncio.sleep`` with a capped duration so the event
    loop still makes progress for the driver loop.
    """

    def __init__(self, cap: float = 0.001):
        import asyncio as _asyncio

        self.durations: List[float] = []
        self._cap = cap
        self._real = _asyncio.sleep

    async def __call__(self, seconds: float):
        self.durations.append(seconds)
        await self._real(min(seconds, self._cap))


# ---------------------------------------------------------------------------
# module installation
# ---------------------------------------------------------------------------
def install(db: FakeDatabase, config_overrides: Optional[Dict[str, Any]] = None):
    """Install stub modules and return the freshly loaded book_service module."""
    for name in _TOUCHED:
        _snapshot[name] = sys.modules.get(name, KeyError)

    def mod(name: str, **attrs: Any) -> types.ModuleType:
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m
        return m

    mod("src", __path__=[])
    mod("src.services", __path__=[])
    mod("src.userbot", __path__=[])

    mod("telethon", __path__=[], TelegramClient=object)
    mod("telethon.errors", FloodWaitError=FakeFloodWaitError)
    mod("telethon.tl", __path__=[])
    mod("telethon.tl.types", InputMessagesFilterDocument=object())
    mod("aiogram", __path__=[], Bot=object)
    mod("aiogram.types", InlineKeyboardMarkup=object, InlineKeyboardButton=object)

    cfg = {
        "BOOK_SOURCE_CHAT": "fake_source_chat",
        "BOOK_STORAGE_CHAT": "@fakestorage",
        "BOOK_STORAGE_CHAT_ID": -1004326786240,
        "BOOK_COPY_PAUSE_SECONDS": 0.4,
        "BOOK_PROGRESS_FLUSH_EVERY": 25,
        "BOOK_INSERT_BATCH_SIZE": 1,
        "BOOK_JOURNAL_PATH": str(_journal_dir() / "book_copy_journal.jsonl"),
        "_IS_TEST_STUB": True,
    }
    cfg.update(config_overrides or {})
    mod("src.config", **cfg)

    mod(
        "src.database",
        get_db=db.get_db,
        db_session=db.db_session,
        get_userbot_setting=db.get_userbot_setting,
        set_userbot_setting=db.set_userbot_setting,
        is_book_indexed=db.is_book_indexed,
        load_book_dedupe_index=db.load_book_dedupe_index,
        BookDedupeIndex=REAL_BookDedupeIndex,
        add_book=lambda **kw: db.add_book(**kw),
        add_books_batch=lambda books, conn=None: db.add_books_batch(books, conn=conn),
        get_book_by_id=lambda *a, **k: None,
        increment_book_download=lambda *a, **k: None,
        get_books_count=lambda *a, **k: len(db.books),
        search_books_db=lambda *a, **k: [],
    )

    async def _get_or_create_client():
        raise AssertionError("tests must inject their own fake client")

    mod("src.userbot.listener", get_or_create_client=_get_or_create_client)

    # The REAL journal module (pure stdlib, no network) is loaded on top of the
    # stubbed ``src.services`` package so the copier exercises production code.
    journal_spec = importlib.util.spec_from_file_location(
        "src.services.book_journal", ROOT / "src" / "services" / "book_journal.py"
    )
    assert journal_spec is not None and journal_spec.loader is not None
    journal_mod = importlib.util.module_from_spec(journal_spec)
    sys.modules["src.services.book_journal"] = journal_mod
    journal_spec.loader.exec_module(journal_mod)

    spec = importlib.util.spec_from_file_location(
        "src.services.book_service", BOOK_SERVICE_SOURCE
    )
    book_service = importlib.util.module_from_spec(spec)
    sys.modules["src.services.book_service"] = book_service
    spec.loader.exec_module(book_service)
    return book_service


def restore() -> None:
    for name, value in _snapshot.items():
        if value is KeyError:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value
    _snapshot.clear()
