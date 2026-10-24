'use strict';
// Offline stub-DOM harness for src/static/webapp.html.
// No browser, no network, no packages. The real inline <script> is extracted
// from the page and evaluated in a node:vm context with a minimal DOM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const WEBAPP = path.join(REPO_ROOT, 'src/static/webapp.html');

function readHtml() {
  return fs.readFileSync(WEBAPP, 'utf8');
}

function extractInlineScript(html) {
  const m = html.match(/<script>\s*([\s\S]*?)<\/script>/);
  if (!m) throw new Error('inline <script> block not found in webapp.html');
  return m[1];
}

function element(tag) {
  return {
    tag: tag || 'div',
    innerHTML: '',
    innerText: '',
    value: 'test',
    checked: false,
    style: {},
    children: [],
    attrs: {},
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    appendChild(e) { this.children.push(e); return e; },
    setAttribute(k, v) { this.attrs[k] = v; this[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    canPlayType() { return ''; },
    reset() {},
    focus() {},
    addEventListener() {},
    removeEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return null; }
  };
}

// Fresh isolated context per test slice so state never leaks between cases.
function makeContext() {
  const nodes = new Map();
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, element());
    return nodes.get(id);
  };
  const state = {
    calls: [],      // every fetch({url, options})
    opened: [],     // every window.open(url)
    links: [],      // every Telegram WebApp openLink(url)
    alerts: [],
    response: {},   // next fetch JSON body
    rejectFetch: false,
    rejectMessage: 'synthetic network failure'
  };

  const c = vm.createContext({
    console: { log() {}, error() {}, warn() {}, info() {} },
    document: {
      getElementById: node,
      querySelectorAll() { return []; },
      querySelector() { return null; },
      createElement(tag) { return element(tag); },
      addEventListener() {},
      body: element('body')
    },
    setInterval() {}, setTimeout() {}, clearTimeout() {}, clearInterval() {},
    alert(m) { state.alerts.push(String(m)); },
    confirm() { return true; },
    prompt() { return 'synthetic question'; },
    encodeURIComponent,
    decodeURIComponent,
    JSON, Math, Date, String, Number, Object, Array, Boolean, parseFloat, parseInt, isNaN,
    fetch: async (url, options = {}) => {
      state.calls.push({ url, options });
      if (state.rejectFetch) throw new Error(state.rejectMessage);
      const failed = state.response && state.response.success === false;
      return {
        ok: !failed,
        status: failed ? 401 : 200,
        json: async () => state.response
      };
    }
  });
  c.window = c;
  c.globalThis = c;
  c.addEventListener = () => {};
  c.removeEventListener = () => {};
  c.scrollTo = () => {};
  c.open = (url) => { state.opened.push(url); return null; };
  c.Telegram = {
    WebApp: {
      initData: 'SYNTHETIC_NOT_A_CREDENTIAL',
      initDataUnsafe: { user: { id: 123 } },
      ready() {}, expand() {},
      setHeaderColor() {}, setBackgroundColor() {},
      openLink(u) { state.links.push(u); },
      HapticFeedback: { impactOccurred() {}, notificationOccurred() {} },
      BackButton: { onClick() {}, show() {}, hide() {} }
    }
  };

  const source = extractInlineScript(readHtml());
  vm.runInContext(source, c, { timeout: 5000, filename: 'webapp-inline.js' });

  return {
    c,
    node,
    state,
    html: (id) => node(id).innerHTML,
    run: (code) => vm.runInContext(code, c, { timeout: 5000 })
  };
}

// --- tiny assertion runner -------------------------------------------------
function makeRunner(label) {
  const results = [];
  const api = {
    ok(name, cond, detail) {
      results.push({ name, passed: !!cond, detail: detail === undefined ? '' : String(detail).slice(0, 400) });
    },
    get results() { return results; },
    report() {
      const failed = results.filter((r) => !r.passed);
      console.log(`\n${label}: ${results.length - failed.length}/${results.length} passed`);
      for (const f of failed) console.log(`  FAIL  ${f.name}${f.detail ? ' :: ' + f.detail : ''}`);
      return { total: results.length, passed: results.length - failed.length, failed: failed.length, failures: failed };
    }
  };
  return api;
}

// Inert payloads: no network, no exfiltration, only a context-local flag.
const PAYLOAD = {
  // text/HTML context
  html: '<img src=data:, onerror="globalThis.__xss=1">',
  // attribute breakout
  attr: '"><img src=data:, onerror="globalThis.__xss=1">',
  // JS-string-literal breakout inside an inline handler attribute
  js: "');globalThis.__xss=1;//",
  // dangerous URL schemes
  jsUrl: 'javascript:globalThis.__xss=1;//embed',
  jsUrlFamelack: 'javascript:globalThis.__xss=1;//famelack.com',
  jsUrlM3u8: 'javascript:globalThis.__xss=1;//a.m3u8',
  dataUrl: 'data:text/html,<script>globalThis.__xss=1</script>'
};

// Decode an HTML attribute value the way a browser does before the JS parser runs.
function htmlAttrDecode(s) {
  return String(s)
    .replace(/&#0*39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&#0*34;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

// Does an inline on* handler extracted from rendered HTML execute injected code?
function inlineHandlerExecutes(ctx, renderedHtml, attr) {
  const re = new RegExp(attr + '="([^"]*)"', 'g');
  let m;
  while ((m = re.exec(renderedHtml))) {
    const code = htmlAttrDecode(m[1]);
    ctx.c.__xss = 0;
    try { ctx.run(code); } catch (e) { /* a syntax error means no injection */ }
    if (ctx.c.__xss === 1) return { executed: true, code };
  }
  return { executed: false, code: null };
}

module.exports = {
  REPO_ROOT, WEBAPP, readHtml, extractInlineScript,
  makeContext, makeRunner, element, PAYLOAD, htmlAttrDecode, inlineHandlerExecutes
};
