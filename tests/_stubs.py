"""Offline import stubs for testing src.web without production dependencies.

Installs in-memory fakes for ``src.config``, ``src.database``, ``src.services.*``
and ``aiogram`` BEFORE ``src.web`` is imported, so the whole security suite runs
with no secrets, no network, no aiogram and no real database.

Import ``load_web()`` from this module; it is idempotent.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import importlib.util
import json
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "web.py"

# Synthetic, non-secret values. The token is fake and never used against Telegram.
BOT_TOKEN = "000000000:TEST_TOKEN_NOT_A_SECRET"
USER_ID = 111111
OTHER_ID = 222222
ADMIN_ID = 999999

# Every DB call made through the fake module is appended here.
db_calls: List[Dict[str, Any]] = []
_settings_store: Dict[int, Dict[str, Any]] = {}
COPIER_DEBUG = {
    "version": "v-test",
    "running": False,
    "status": "SYNTHETIC_STATUS",
    "error": "SYNTHETIC_INTERNAL_ERROR_TEXT",
    "last_offset": 4242,
}


def _module(name: str, **attrs: Any) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _db_fake(name: str):
    def fake(*args: Any, **kwargs: Any):
        db_calls.append({"name": name, "args": list(args), "kwargs": kwargs})
        if name == "get_secretary_settings":
            return dict(_settings_store.get(args[0], {}), user_id=args[0])
        if name == "update_secretary_settings":
            _settings_store.setdefault(args[0], {}).update(kwargs)
            return None
        if name in ("add_service", "add_football_stream", "add_secretary_schedule"):
            return 101
        if name == "count_services":
            return 0
        if name == "get_service_by_id":
            return {"id": args[0], "title": "Synthetic public listing"}
        if name.startswith("get_"):
            return []
        return None

    return fake


def _async_fake(name: str, value: Any):
    async def fake(*args: Any, **kwargs: Any):
        db_calls.append({"name": name, "args": list(args), "kwargs": kwargs})
        return json.loads(json.dumps(value))

    return fake


_PROVIDERS = {
    "cbu_service": {
        "get_currency_history": {"points": []},
        "get_all_rates": {"USD": {"rate": 1}},
    },
    "prayer_service": {"get_prayer_times": {"fajr": "05:00"}},
    "football_service": {
        "get_standings": {"table": []},
        "get_matches": [],
        "get_all_live_and_today_matches": [],
    },
    "weather_service": {
        "get_coordinates_by_city": [0, 0, "Synthetic", "Synthetic"],
        "get_weather": {"synthetic": True},
    },
}


def install_stubs() -> None:
    """Register all fake modules (idempotent)."""
    if isinstance(sys.modules.get("src.config"), types.ModuleType) and getattr(
        sys.modules["src.config"], "_IS_TEST_STUB", False
    ):
        return

    _module("src", __path__=[])
    _module("src.services", __path__=[])
    _module("aiogram", __path__=[])

    class _Keyboard:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    _module("aiogram.types", InlineKeyboardMarkup=_Keyboard, InlineKeyboardButton=_Keyboard)
    _module(
        "src.config",
        ADMIN_ID=ADMIN_ID,
        ADMIN_IDS=[ADMIN_ID],
        BOT_TOKEN=BOT_TOKEN,
        _IS_TEST_STUB=True,
    )

    text = SOURCE.read_text(encoding="utf-8")
    db_names = {
        alias.name
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.ImportFrom) and node.module == "src.database"
        for alias in node.names
    }
    _module("src.database", **{n: _db_fake(n) for n in db_names})

    for provider, funcs in _PROVIDERS.items():
        _module(
            "src.services." + provider,
            **{
                provider: types.SimpleNamespace(
                    **{k: _async_fake(k, v) for k, v in funcs.items()}
                )
            },
        )
    _module(
        "src.services.secretary_service",
        SECRETARY_MODES={"normal": "Synthetic"},
        secretary_service=types.SimpleNamespace(
            get_detailed_time_context=lambda: "Synthetic offline time"
        ),
    )
    _module(
        "src.services.ai_secretary_service",
        generate_ai_reply=_async_fake("generate_ai_reply", "Synthetic reply"),
    )
    _module(
        "src.services.book_service",
        get_copier_debug_status=lambda: dict(COPIER_DEBUG),
    )


def load_web():
    """Import (once) and return the real src.web module on top of the stubs."""
    install_stubs()
    if "src.web" in sys.modules and getattr(sys.modules["src.web"], "__file__", None):
        return sys.modules["src.web"]
    spec = importlib.util.spec_from_file_location("src.web", SOURCE)
    web = importlib.util.module_from_spec(spec)
    sys.modules["src.web"] = web
    spec.loader.exec_module(web)
    return web


def sign_init_data(user_id: int = USER_ID, auth_date: Any = "now") -> str:
    """Build a correctly HMAC-signed initData string.

    ``auth_date``: "now" for current time, None to omit the field entirely,
    or any raw value (int/str) to embed verbatim.
    """
    payload = {"user": json.dumps({"id": user_id, "first_name": "Synthetic"}, separators=(",", ":"))}
    if auth_date is not None:
        payload["auth_date"] = str(int(time.time()) if auth_date == "now" else auth_date)
    check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def reset_state() -> None:
    db_calls.clear()
    _settings_store.clear()
    web = sys.modules.get("src.web")
    if web is not None and hasattr(web, "_rate_limit_cache"):
        web._rate_limit_cache.clear()
