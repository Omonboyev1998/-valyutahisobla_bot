'use strict';
// Security regression suite for src/static/webapp.html
//   node tests/frontend/test_webapp_security.cjs
// Pure offline: stub DOM + node:vm, inert payloads, no network, no browser.
const H = require('./harness.cjs');
const { makeContext, makeRunner, PAYLOAD, inlineHandlerExecutes } = H;

const t = makeRunner('webapp.html security suite');
const slices = [];
const slice = (name, fn) => slices.push({ name, fn });

// ===========================================================================
// FINDING 1 — secretary log sender_name / created_at (stored XSS, third party)
// ===========================================================================
slice('finding1-secretary-log', async () => {
  // sender_name is the attacker's own Telegram display name.
  {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      logs: [{ sender_name: PAYLOAD.html, message_text: 'safe', created_at: '2026-01-01 12:00', is_urgent: false }]
    };
    await ctx.c.loadSecretaryLogs();
    const out = ctx.html('secLogsContainer');
    t.ok('log sender_name is HTML-escaped', !out.includes(PAYLOAD.html), out.slice(0, 200));
    t.ok('log sender_name payload appears escaped', out.includes('&lt;img'), out.slice(0, 200));
  }
  // same field, attribute-breakout shape
  {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      logs: [{ sender_name: PAYLOAD.attr, message_text: 'safe', created_at: '2026-01-01 12:00' }]
    };
    await ctx.c.loadSecretaryLogs();
    const out = ctx.html('secLogsContainer');
    t.ok('log sender_name attribute breakout neutralised', !out.includes('<img'), out.slice(0, 200));
  }
  // created_at is sliced to 5 chars but those 5 chars were raw.
  {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      logs: [{ sender_name: 'safe', message_text: 'safe', created_at: '2026-01-01 <img>' }]
    };
    await ctx.c.loadSecretaryLogs();
    const out = ctx.html('secLogsContainer');
    t.ok('log created_at is HTML-escaped', !out.includes('<img'), out.slice(0, 200));
  }
  // REGRESSION: message_text must stay escaped, is_urgent badge must stay.
  {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      logs: [{ sender_name: 'Ali', message_text: PAYLOAD.html, created_at: '2026-01-01 12:34', is_urgent: true }]
    };
    await ctx.c.loadSecretaryLogs();
    const out = ctx.html('secLogsContainer');
    t.ok('REGRESSION log message_text still escaped', !out.includes(PAYLOAD.html) && out.includes('&lt;img'));
    t.ok('REGRESSION urgent badge still rendered', out.includes('[SHOSHILINCH]'));
    t.ok('REGRESSION log time still rendered as HH:MM', out.includes('12:34'), out.slice(0, 300));
    t.ok('REGRESSION log sender name still visible', out.includes('Ali'));
  }
  // REGRESSION: empty-state text and auth header
  {
    const ctx = makeContext();
    ctx.state.response = { success: false, error: 'synthetic unauthorized' };
    await ctx.c.loadSecretaryLogs();
    t.ok('REGRESSION 401 logs degrade to neutral empty state',
      ctx.html('secLogsContainer').includes('hali xabarlarni'));
    t.ok('REGRESSION logs request sends init data header',
      ctx.state.calls.at(-1).options.headers['X-Telegram-Init-Data'] === 'SYNTHETIC_NOT_A_CREDENTIAL');
  }
});

// ===========================================================================
// FINDING 2 — service phone / username break out of href
// ===========================================================================
const SERVICE = {
  id: 1, title: 'safe', master_name: 'safe', category: 'safe', region: 'safe',
  price: 'safe', description: 'safe', phone: '+998901234567', username: 'legit_user'
};

