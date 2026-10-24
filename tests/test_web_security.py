"""Offline security regression suite for src/web.py.

Runs with no secrets, no network, no aiogram, no real database: all production
imports are replaced by in-memory fakes (see tests/_stubs.py) and requests go
through a real aiohttp TestServer bound to loopback.

Run:  python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _stubs  # noqa: E402
from _stubs import ADMIN_ID, OTHER_ID, USER_ID, sign_init_data  # noqa: E402

web = _stubs.load_web()

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

YEAR = 31_536_000


class WebSecurityCase(unittest.IsolatedAsyncioTestCase):
    """Base: a live loopback aiohttp server over the real route table."""

    async def asyncSetUp(self) -> None:
        _stubs.reset_state()
        self.app = web.create_web_app(bot=None)
        self.client = TestClient(TestServer(self.app, host="127.0.0.1"))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def req(self, method, path, *, init_data=None, body=None, headers=None):
        hdr = dict(headers or {})
        if init_data is not None:
            hdr["X-Telegram-Init-Data"] = init_data
        start = len(_stubs.db_calls)
        resp = await self.client.request(method, path, headers=hdr, json=body)
        raw = await resp.text()
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw
        return {
            "status": resp.status,
            "body": data,
            "cors": resp.headers.get("Access-Control-Allow-Origin"),
            "calls": _stubs.db_calls[start:],
        }


class AuthDateFreshnessTests(WebSecurityCase):
    """Finding 1: validate_telegram_init_data must enforce auth_date freshness."""

    PRIVATE = "/api/secretary/settings"

    async def test_current_auth_date_is_accepted(self):
        res = await self.req("GET", self.PRIVATE, init_data=sign_init_data())
        self.assertEqual(res["status"], 200, res["body"])
        self.assertEqual(res["body"]["settings"]["user_id"], USER_ID)

    async def test_invalid_signature_still_rejected(self):
        tok = sign_init_data()
        tampered = tok[:-1] + ("0" if tok[-1] != "0" else "1")
        res = await self.req("GET", self.PRIVATE, init_data=tampered)
        self.assertEqual(res["status"], 401)

    async def test_year_old_auth_date_rejected(self):
        res = await self.req(
            "GET", self.PRIVATE, init_data=sign_init_data(auth_date=int(time.time()) - YEAR)
        )
        self.assertEqual(res["status"], 401, "stale signed initData must not authenticate")
        self.assertFalse(res["calls"])

    async def test_missing_auth_date_rejected(self):
        res = await self.req("GET", self.PRIVATE, init_data=sign_init_data(auth_date=None))
        self.assertEqual(res["status"], 401, "initData without auth_date must not authenticate")

    async def test_nonnumeric_auth_date_rejected(self):
        res = await self.req("GET", self.PRIVATE, init_data=sign_init_data(auth_date="not-a-date"))
        self.assertEqual(res["status"], 401, "non-numeric auth_date must not authenticate")

    async def test_future_auth_date_rejected(self):
        res = await self.req(
            "GET", self.PRIVATE, init_data=sign_init_data(auth_date=int(time.time()) + YEAR)
        )
        self.assertEqual(res["status"], 401, "far-future auth_date must not authenticate")

    async def test_small_clock_skew_tolerated(self):
        res = await self.req(
            "GET", self.PRIVATE, init_data=sign_init_data(auth_date=int(time.time()) + 10)
        )
        self.assertEqual(res["status"], 200, "small forward clock skew should still work")

    async def test_recent_auth_date_within_window_accepted(self):
        res = await self.req(
            "GET", self.PRIVATE, init_data=sign_init_data(auth_date=int(time.time()) - 3600)
        )
        self.assertEqual(res["status"], 200, "one-hour-old initData must remain valid")

    async def test_max_age_is_configurable_with_sane_default(self):
        self.assertTrue(hasattr(web, "INIT_DATA_MAX_AGE_SEC"))
        self.assertEqual(web.INIT_DATA_MAX_AGE_SEC, 86400)
        self.assertTrue(hasattr(web, "INIT_DATA_FUTURE_SKEW_SEC"))
        self.assertLessEqual(web.INIT_DATA_FUTURE_SKEW_SEC, 300)
        # Overriding the window must take effect without touching any secret.
        old = web.INIT_DATA_MAX_AGE_SEC
        try:
            web.INIT_DATA_MAX_AGE_SEC = 60
            res = await self.req(
                "GET", self.PRIVATE, init_data=sign_init_data(auth_date=int(time.time()) - 3600)
            )
            self.assertEqual(res["status"], 401)
        finally:
            web.INIT_DATA_MAX_AGE_SEC = old

    async def test_unsigned_user_payload_rejected(self):
        res = await self.req(
            "GET", self.PRIVATE, init_data=urlencode({"user": json.dumps({"id": USER_ID})})
        )
        self.assertEqual(res["status"], 401)

    async def test_query_param_init_data_still_supported(self):
        res = await self.req(
            "GET", self.PRIVATE + "?" + urlencode({"init_data": sign_init_data()})
        )
        self.assertEqual(res["status"], 200)


class AddServiceIdentityTests(WebSecurityCase):
    """Finding 2: POST /api/services must require a verified initData identity."""

    PATH = "/api/services"
    BODY = {"title": "Synthetic listing", "phone": "SYNTHETIC_NOT_A_PHONE", "user_id": OTHER_ID}

    async def test_unauthenticated_post_rejected_with_401(self):
        res = await self.req("POST", self.PATH, body=dict(self.BODY))
        self.assertEqual(res["status"], 401, res["body"])
        self.assertFalse(res["calls"], "no DB write may happen without a verified identity")

    async def test_invalid_signature_post_rejected_with_401(self):
        res = await self.req("POST", self.PATH, init_data="invalid", body=dict(self.BODY))
        self.assertEqual(res["status"], 401)
        self.assertFalse(res["calls"])

    async def test_stale_signature_post_rejected_with_401(self):
        res = await self.req(
            "POST",
            self.PATH,
            init_data=sign_init_data(auth_date=int(time.time()) - YEAR),
            body=dict(self.BODY),
        )
        self.assertEqual(res["status"], 401)
        self.assertFalse(res["calls"])

    async def test_missing_user_id_no_longer_defaults_to_one(self):
        body = {k: v for k, v in self.BODY.items() if k != "user_id"}
        res = await self.req("POST", self.PATH, body=body)
        self.assertEqual(res["status"], 401)
        self.assertFalse(
            [c for c in res["calls"] if c["name"] == "add_service"],
            "unauthenticated post must never fall back to user_id=1",
        )

    async def test_verified_identity_overrides_body_user_id(self):
        res = await self.req("POST", self.PATH, init_data=sign_init_data(), body=dict(self.BODY))
        self.assertEqual(res["status"], 200, res["body"])
        adds = [c for c in res["calls"] if c["name"] == "add_service"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["kwargs"]["user_id"], USER_ID)

    async def test_rate_limit_still_enforced_for_authenticated_posts(self):
        tok = sign_init_data()
        statuses = []
        for _ in range(5):
            res = await self.req("POST", self.PATH, init_data=tok, body=dict(self.BODY))
            statuses.append(res["status"])
        self.assertEqual(statuses[:4], [200, 200, 200, 200], statuses)
        self.assertEqual(statuses[4], 429, statuses)

    async def test_rate_limit_not_bypassed_by_forwarded_for(self):
        tok = sign_init_data()
        for _ in range(4):
            await self.req("POST", self.PATH, init_data=tok, body=dict(self.BODY))
        res = await self.req(
            "POST",
            self.PATH,
            init_data=tok,
            body=dict(self.BODY),
            headers={"X-Forwarded-For": "198.51.100.99"},
        )
        self.assertEqual(res["status"], 429)
        self.assertFalse([c for c in res["calls"] if c["name"] == "add_service"])

    async def test_missing_required_fields_still_400(self):
        res = await self.req(
            "POST", self.PATH, init_data=sign_init_data(), body={"title": "", "phone": ""}
        )
        self.assertEqual(res["status"], 400)


class CopierStatusTests(WebSecurityCase):
    """Finding 3: /api/copier_status is admin-only."""

    PATH = "/api/copier_status"

    async def test_unauthenticated_denied_401_without_debug_payload(self):
        res = await self.req("GET", self.PATH)
        self.assertEqual(res["status"], 401, res["body"])
        raw = json.dumps(res["body"])
        self.assertNotIn("SYNTHETIC_STATUS", raw)
        self.assertNotIn("SYNTHETIC_INTERNAL_ERROR_TEXT", raw)
        self.assertNotIn("4242", raw)

    async def test_non_admin_verified_user_denied_403(self):
        res = await self.req("GET", self.PATH, init_data=sign_init_data(USER_ID))
        self.assertEqual(res["status"], 403, res["body"])
        self.assertNotIn("SYNTHETIC_INTERNAL_ERROR_TEXT", json.dumps(res["body"]))

    async def test_stale_admin_signature_denied(self):
        res = await self.req(
            "GET",
            self.PATH,
            init_data=sign_init_data(ADMIN_ID, auth_date=int(time.time()) - YEAR),
        )
        self.assertIn(res["status"], (401, 403))
        self.assertNotIn("SYNTHETIC_INTERNAL_ERROR_TEXT", json.dumps(res["body"]))

    async def test_verified_admin_gets_debug_payload(self):
        res = await self.req("GET", self.PATH, init_data=sign_init_data(ADMIN_ID))
        self.assertEqual(res["status"], 200, res["body"])
        self.assertEqual(res["body"]["status"], "SYNTHETIC_STATUS")


class CorsPolicyTests(WebSecurityCase):
    """Finding 4: no wildcard CORS on private/authenticated or write responses."""

    async def test_private_authenticated_response_not_wildcard(self):
        res = await self.req(
            "GET",
            "/api/secretary/settings",
            init_data=sign_init_data(),
            headers={"Origin": "https://example.invalid"},
        )
        self.assertEqual(res["status"], 200)
        self.assertNotEqual(res["cors"], "*", "private data must not carry wildcard CORS")

    async def test_private_unauthorized_response_not_wildcard(self):
        res = await self.req("GET", "/api/secretary/settings")
        self.assertEqual(res["status"], 401)
        self.assertNotEqual(res["cors"], "*")

    async def test_write_endpoint_response_not_wildcard(self):
        res = await self.req(
            "POST", "/api/services", init_data=sign_init_data(), body=dict(AddServiceIdentityTests.BODY)
        )
        self.assertEqual(res["status"], 200)
        self.assertNotEqual(res["cors"], "*")

    async def test_copier_status_response_not_wildcard(self):
        res = await self.req("GET", "/api/copier_status", init_data=sign_init_data(ADMIN_ID))
        self.assertNotEqual(res["cors"], "*")

    async def test_football_admin_write_not_wildcard(self):
        res = await self.req(
            "POST",
            "/api/football/streams",
            init_data=sign_init_data(ADMIN_ID),
            body={"title": "Synthetic fixture", "stream_url": "https://example.invalid/offline"},
        )
        self.assertEqual(res["status"], 200)
        self.assertNotEqual(res["cors"], "*")

    async def test_public_get_endpoints_keep_wildcard_and_200(self):
        public = [
            "/ping",
            "/health",
            "/api/rates/history",
            "/api/rates/current",
            "/api/prayer",
            "/api/football/standings",
            "/api/football/matches",
            "/api/football/streams",
            "/api/tv/channels",
            "/api/weather",
            "/api/services",
            "/api/services/101",
        ]
        for path in public:
            with self.subTest(path=path):
                res = await self.req("GET", path)
                self.assertEqual(res["status"], 200, res["body"])
        for path in public:
            if path in ("/ping", "/health"):
                continue  # ping_handler intentionally sends no CORS header
            with self.subTest(path=path, header="cors"):
                res = await self.req("GET", path)
                self.assertEqual(res["cors"], "*", "public read-only GETs stay open to the Mini App")


class PreservedControlsTests(WebSecurityCase):
    """Guard rails: existing controls must not be weakened by this hardening."""

    SECRETARY_ROUTES = [
        ("GET", "/settings"),
        ("POST", "/settings"),
        ("GET", "/logs"),
        ("GET", "/schedules"),
        ("POST", "/schedules"),
        ("POST", "/schedules/reset"),
        ("POST", "/schedules/clear"),
        ("POST", "/schedules/77/toggle"),
        ("DELETE", "/schedules/77"),
        ("POST", "/test_ai"),
    ]

    async def test_ten_secretary_routes_unauthenticated_401(self):
        for method, suffix in self.SECRETARY_ROUTES:
            with self.subTest(route=f"{method} {suffix}"):
                res = await self.req(
                    "POST" if method == "POST" else method,
                    "/api/secretary" + suffix + f"?user_id={OTHER_ID}",
                    body={"user_id": OTHER_ID, "reply_text": "Synthetic"},
                )
                self.assertEqual(res["status"], 401)
                self.assertFalse(res["calls"])

    async def test_secretary_routes_use_verified_identity_not_body_id(self):
        tok = sign_init_data()
        for method, suffix in self.SECRETARY_ROUTES:
            with self.subTest(route=f"{method} {suffix}"):
                _stubs.reset_state()
                res = await self.req(
                    method,
                    "/api/secretary" + suffix + f"?user_id={OTHER_ID}",
                    init_data=tok,
                    body={"user_id": OTHER_ID, "reply_text": "Synthetic", "is_enabled": 1},
                )
                self.assertEqual(res["status"], 200, res["body"])
                for call in res["calls"]:
                    if call["name"] in (
                        "toggle_secretary_schedule",
                        "delete_secretary_schedule",
                    ):
                        observed = call["args"][1]
                    elif call["args"]:
                        observed = call["args"][0]
                    else:
                        observed = call["kwargs"].get("user_id")
                    if observed is not None:
                        self.assertEqual(observed, USER_ID, call)

    async def test_football_admin_writes_denied_403(self):
        body = {
            "title": "Synthetic fixture",
            "stream_url": "https://example.invalid/offline",
            "user_id": ADMIN_ID,
        }
        for label, tok in (("unauth", None), ("nonadmin", sign_init_data(USER_ID))):
            for method, path in (
                ("POST", "/api/football/streams"),
                ("DELETE", "/api/football/streams/77"),
            ):
                with self.subTest(case=label, route=f"{method} {path}"):
                    res = await self.req(method, path, init_data=tok, body=body)
                    self.assertEqual(res["status"], 403)
                    self.assertFalse(res["calls"])

    async def test_football_admin_writes_allowed_for_admin(self):
        body = {"title": "Synthetic fixture", "stream_url": "https://example.invalid/offline"}
        for method, path in (
            ("POST", "/api/football/streams"),
            ("DELETE", "/api/football/streams/77"),
        ):
            with self.subTest(route=f"{method} {path}"):
                res = await self.req(method, path, init_data=sign_init_data(ADMIN_ID), body=body)
                self.assertEqual(res["status"], 200, res["body"])

    async def test_ai_test_rate_limit_429_after_six(self):
        tok = sign_init_data()
        statuses = []
        for _ in range(7):
            res = await self.req(
                "POST", "/api/secretary/test_ai", init_data=tok, body={"message": "Synthetic"}
            )
            statuses.append(res["status"])
        self.assertEqual(statuses, [200] * 6 + [429], statuses)
        other = await self.req(
            "POST",
            "/api/secretary/test_ai",
            init_data=sign_init_data(OTHER_ID),
            body={"message": "Synthetic"},
        )
        self.assertEqual(other["status"], 200, "rate limit is per verified identity")


if __name__ == "__main__":
    unittest.main(verbosity=2)
