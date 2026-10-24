# Frontend security fix evidence — `src/static/webapp.html`

Branch `work/security-hardening`, base commit `8a3da42`.
Baseline sha256 `41406f8aa49c493d22fcdbe48bf8f29d57536afdfa60d3fa573c9962c1a58480`
Fixed sha256 `caa0260f7b6ab2ff5f9852fd28c23cb4e95452c96441154e6ecc04338c3d6c11`

## Run the suite

```
cd <repo root>
node tests/frontend/test_webapp_security.cjs
```

163/163 assertions pass. Exit code 0 on success, 1 on any failure.

The harness (`harness.cjs`) extracts the page's real inline `<script>` and evaluates it in a
`node:vm` context with a stub DOM — no browser, no network, no packages. Each test slice gets a
fresh context so state never leaks. Payloads are inert (`globalThis.__xss = 1`, never a network
call or exfiltration).

## Fixes, by finding

| # | Sink | Fix |
|---|------|-----|
| 1 | secretary log `sender_name`, `created_at` | `escapeHtml()`; `created_at` coerced with `String(...)` before `.slice()` |
| 2 | service `phone` / `username` in `href` | new `safePhone()` / `safeUsername()` allowlists + `escapeHtml()` in the attribute; `rating`/`rating_count` also escaped |
| 3 | `openFootballStreamById('${escapeHtml(x.id)}')` | replaced with `openFootballStreamByIndex(N)` — a numeric index into `window._footballStreamList`, mirroring the already-correct TV-catalog pattern. No attacker data in a JS-in-attribute context. |
| 4 | AI `reply` / `error` / `err.message` | `escapeHtml()` before the `\n`→`<br>` transform, so formatting survives but markup does not |
| 5 | schedule `start_time` / `end_time` | `escapeHtml()`; schedule ids coerced with `Number()` in the inline handlers |
| 6 | matches, standings, weather forecast, stream `match_time`/`channel_name`, player + HLS fallback text, logo URLs | `escapeHtml()` for text; `escapeHtml(safeUrl(...))` for every logo `src`; the three `openExternalUrl('${url}')` buttons became `openFallbackUrlByIndex(0..2)` over `window._fallbackUrls`; `openExternalChannel('${channel}')` and `openCustomStreamForMatch('${title}')` became `openCurrentFallbackChannel()` / `openCustomStreamForCurrentMatch()` reading `window._currentStreamContext` |
| 7 | `iframe.src`, `videoEl.src`, `window.open`, `tg.openLink` | new `safeUrl(url, fallback)` — parses the scheme after stripping control characters and accepts **only** `http`/`https`; rejects `javascript:`, `data:`, `blob:`, `vbscript:`, protocol-relative `//host`, and control-char-obfuscated variants. The substring gates (`includes('embed')`, `includes('famelack.com')`, `.m3u8`) remain for *routing* but no longer decide safety. |
| 8 | `submitNewStream` had no auth header | `headers: getAuthHeaders({ 'Content-Type': 'application/json' })` |

## Could not be fixed in this file

- **No Content-Security-Policy.** A `<meta http-equiv="Content-Security-Policy">` would be a
  behavioural change to a page that relies on inline `<script>`, inline `on*` handlers and inline
  `style` attributes throughout its static markup; adding one without `unsafe-inline` would break
  the page, and with `unsafe-inline` it buys almost nothing against these sinks. A real CSP needs a
  response header from `src/web.py` plus removal of inline handlers — out of this task's scope and
  another agent owns the backend.
- **CDN scripts without SRI** (`telegram-web-app.js`, `chart.js`, `hls.js@latest`). Correct
  `integrity` hashes cannot be computed offline, and `hls.js@latest` is version-floating so a pinned
  hash would need a pinned version first. Left unchanged rather than guessed.
- **`Access-Control-Allow-Origin: *` on the API.** Backend-only (`src/web.py`).

## Re-running the original audit harness against the fixed file

The prior audit asserted *current unsafe behaviour*, so a fixed page must fail those assertions.
Its `check()` throws on first failure, so a soft-failing copy (`test_frontend_soft.cjs`, identical
except assertions are recorded instead of thrown) was used to enumerate all of them:

- **28 / 72 still pass** — exactly the "already correct" set: the six escaped service text fields,
  escaped log `message_text`, TV index-based onclick, `getAuthHeaders` semantics, all 11 protected
  secretary/service calls sending `X-Telegram-Init-Data`, both 401 empty-state degradations.
- **44 / 72 now fail *because the vulnerability is gone*** — every "raw HTML", "attribute breakout",
  "inline handler executes", "unvalidated iframe/window.open URL" assertion, plus
  `BUG stream POST missing auth header`.

No commit, push, deploy, or bot start was performed. No `.py` file was modified by this work.