slice('finding2-service-href', async () => {
  for (const field of ['phone', 'username']) {
    const ctx = makeContext();
    ctx.c.fixture = { ...SERVICE, [field]: PAYLOAD.attr };
    ctx.run('cachedServices=[fixture];renderServicesList(cachedServices)');
    const list = ctx.html('servicesContainer');
    t.ok(`service list ${field} attribute breakout neutralised`, !list.includes('<img'), list.slice(0, 250));
    t.ok(`service list ${field} payload not raw`, !list.includes(PAYLOAD.attr));

    ctx.run('openServiceDetail(1)');
    const detail = ctx.html('serviceDetailBody');
    t.ok(`service detail ${field} attribute breakout neutralised`, !detail.includes('<img'), detail.slice(0, 250));
    t.ok(`service detail ${field} payload not raw`, !detail.includes(PAYLOAD.attr));
  }
  // javascript: scheme must not survive in a tel:/t.me href
  {
    const ctx = makeContext();
    ctx.c.fixture = { ...SERVICE, phone: 'javascript:globalThis.__xss=1', username: 'javascript:globalThis.__xss=1' };
    ctx.run('cachedServices=[fixture];renderServicesList(cachedServices)');
    const list = ctx.html('servicesContainer');
    t.ok('service href never yields a bare javascript: scheme', !/href="javascript:/i.test(list), list.slice(0, 250));
  }
  // REGRESSION: benign values still render and still work as links
  {
    const ctx = makeContext();
    ctx.c.fixture = { ...SERVICE, username: '@legit_user' };
    ctx.run('cachedServices=[fixture];renderServicesList(cachedServices)');
    const list = ctx.html('servicesContainer');
    t.ok('REGRESSION benign phone still in tel: href', list.includes('href="tel:+998901234567"'), list.slice(0, 400));
    t.ok('REGRESSION benign username still in t.me href', list.includes('href="https://t.me/legit_user"'), list.slice(0, 600));
    ctx.run('openServiceDetail(1)');
    const detail = ctx.html('serviceDetailBody');
    t.ok('REGRESSION detail benign phone shown', detail.includes('+998901234567'));
    t.ok('REGRESSION detail benign username shown', detail.includes('@legit_user') || detail.includes('(@legit_user)'));
  }
  // REGRESSION: already-correct escaped text fields stay escaped
  {
    for (const field of ['title', 'master_name', 'category', 'region', 'price', 'description']) {
      const ctx = makeContext();
      ctx.c.fixture = { ...SERVICE, [field]: PAYLOAD.html };
      ctx.run('cachedServices=[fixture];renderServicesList(cachedServices)');
      t.ok(`REGRESSION service text ${field} escaped`, !ctx.html('servicesContainer').includes(PAYLOAD.html));
      ctx.run('openServiceDetail(1)');
      t.ok(`REGRESSION service detail text ${field} escaped`, !ctx.html('serviceDetailBody').includes(PAYLOAD.html));
    }
  }
  // rating / rating_count are rendered unescaped numerics today
  {
    for (const field of ['rating', 'rating_count']) {
      const ctx = makeContext();
      ctx.c.fixture = { ...SERVICE, [field]: PAYLOAD.html };
      ctx.run('cachedServices=[fixture];renderServicesList(cachedServices)');
      t.ok(`service ${field} escaped`, !ctx.html('servicesContainer').includes(PAYLOAD.html),
        ctx.html('servicesContainer').slice(0, 200));
    }
  }
});

// ===========================================================================
// FINDING 3 — football stream inline onclick with interpolated id
// ===========================================================================
const STREAM = {
  id: 1, title: 'safe', home_team: 'Home', away_team: 'Away', is_live: 0,
  league: 'League', channel_name: 'Channel', match_time: '12:00', score: '0:0',
  stream_url: 'https://example.invalid/a.m3u8'
};

slice('finding3-football-inline-onclick', async () => {
  // Hostile non-numeric id must not reopen the JS string literal.
  for (const live of [1, 0]) {
    const ctx = makeContext();
    ctx.c.renderFootballStreams([{ ...STREAM, is_live: live, id: PAYLOAD.js }]);
    const containers = ['fbHeroMatchContainer', 'fbLiveMatchesList', 'fbUpcomingList'];
    for (const id of containers) {
      const out = ctx.html(id);
      if (!out) continue;
      const res = inlineHandlerExecutes(ctx, out, 'onclick');
      t.ok(`football id (is_live=${live}) does not execute via ${id} onclick`, !res.executed, res.code);
      t.ok(`football id (is_live=${live}) not interpolated into ${id} onclick`,
        !/onclick="[^"]*openFootballStreamById\('/.test(out), out.slice(0, 300));
    }
  }
  // REGRESSION: clicking the rendered row still opens the right stream.
  {
    const ctx = makeContext();
    ctx.c.renderFootballStreams([
      { ...STREAM, id: 11, is_live: 1, home_team: 'A', away_team: 'B' },
      { ...STREAM, id: 22, is_live: 0, home_team: 'C', away_team: 'D' }
    ]);
    const live = ctx.html('fbLiveMatchesList');
    const up = ctx.html('fbUpcomingList');
    t.ok('REGRESSION live row still has a click route', /data-stream-id|onclick=/.test(live), live.slice(0, 200));
    t.ok('REGRESSION upcoming row still has a click route', /data-stream-id|onclick=/.test(up), up.slice(0, 200));
    t.ok('REGRESSION streams map populated for routing',
      !!(ctx.c.window.footballStreamsMap[11] && ctx.c.window.footballStreamsMap[22]));
    // openFootballStreamById must still resolve by id
    ctx.run('openFootballStreamById(11)');
    t.ok('REGRESSION openFootballStreamById(11) opens player',
      ctx.node('playerStreamTitle').innerText !== '' , ctx.node('playerStreamTitle').innerText);
  }
  // REGRESSION: already-correct escaping on the live path
  for (const field of ['home_team', 'away_team', 'league', 'score', 'channel_name']) {
    const ctx = makeContext();
    ctx.c.renderFootballStreams([{ ...STREAM, is_live: 1, [field]: PAYLOAD.html }]);
    t.ok(`REGRESSION live stream ${field} escaped`,
      !ctx.html('fbLiveMatchesList').includes(PAYLOAD.html) && !ctx.html('fbHeroMatchContainer').includes(PAYLOAD.html));
  }
});

// ===========================================================================
// FINDING 4 — secretary AI test output rendered as raw HTML
// ===========================================================================
slice('finding4-ai-output', async () => {
  {
    const ctx = makeContext();
    ctx.state.response = { success: true, reply: PAYLOAD.html };
    await ctx.c.testSecretaryAiFromModal();
    const out = ctx.html('secAiTestResult');
    t.ok('AI reply is HTML-escaped', !out.includes(PAYLOAD.html), out.slice(0, 200));
    t.ok('AI reply payload shown escaped', out.includes('&lt;img'), out.slice(0, 200));
  }
  {
    const ctx = makeContext();
    ctx.state.response = { success: false, error: PAYLOAD.html };
    await ctx.c.testSecretaryAiFromModal();
    t.ok('AI error is HTML-escaped', !ctx.html('secAiTestResult').includes(PAYLOAD.html));
  }
  {
    const ctx = makeContext();
    ctx.state.rejectFetch = true;
    ctx.state.rejectMessage = PAYLOAD.html;
    await ctx.c.testSecretaryAiFromModal();
    t.ok('AI exception message is HTML-escaped', !ctx.html('secAiTestResult').includes(PAYLOAD.html));
  }
  // REGRESSION: newline -> <br> formatting of the reply must survive.
  {
    const ctx = makeContext();
    ctx.state.response = { success: true, reply: 'line one\nline two' };
    await ctx.c.testSecretaryAiFromModal();
    const out = ctx.html('secAiTestResult');
    t.ok('REGRESSION AI reply keeps <br> line breaks', out.includes('line one<br>line two'), out.slice(0, 200));
    t.ok('REGRESSION AI reply keeps its heading', out.includes('AI Javobi'));
    t.ok('REGRESSION test_ai request sends init data header',
      ctx.state.calls.at(-1).options.headers['X-Telegram-Init-Data'] === 'SYNTHETIC_NOT_A_CREDENTIAL');
  }
});

// ===========================================================================
// FINDING 5 — secretary schedule start_time / end_time raw
// ===========================================================================
slice('finding5-schedule-times', async () => {
  for (const field of ['start_time', 'end_time']) {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      schedules: [{ id: 1, title: 'safe', reply_text: 'safe', start_time: '09:00', end_time: '18:00', is_active: 1, [field]: PAYLOAD.html }]
    };
    await ctx.c.loadSecretarySchedules();
    t.ok(`schedule ${field} is HTML-escaped`, !ctx.html('secSchedulesList').includes(PAYLOAD.html),
      ctx.html('secSchedulesList').slice(0, 200));
  }
  // REGRESSION: layout, title/reply escaping, id-based buttons, empty state
  {
    const ctx = makeContext();
    ctx.state.response = {
      success: true,
      schedules: [{ id: 7, title: PAYLOAD.html, reply_text: PAYLOAD.html, start_time: '09:00', end_time: '18:00', is_active: 1 }]
    };
    await ctx.c.loadSecretarySchedules();
    const out = ctx.html('secSchedulesList');
    t.ok('REGRESSION schedule title still escaped', !out.includes(PAYLOAD.html) && out.includes('&lt;img'));
    t.ok('REGRESSION schedule time range still rendered', out.includes('09:00 - 18:00'), out.slice(0, 400));
    t.ok('REGRESSION schedule toggle uses numeric id', out.includes('toggleSecretarySchedule(7)'));
    t.ok('REGRESSION schedule delete uses numeric id', out.includes('deleteSecretarySchedule(7)'));
    t.ok('REGRESSION active schedule still shows green marker', out.includes('🟢'));
  }
  {
    const ctx = makeContext();
    ctx.state.response = { success: false, error: 'synthetic unauthorized' };
    await ctx.c.loadSecretarySchedules();
    t.ok('REGRESSION 401 schedules degrade to neutral empty state',
      ctx.html('secSchedulesList').includes('Hozircha vaqt'));
  }
});

// ===========================================================================
// FINDING 6 — other upstream-fed sinks (matches, standings, weather, player)
// ===========================================================================
slice('finding6a-matches-standings-weather', async () => {
  for (const field of ['league', 'status', 'score', 'home_logo', 'away_logo']) {
    const ctx = makeContext();
    ctx.state.response = {
      league: field === 'league' ? PAYLOAD.html : 'Liga',
      matches: [{ home_team: 'A', away_team: 'B', status: 'Tugagan', score: '1:0',
        home_logo: 'https://e.invalid/a.png', away_logo: 'https://e.invalid/b.png',
        [field]: field.endsWith('logo') ? PAYLOAD.attr : PAYLOAD.html }]
    };
    await ctx.c.loadFootballMatches('eng.1');
    const out = ctx.html('fbMatchesList');
    t.ok(`match ${field} neutralised`, !out.includes(PAYLOAD.html) && !out.includes('<img src=data:'), out.slice(0, 200));
  }
  for (const field of ['name', 'logo', 'played', 'diff', 'points']) {
    const ctx = makeContext();
    ctx.state.response = {
      standings: [{ name: 'Klub', logo: 'https://e.invalid/l.png', played: 1, diff: 0, points: 3,
        [field]: field === 'logo' ? PAYLOAD.attr : PAYLOAD.html }]
    };
    await ctx.c.loadFootballData('eng.1');
    const out = ctx.html('fbTableBody');
    t.ok(`standings ${field} neutralised`, !out.includes(PAYLOAD.html) && !out.includes('<img src=data:'), out.slice(0, 200));
  }
  for (const field of ['date', 'emoji', 'desc', 'max', 'min']) {
    const ctx = makeContext();
    ctx.state.response = { forecast: [{ date: 'Du', emoji: '☀️', desc: 'ochiq', max: 20, min: 10, [field]: PAYLOAD.html }] };
    await ctx.c.loadWeatherData();
    t.ok(`forecast ${field} neutralised`, !ctx.html('wForecastList').includes(PAYLOAD.html),
      ctx.html('wForecastList').slice(0, 200));
  }
  // REGRESSION: benign upstream data still renders with its content
  {
    const ctx = makeContext();
    ctx.state.response = {
      league: 'Premier League',
      matches: [{ home_team: 'Arsenal', away_team: 'Chelsea', status: 'Tugagan', score: '2:1',
        home_logo: 'https://cdn.invalid/ars.png', away_logo: 'https://cdn.invalid/che.png' }]
    };
    await ctx.c.loadFootballMatches('eng.1');
    const out = ctx.html('fbMatchesList');
    t.ok('REGRESSION match teams + score rendered', out.includes('Arsenal') && out.includes('Chelsea') && out.includes('2:1'));
    t.ok('REGRESSION match logos kept as https src', out.includes('src="https://cdn.invalid/ars.png"'), out.slice(0, 500));
    t.ok('REGRESSION league name rendered', out.includes('Premier League'));
  }
  {
    const ctx = makeContext();
    ctx.state.response = { standings: [{ name: 'Arsenal', logo: 'https://cdn.invalid/ars.png', played: 10, diff: 7, points: 24 }] };
    await ctx.c.loadFootballData('eng.1');
    const out = ctx.html('fbTableBody');
    t.ok('REGRESSION standings row rendered', out.includes('Arsenal') && out.includes('>24<'), out.slice(0, 400));
    t.ok('REGRESSION standings logo kept as https src', out.includes('src="https://cdn.invalid/ars.png"'));
  }
  {
    const ctx = makeContext();
    ctx.state.response = { temp: 21, desc: 'ochiq', emoji: '☀️', apparent_temp: 22, humidity: 40, wind_speed: 2,
      location_name: 'Toshkent', forecast: [{ date: 'Du', emoji: '☀️', desc: 'ochiq', max: 25, min: 12 }] };
    await ctx.c.loadWeatherData();
    const out = ctx.html('wForecastList');
    t.ok('REGRESSION forecast row rendered', out.includes('Du') && out.includes('ochiq') && out.includes('+25'), out.slice(0, 300));
  }
});

slice('finding6b-player-fallback-handlers', async () => {
  // openFootballStream fallback branch: title / channel / startTime
  for (const field of ['title', 'channel', 'startTime']) {
    const ctx = makeContext();
    const args = [1, '', 'Match', 'Channel', 0, 'vs', '12:00'];
    args[{ title: 2, channel: 3, startTime: 6 }[field]] = PAYLOAD.html;
    ctx.c.openFootballStream(...args);
    const out = ctx.html('streamPlayerBox');
    t.ok(`player fallback ${field} neutralised`, !out.includes(PAYLOAD.html), out.slice(0, 200));
  }
  // JS-literal breakout through the inline handlers in that fallback
  for (const field of ['title', 'channel']) {
    const ctx = makeContext();
    const args = [1, '', 'Match', 'Channel', 0, 'vs', '12:00'];
    args[{ title: 2, channel: 3 }[field]] = PAYLOAD.js;
    ctx.c.openFootballStream(...args);
    const res = inlineHandlerExecutes(ctx, ctx.html('streamPlayerBox'), 'onclick');
    t.ok(`player fallback ${field} inline handler does not execute injection`, !res.executed, res.code);
  }
  // showChannelFallbackUI: title/desc text + the three openExternalUrl handlers
  {
    const ctx = makeContext();
    ctx.c.showChannelFallbackUI(PAYLOAD.html, 'noncatalog', 'https://example.invalid/a.m3u8');
    t.ok('HLS fallback title neutralised', !ctx.html('streamPlayerBox').includes(PAYLOAD.html),
      ctx.html('streamPlayerBox').slice(0, 200));
  }
  {
    const ctx = makeContext();
    ctx.c.showChannelFallbackUI('safe', 'noncatalog', "https://example.invalid/a.m3u8" + PAYLOAD.js);
    const res = inlineHandlerExecutes(ctx, ctx.html('streamPlayerBox'), 'onclick');
    t.ok('HLS fallback URL inline handler does not execute injection', !res.executed, res.code);
  }
  {
    const ctx = makeContext();
    ctx.c.showChannelFallbackUI('safe', 'noncatalog', PAYLOAD.jsUrl);
    const out = ctx.html('streamPlayerBox');
    t.ok('HLS fallback never emits a javascript: url in a handler', !/javascript:/i.test(out), out.slice(0, 400));
  }
  // REGRESSION: the fallback UI still offers its three real links
  {
    const ctx = makeContext();
    ctx.c.showChannelFallbackUI("Zo'r TV", "zo'r tv", 'https://example.invalid/a.m3u8');
    const out = ctx.html('streamPlayerBox');
    t.ok('REGRESSION fallback shows official site button', out.includes('Rasmiy Sahifasida'), out.slice(0, 300));
    t.ok('REGRESSION fallback shows youtube button for catalog channel', out.includes('YouTube Jonli Efiri'));
    t.ok('REGRESSION fallback shows famelack portal button', out.includes('Famelack TV Portali'));
    t.ok('REGRESSION fallback shows channel title', out.includes('Zo') , out.slice(0, 300));
  }
});

// ===========================================================================
// FINDING 7 — URL sinks gated only by substring checks
// ===========================================================================
slice('finding7-url-scheme-validation', async () => {
  // iframe src (famelack branch and embed branch)
  for (const url of [PAYLOAD.jsUrlFamelack, PAYLOAD.jsUrl]) {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, url, 'T', 'C', 1, 'vs', 'now');
    const box = ctx.node('streamPlayerBox');
    const srcs = box.children.map((e) => e.src).filter(Boolean);
    t.ok(`iframe/video src rejects ${url.slice(0, 24)}`,
      !srcs.some((s) => /^\s*javascript:/i.test(s)), JSON.stringify(srcs));
    t.ok(`rendered html has no javascript: url for ${url.slice(0, 24)}`,
      !/javascript:/i.test(ctx.html('streamPlayerBox')));
  }
  // video src (m3u8 branch)
  {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, PAYLOAD.jsUrlM3u8, 'T', 'C', 1, 'vs', 'now');
    const srcs = ctx.node('streamPlayerBox').children.map((e) => e.src).filter(Boolean);
    t.ok('video src rejects javascript: m3u8 lookalike',
      !srcs.some((s) => /^\s*javascript:/i.test(s)), JSON.stringify(srcs));
  }
  // data: URL must be rejected too
  {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, PAYLOAD.dataUrl + '#embed', 'T', 'C', 1, 'vs', 'now');
    const srcs = ctx.node('streamPlayerBox').children.map((e) => e.src).filter(Boolean);
    t.ok('iframe src rejects data: url', !srcs.some((s) => /^\s*data:/i.test(s)), JSON.stringify(srcs));
  }
  // window.open / tg.openLink via openStreamInNewTab
  {
    const ctx = makeContext();
    ctx.run(`currentActiveStreamUrl = ${JSON.stringify(PAYLOAD.jsUrl)};`);
    ctx.c.openStreamInNewTab();
    const all = ctx.state.opened.concat(ctx.state.links);
    t.ok('openStreamInNewTab never passes a javascript: url',
      !all.some((u) => /^\s*javascript:/i.test(u)), JSON.stringify(all));
  }
  // openExternalUrl directly
  {
    const ctx = makeContext();
    ctx.c.openExternalUrl(PAYLOAD.jsUrl);
    ctx.c.openExternalUrl(PAYLOAD.dataUrl);
    const all = ctx.state.opened.concat(ctx.state.links);
    t.ok('openExternalUrl rejects javascript:/data: urls',
      !all.some((u) => /^\s*(javascript|data):/i.test(u)), JSON.stringify(all));
  }
  // openChannelStream window.open branch (famelack)
  {
    const ctx = makeContext();
    ctx.c.openChannelStream('Ch', PAYLOAD.jsUrlFamelack, 'Telekanal');
    const all = ctx.state.opened.concat(ctx.state.links);
    t.ok('openChannelStream rejects javascript: famelack lookalike',
      !all.some((u) => /^\s*javascript:/i.test(u)), JSON.stringify(all));
  }
  // REGRESSION: real http(s) URLs still flow through every path
  {
    const ctx = makeContext();
    ctx.c.openExternalUrl('https://example.invalid/page');
    t.ok('REGRESSION openExternalUrl passes https url',
      ctx.state.links.includes('https://example.invalid/page') || ctx.state.opened.includes('https://example.invalid/page'));
  }
  {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, 'https://famelack.com/tv/uz', 'T', 'C', 1, 'vs', 'now');
    const srcs = ctx.node('streamPlayerBox').children.map((e) => e.src).filter(Boolean);
    t.ok('REGRESSION famelack iframe still gets its https src', srcs.includes('https://famelack.com/tv/uz'), JSON.stringify(srcs));
  }
  {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, 'https://example.invalid/live.m3u8', 'T', 'C', 1, 'vs', 'now');
    const srcs = ctx.node('streamPlayerBox').children.map((e) => e.src).filter(Boolean);
    t.ok('REGRESSION m3u8 video still gets its https src', srcs.includes('https://example.invalid/live.m3u8'), JSON.stringify(srcs));
  }
  {
    const ctx = makeContext();
    ctx.c.openFootballStream(1, 'https://www.youtube.com/watch?v=abc123', 'T', 'C', 1, 'vs', 'now');
    const srcs = ctx.node('streamPlayerBox').children.map((e) => e.src).filter(Boolean);
    t.ok('REGRESSION youtube watch url still converted to embed',
      srcs.some((s) => s.startsWith('https://www.youtube.com/embed/abc123')), JSON.stringify(srcs));
  }
  {
    const ctx = makeContext();
    ctx.run('currentActiveStreamUrl = "https://example.invalid/live.m3u8";');
    ctx.c.openStreamInNewTab();
    const all = ctx.state.opened.concat(ctx.state.links);
    t.ok('REGRESSION openStreamInNewTab passes https url', all.includes('https://example.invalid/live.m3u8'), JSON.stringify(all));
  }
  // safeUrl unit behaviour
  {
    const ctx = makeContext();
    const su = ctx.c.safeUrl;
    t.ok('safeUrl allows http', su('http://a.invalid/x') === 'http://a.invalid/x');
    t.ok('safeUrl allows https', su('https://a.invalid/x') === 'https://a.invalid/x');
    t.ok('safeUrl rejects javascript', su('javascript:alert(1)') === '');
    t.ok('safeUrl rejects JaVaScRiPt mixed case', su('JaVaScRiPt:alert(1)') === '');
    t.ok('safeUrl rejects whitespace-padded javascript', su('  javascript:alert(1)') === '');
    t.ok('safeUrl rejects embedded-control-char javascript', su('java\u0000script:alert(1)') === '',
      JSON.stringify(su('java\u0000script:alert(1)')));
    t.ok('safeUrl rejects tab-split javascript', su('java\tscript:alert(1)') === '', JSON.stringify(su('java\tscript:alert(1)')));
    t.ok('safeUrl rejects data', su('data:text/html,x') === '');
    t.ok('safeUrl rejects vbscript', su('vbscript:x') === '');
    t.ok('safeUrl rejects blob', su('blob:https://a.invalid/x') === '');
    t.ok('safeUrl rejects protocol-relative', su('//evil.invalid/x') === '');
    t.ok('safeUrl keeps relative path', su('/local/path.png') === '/local/path.png');
    t.ok('safeUrl honours fallback', su('javascript:x', 'https://fb.invalid/i.png') === 'https://fb.invalid/i.png');
  }
});

