/* Exercise the real public worker and gallery handlers; no host or private data. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'KCMC-Connect-Phase6-Recreated');
const BASE = '61c70f590735522adbfd6be02dab6888924a54fd';
const PINS = {
  'public-presentation.js': '5dfe8c3dc99e5c8771f383157cdfc1f3def1f4e72810094a16e6203dbaf4c150',
  'sw.js': '11091e96760a045f952650a8e720ed02607307cb87173f5978cd9f246c6fdfd0',
};
function baseline(name) {
  const content = process.env.KCMC_PHOTO_BASELINE_DIR
    ? fs.readFileSync(path.join(process.env.KCMC_PHOTO_BASELINE_DIR, name))
    : cp.execFileSync('git', ['show', BASE + ':KCMC-Connect-Phase6-Recreated/' + name], {cwd: ROOT});
  assert.equal(crypto.createHash('sha256').update(content).digest('hex'), PINS[name], 'stale negative-control source remains pinned');
  return content.toString();
}
function check(label, fn) { fn(); console.log('PASS:', label); }
function target() {
  const handlers = new Map();
  return {handlers, addEventListener(name, fn) { handlers.set(name, fn); }, fire(name, event = {}) { handlers.get(name)?.(event); }};
}
function gallery(source, states = Array.from({length: 9}, () => ({complete: true, naturalWidth: 20})), reduced = false) {
  const photos = states.map((state, i) => ({...state, hidden: i !== 0, alt: 'Synthetic public photo ' + (i + 1), classList: {toggle() {}}}));
  const controls = {hidden: true}, status = {textContent: ''}, toggle = {...target(), textContent: ''};
  const previous = target(), next = target(), root = target(), doc = target(), win = target(), motion = {...target(), matches: reduced};
  let active = true, timerId = 0;
  const timers = new Map();
  root.querySelectorAll = () => photos;
  root.querySelector = selector => ({'[data-hero-controls]': controls, '[data-hero-status]': status, '[data-hero-toggle]': toggle, '[data-hero-previous]': previous, '[data-hero-next]': next}[selector] || null);
  root.closest = () => ({classList: {contains: () => active}});
  doc.hidden = false;
  doc.getElementById = () => null;
  doc.querySelector = selector => selector === '[data-hero-gallery]' ? root : null;
  win.matchMedia = () => motion;
  const sandbox = {document: doc, window: win, setTimeout(fn, delay) { const id = ++timerId; timers.set(id, {fn, delay}); return id; }, clearTimeout(id) { timers.delete(id); }};
  vm.runInNewContext(source, sandbox, {timeout: 1000});
  return {photos, controls, status, toggle, previous, next, root, doc, win, motion, timers, setActive(value) { active = value; }, current() { return photos.findIndex(photo => !photo.hidden); }, tick() { const [id, timer] = timers.entries().next().value; timers.delete(id); timer.fn(); }};
}
const staleJS = baseline('public-presentation.js');
const repairedJS = fs.readFileSync(path.join(APP, 'public-presentation.js'), 'utf8');
const states = Array.from({length: 9}, (_, i) => ({complete: true, naturalWidth: i === 3 ? 0 : 20}));
check('stale gallery reproduces the missing fourth-frame freeze', () => {
  const g = gallery(staleJS, states); g.next.fire('click'); g.next.fire('click'); g.next.fire('click');
  assert.equal(g.current(), 2); g.next.fire('click'); assert.equal(g.current(), 2);
});
check('Next skips a broken frame and Previous scans backward', () => {
  const g = gallery(repairedJS, states); g.next.fire('click'); g.next.fire('click'); g.next.fire('click');
  assert.equal(g.current(), 4); assert.equal(g.status.textContent, 'Photo 5 of 9. Synthetic public photo 5');
  g.previous.fire('click'); assert.equal(g.current(), 2);
  assert.equal(g.photos.filter(photo => !photo.hidden).length, 1); assert.equal(g.timers.size, 0);
  assert.equal(g.toggle.textContent, 'Play photos');
});
check('pending frames are skipped and become eligible after loading', () => {
  const g = gallery(repairedJS, states.map((state, i) => ({...state, complete: i !== 3})));
  g.next.fire('click'); g.next.fire('click'); g.next.fire('click'); assert.equal(g.current(), 4);
  g.photos[3].complete = true; g.photos[3].naturalWidth = 20;
  g.previous.fire('click'); assert.equal(g.current(), 3);
});
check('automatic advance keeps the seven-minute delay and skips missing frames', () => {
  const g = gallery(repairedJS, states);
  for (let i = 0; i < 3; i++) { assert.equal([...g.timers.values()][0].delay, 420000); g.tick(); }
  assert.equal(g.current(), 4); assert.equal(g.status.textContent, ''); assert.equal(g.timers.size, 1);
});
check('wraparound and all-other-frames-unavailable keep one usable image', () => {
  const g = gallery(repairedJS); g.previous.fire('click'); assert.equal(g.current(), 8); g.next.fire('click'); assert.equal(g.current(), 0);
  const only = gallery(repairedJS, states.map((state, i) => ({...state, naturalWidth: i ? 0 : 20})));
  only.next.fire('click'); only.previous.fire('click'); assert.equal(only.current(), 0);
  const none = gallery(repairedJS, states.map(state => ({...state, naturalWidth: 0})));
  none.next.fire('click'); assert.equal(none.current(), 0);
});
check('manual, focus, hover, visibility and reduced-motion pause rules survive', () => {
  const g = gallery(repairedJS);
  g.root.fire('mouseenter'); assert.equal(g.timers.size, 0); g.root.fire('mouseleave'); assert.equal(g.timers.size, 1);
  g.doc.hidden = true; g.doc.fire('visibilitychange'); assert.equal(g.timers.size, 0);
  g.doc.hidden = false; g.doc.fire('visibilitychange'); assert.equal(g.timers.size, 1);
  g.setActive(false); g.win.fire('hashchange'); assert.equal(g.timers.size, 0);
  g.setActive(true); g.win.fire('hashchange'); assert.equal(g.timers.size, 1);
  g.root.fire('focusin', {target: g.next}); assert.equal(g.timers.size, 0); assert.equal(g.toggle.textContent, 'Play photos');
  g.toggle.fire('click'); assert.equal(g.timers.size, 1); g.motion.fire('change'); assert.equal(g.timers.size, 0);
  assert.equal(gallery(repairedJS, states, true).timers.size, 0);
});

async function worker(source) {
  const handlers = new Map(), rows = new Map();
  let online = true, policy = null;
  const base = 'https://public.example.invalid/app/sw.js';
  const cache = {async put(request, response) { rows.set(request.url, response.clone()); }, async match(request, opts = {}) {
    const url = typeof request === 'string' ? request : request.url;
    if (rows.has(url)) return rows.get(url).clone();
    if (opts.ignoreSearch) { const wanted = new URL(url); for (const [key, value] of rows) if (new URL(key).pathname === wanted.pathname) return value.clone(); }
  }};
  const requests = [];
  const sandbox = {URL, Request, Response, Set, Promise, console, caches: {async open() { return cache; }, async keys() { return []; }, async delete() {}},
    async fetch(request) { requests.push(request); if (!online) throw new Error('Synthetic offline'); return new Response('Synthetic ' + new URL(request.url).pathname, {status: 200, headers: policy || {}}); },
    self: {location: {href: base, origin: new URL(base).origin}, addEventListener(name, fn) { handlers.set(name, fn); }, async skipWaiting() {}, clients: {async claim() {}}}};
  vm.runInNewContext(source, sandbox, {timeout: 1000});
  let installation; handlers.get('install')({waitUntil(promise) { installation = promise; }}); await installation;
  return {rows, requests, offline() { online = false; }, setPolicy(value) { policy = value; }, async request(relative) {
    let reply; const waits = []; const request = new Request(new URL(relative, base));
    handlers.get('fetch')({request, respondWith(promise) { reply = promise; }, waitUntil(promise) { waits.push(promise); }});
    const result = await reply; await Promise.all(waits); return result;
  }};
}
(async () => {
  const stale = await worker(baseline('sw.js')); stale.offline();
  await assert.rejects(stale.request('./assets/visuals/kcmc-ministry-group.jpg'), /Synthetic offline/);
  console.log('PASS: stale worker reproduces uncached fourth-frame offline failure');
  const fixed = await worker(fs.readFileSync(path.join(APP, 'sw.js'), 'utf8'));
  assert(fixed.requests.every(request => request.credentials === 'omit' && request.cache === 'reload'));
  fixed.offline();
  const index = fs.readFileSync(path.join(APP, 'index.php'), 'utf8');
  const heroPaths = [...index.matchAll(/data-hero-photo[^>]*src="([^"]+)"/g)].map(match => match[1]);
  assert.equal(heroPaths.length, 4);
  assert.ok(heroPaths.every(path => !/stage-2014|ministry-group|bridge-/.test(path)));
  for (const asset of heroPaths) assert.equal((await fixed.request(asset)).status, 200, asset + ' is available offline');
  console.log('PASS: all four retained hero paths are anonymously cached and available offline');
  for (const name of ['kcmc-ministry-group.jpg', 'kcmc-bridge-logo.jpg', 'kcmc-bridge-wordmark.png', 'kcmc-bridge-logo-composite.png']) {
    assert(!fixed.rows.has(new URL('./assets/visuals/' + name, 'https://public.example.invalid/app/sw.js').href));
  }
  console.log('PASS: removed poster and layered artwork are absent from the refreshed public cache');
  for (const relative of ['./member/login.php', './admin/publication-designer.php', './api/public-content.php', './data/content.json', './backups/test.json', './?token=synthetic', './assets/visuals/kcmc-congregation-gathering.jpg?token=synthetic']) {
    await assert.rejects(fixed.request(relative), /Synthetic offline/);
    assert(!fixed.rows.has(new URL(relative, 'https://public.example.invalid/app/sw.js').href));
  }
  console.log('PASS: private, API, data, backup and token-bearing paths remain network only');
  for (const headers of [{'Cache-Control': 'private'}, {'Cache-Control': 'no-store'}, {'Set-Cookie': 'synthetic=1'}]) {
    const guarded = await worker(fs.readFileSync(path.join(APP, 'sw.js'), 'utf8')); guarded.rows.clear(); guarded.setPolicy(headers);
    await guarded.request('./assets/visuals/kcmc-congregation-gathering.jpg'); assert.equal(guarded.rows.size, 0);
  }
  console.log('PASS: private/no-store/cookie response policy remains fail closed');
})().catch(error => { console.error(error); process.exitCode = 1; });