// ===========================================================================
// FINDING 8 — submitNewStream must send admin auth headers
// ===========================================================================
slice('finding8-stream-post-auth', async () => {
  const ctx = makeContext();
  ctx.state.response = { success: true };
  await ctx.c.submitNewStream({ preventDefault() {} });
  const req = ctx.state.calls.find((c) => c.url === '/api/football/streams' && (c.options.method || 'GET') === 'POST');
  t.ok('submitNewStream posts to /api/football/streams', !!req, JSON.stringify(ctx.state.calls.map((c) => c.url)));
  t.ok('submitNewStream sends X-Telegram-Init-Data',
    req.options.headers['X-Telegram-Init-Data'] === 'SYNTHETIC_NOT_A_CREDENTIAL', JSON.stringify(req.options.headers));
  t.ok('submitNewStream keeps JSON content type',
    req.options.headers['Content-Type'] === 'application/json');
  t.ok('submitNewStream still sends a JSON body', typeof req.options.body === 'string' && req.options.body.includes('stream_url'));
});

// ===========================================================================
// GLOBAL REGRESSIONS — auth helper, TV catalog, all protected calls
// ===========================================================================
slice('global-regressions', async () => {
  {
    const ctx = makeContext();
    const extra = { 'Content-Type': 'application/json' };
    const h = ctx.c.getAuthHeaders(extra);
    t.ok('REGRESSION getAuthHeaders preserves content type', h['Content-Type'] === 'application/json');
    t.ok('REGRESSION getAuthHeaders copies initData', h['X-Telegram-Init-Data'] === 'SYNTHETIC_NOT_A_CREDENTIAL');
    t.ok('REGRESSION getAuthHeaders does not mutate extras', !extra['X-Telegram-Init-Data']);
    ctx.c.Telegram.WebApp.initData = '';
    t.ok('REGRESSION no fabricated auth header without initData', !ctx.c.getAuthHeaders()['X-Telegram-Init-Data']);
  }
  // TV catalog: constant data, index-based routing, escaped labels
  {
    const ctx = makeContext();
    ctx.run('currentTvMode="uz";currentTvFilter="all";tvSearchQuery="";renderTvChannels()');
    const out = ctx.html('channelsCatalogGrid');
    t.ok('REGRESSION TV catalog uses numeric index onclick',
      /onclick="openFilteredTvChannelByIndex\(\d+\)"/.test(out), out.slice(0, 300));
    t.ok('REGRESSION TV catalog does not inline channel names in handlers',
      !out.includes('onclick="openChannelStream'));
    t.ok('REGRESSION TV catalog renders channel names', out.includes('channel-name'));
  }
  // all 11 protected secretary/service calls still carry the header
  {
    const ctx = makeContext();
    ctx.state.response = { success: false, error: 'synthetic unauthorized' };
    ctx.state.calls.length = 0;
    await ctx.c.submitNewService({ preventDefault() {} });
    await ctx.c.loadSecretarySettings();
    await ctx.c.saveSecretarySettings();
    await ctx.c.testSecretaryAiFromModal();
    await ctx.c.loadSecretarySchedules();
    await ctx.c.saveNewSecretarySchedule();
    await ctx.c.toggleSecretarySchedule(1);
    await ctx.c.deleteSecretarySchedule(1);
    await ctx.c.clearAllSecretarySchedules();
    await ctx.c.resetSecretarySchedules();
    await ctx.c.loadSecretaryLogs();
    t.ok('REGRESSION 11 protected calls exercised', ctx.state.calls.length === 11, String(ctx.state.calls.length));
    for (const req of ctx.state.calls) {
      t.ok(`REGRESSION auth header on ${(req.options.method || 'GET')} ${req.url}`,
        req.options.headers && req.options.headers['X-Telegram-Init-Data'] === 'SYNTHETIC_NOT_A_CREDENTIAL');
    }
  }
  // escapeHtml itself
  {
    const ctx = makeContext();
    const e = ctx.c.escapeHtml;
    t.ok('REGRESSION escapeHtml covers & < > " \'',
      e('&<>"\'') === '&amp;&lt;&gt;&quot;&#039;', e('&<>"\''));
    t.ok('REGRESSION escapeHtml stringifies numbers', e(5) === '5');
    t.ok('REGRESSION escapeHtml maps falsy to empty string', e(null) === '' && e(undefined) === '' && e('') === '');
  }
  // no inline on* handler anywhere in rendered output carries interpolated quotes
  {
    const html = H.readHtml();
    t.ok('no remaining openFootballStreamById string interpolation',
      !/openFootballStreamById\('\$\{/.test(html));
    t.ok('no remaining openExternalUrl string interpolation',
      !/openExternalUrl\('\$\{/.test(html));
    t.ok('no remaining openExternalChannel string interpolation',
      !/openExternalChannel\('\$\{/.test(html));
    t.ok('no remaining openCustomStreamForMatch string interpolation',
      !/openCustomStreamForMatch\('\$\{/.test(html));
  }
});

// ===========================================================================
(async () => {
  for (const s of slices) {
    try { await s.fn(); }
    catch (e) { t.ok(s.name + ' threw', false, e && e.message); }
  }
  const r = t.report();
  console.log(`\nTOTAL ${r.passed}/${r.total} passed, ${r.failed} failed`);
  process.exitCode = r.failed ? 1 : 0;
})();
