'use strict';
// Execute the actual client with synthetic browser objects. No browser/network sends.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/member/push-settings.js'), 'utf8');
const key = Uint8Array.from([4, ...Array.from({length: 64}, (_, n) => n + 1)]);
const publicKey = Buffer.from(key).toString('base64url');
const tick = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); };

async function workerRuntime() {
  const workerSource = fs.readFileSync(process.argv[3] || path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/sw.js'), 'utf8');
  const appURL = 'https://fixture.example.invalid/app/';
  const handlers = {}, displays = [], opened = [], focused = [];
  let windows = [];
  const self = {
    location: new URL(appURL + 'sw.js'),
    addEventListener(type, fn) { handlers[type] = fn; },
    registration: {async showNotification(title, options) { displays.push({title, options}); }},
    clients: {
      async matchAll(options) { assert.equal(options.type, 'window'); assert.equal(options.includeUncontrolled, true); return windows; },
      async openWindow(url) { opened.push(url); }
    }
  };
  vm.runInNewContext(workerSource, {self, URL,
    fetch() { throw new Error('Push display and click must not fetch network resources directly'); }
  }, {filename: 'actual-push-worker.js'});
  const push = async data => {
    let work;
    handlers.push({data, waitUntil(promise) { work = promise; }});
    assert.ok(work && typeof work.then === 'function', 'push waits for notification display');
    await work;
    return displays.at(-1);
  };
  const click = async data => {
    let work, closed = 0;
    handlers.notificationclick({notification: {data, close() { closed++; }}, waitUntil(promise) { work = promise; }});
    await work;
    assert.equal(closed, 1);
  };

  await push(null); await push(null);
  assert.equal(displays.length, 2);
  for (const {title, options} of displays) {
    assert.equal(title, 'KCMC Connect');
    assert.equal(options.body, 'There is a new KCMC update.');
    assert.equal(options.tag, 'kcmc-update');
    assert.equal(options.renotify, true, 'replacement notifications request a fresh alert');
    assert.equal(options.data.url, appURL);
  }
  console.log('PASS: actual worker displays both payloadless pushes with repeat alerts and one stable tag');

  for (const url of ['https://outside.example.invalid/', './member/private.php', './admin/private.php', './api/private.php', './data/private.json', './backups/private.json', './?private=synthetic', './#private']) {
    const result = await push({json: () => ({url})});
    assert.equal(result.options.data.url, appURL, 'unsafe notification links fall back to public home');
  }
  const malformed = await push({json() { throw new Error('Synthetic malformed payload'); }});
  assert.equal(malformed.options.data.url, appURL);
  assert.equal(malformed.title, 'KCMC Connect');
  const publicPush = await push({json: () => ({title: 'T'.repeat(100), body: 'B'.repeat(200), url: './events.php'})});
  assert.equal(publicPush.title.length, 80);
  assert.equal(publicPush.options.body.length, 180);
  assert.equal(publicPush.options.data.url, appURL + 'events.php');
  console.log('PASS: actual worker preserves safe public destinations, fallbacks and payload bounds');

  windows = [{url: appURL + 'events.php', async focus() { focused.push(this.url); }}];
  await click(publicPush.options.data);
  assert.deepEqual(focused, [appURL + 'events.php']);
  assert.equal(opened.length, 0, 'an existing matching window is focused');
  windows = [];
  await click(displays[0].options.data);
  await click(undefined);
  assert.deepEqual(opened, [appURL, appURL]);
  console.log('PASS: actual worker click focuses an existing public page or opens public home, including missing-data fallback');
}

function fixture({firstVisit = false, oldKey = false, unsubscribeFails = false, denied = false, saveFails = false,
  permission = denied ? 'denied' : 'granted', parentWorker = false, replacingWorker = false, displayFails = false,
  appURL = 'https://fixture.example.invalid/app/'} = {}) {
  const actions = [], requests = [], handlers = {}, registrations = [], displays = [];
  const workerURL = appURL + 'sw.js';
  const status = {textContent: ''};
  const displayStatus = {textContent: ''};
  const enable = {disabled: false, addEventListener(type, fn) { handlers.enable = fn; }};
  const disable = {disabled: false, addEventListener(type, fn) { handlers.disable = fn; }};
  const display = {disabled: false, addEventListener(type, fn) { handlers.display = fn; }};
  const root = {dataset: {enabled: '1', api: '/app/api/push-subscription.php', worker: new URL(workerURL).pathname, csrf: 'synthetic-csrf', publicKey}};
  const listeners = new Set();
  const worker = {scriptURL: workerURL, state: 'installing', addEventListener(type, fn) { listeners.add(fn); }, removeEventListener(type, fn) { listeners.delete(fn); }};
  const subscription = (old = false) => ({
    endpoint: old ? 'https://push.example.invalid/old' : 'https://push.example.invalid/new',
    options: {applicationServerKey: Uint8Array.from(old ? [4, ...Array(64).fill(99)] : key).buffer},
    toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'synthetic', auth: 'synthetic'}}; },
    async unsubscribe() { actions.push('browser-unsubscribe'); if (unsubscribeFails) return false; currentSub = null; return true; }
  });
  let currentSub = firstVisit ? null : subscription(oldKey);
  const reg = {
    active: firstVisit ? null : {scriptURL: replacingWorker ? appURL + 'unrelated.js' : workerURL},
    installing: firstVisit || replacingWorker ? worker : null,
    async showNotification(title, options) {
      actions.push('display-notification');
      if (displayFails) throw new Error('Synthetic display rejected');
      displays.push({title, options});
    },
    pushManager: {
      async getSubscription() { return currentSub; },
      async subscribe(options) {
        assert.equal(reg.active?.scriptURL, workerURL, 'subscription must wait for the KCMC worker activation');
        assert.deepEqual(Array.from(options.applicationServerKey), Array.from(key));
        actions.push('browser-subscribe'); currentSub = subscription(); return currentSub;
      }
    }
  };
  const Notification = {permission, async requestPermission() { actions.push('permission'); return this.permission; }};
  const navigator = {serviceWorker: {
    async getRegistration() {
      actions.push('get-unspecified-registration');
      if (parentWorker) return {scope: 'https://fixture.example.invalid/', active: {scriptURL: 'https://fixture.example.invalid/other-sw.js'}, pushManager: {
        getSubscription() { throw new Error('Unrelated parent worker must not be used'); }
      }};
      return firstVisit ? null : reg;
    },
    async register(url, options) {
      assert.equal(url, workerURL);
      assert.equal(options.scope, appURL);
      assert.equal(options.updateViaCache, 'none');
      registrations.push({url, scope: options.scope}); actions.push('register'); return reg;
    }
  }};
  const context = {
    URL, Uint8Array, setTimeout, clearTimeout, atob: value => Buffer.from(value, 'base64').toString('binary'),
    document: {getElementById(id) { return {'push-settings': root, 'push-status': status, 'push-enable': enable, 'push-disable': disable,
      'push-display-test': display, 'push-display-status': displayStatus}[id]; }},
    navigator, Notification, window: {PushManager: {}, Notification, location: {href: appURL + 'member/notifications.php?private-context=synthetic#device'}},
    async fetch(url, options) {
      assert.equal(url, '/app/api/push-subscription.php');
      assert.equal(options.credentials, 'same-origin');
      const body = JSON.parse(options.body); requests.push(body); actions.push('server-' + body.action);
      assert.equal(body.csrf, 'synthetic-csrf');
      return {ok: !saveFails, async json() { return saveFails ? {ok: false, error: 'Synthetic save rejected'} : {ok: true}; }};
    }
  };
  vm.runInNewContext(source, context, {filename: 'actual-push-settings.js'});
  return {actions, requests, registrations, displays, status, displayStatus, enable, disable, display,
    click: () => handlers.enable(), off: () => handlers.disable(), show: () => handlers.display(),
    activate() { worker.state = 'activated'; reg.active = worker; for (const listener of [...listeners]) listener(); },
    redundant() { worker.state = 'redundant'; for (const listener of [...listeners]) listener(); }
  };
}

(async () => {
  let f = fixture({firstVisit: true});
  await tick();
  const enabling = f.click(); await tick();
  assert.ok(!f.actions.includes('browser-subscribe'), 'first visit does not subscribe before activation');
  f.activate(); await enabling;
  assert.deepEqual(f.actions.filter(a => a.startsWith('browser-') || a.startsWith('server-')), ['browser-subscribe', 'server-subscribe']);
  assert.equal(f.status.textContent, 'Notifications are enabled on this device.');
  assert.equal(f.enable.disabled, false);
  console.log('PASS: first-visit subscription waits for the active worker');

  f = fixture({oldKey: true}); await tick();
  assert.match(f.status.textContent, /older notification key/);
  assert.equal(f.requests.length, 0, 'loading settings never sends or changes subscriptions');
  await f.click();
  assert.deepEqual(f.actions.filter(a => a.startsWith('browser-') || a.startsWith('server-')), ['server-unsubscribe', 'browser-unsubscribe', 'browser-subscribe', 'server-subscribe']);
  assert.equal(f.requests[0].endpoint, 'https://push.example.invalid/old');
  assert.equal(f.requests[1].subscription.endpoint, 'https://push.example.invalid/new');
  console.log('PASS: explicit Enable reconnects a subscription bound to an older VAPID key');

  f = fixture({oldKey: true, unsubscribeFails: true}); await tick(); await f.click();
  assert.ok(!f.actions.includes('browser-subscribe'));
  assert.match(f.status.textContent, /Could not reconnect/);
  assert.equal(f.enable.disabled, false);
  console.log('PASS: failed browser unsubscribe does not claim success or save an incompatible replacement');

  f = fixture(); await tick();
  assert.match(f.status.textContent, /confirm this device is registered/);
  await f.click();
  assert.deepEqual(f.actions.filter(a => a.startsWith('browser-') || a.startsWith('server-')), ['server-subscribe']);
  console.log('PASS: a matching existing subscription is re-saved without unnecessary replacement');

  f = fixture({denied: true}); await tick(); await f.click();
  assert.equal(f.requests.length, 0);
  assert.match(f.status.textContent, /permission was not granted/);
  assert.equal(f.enable.disabled, false);
  console.log('PASS: denied permission makes no server request');

  f = fixture({saveFails: true}); await tick(); await f.click();
  assert.equal(f.status.textContent, 'Synthetic save rejected');
  assert.equal(f.enable.disabled, false);
  console.log('PASS: failed server registration is reported without claiming enabled status');

  f = fixture(); await tick(); await f.off();
  assert.deepEqual(f.actions.filter(a => a.startsWith('browser-') || a.startsWith('server-')), ['server-unsubscribe', 'browser-unsubscribe']);
  assert.equal(f.status.textContent, 'Notifications are disabled on this device.');
  console.log('PASS: explicit disable still revokes server and browser subscriptions');

  f = fixture({unsubscribeFails: true}); await tick(); await f.off();
  assert.match(f.status.textContent, /could not finish turning notifications off/);
  assert.doesNotMatch(f.status.textContent, /Notifications are disabled/);
  assert.equal(f.disable.disabled, false);
  console.log('PASS: browser unsubscribe refusal reports a retry instead of claiming disabled');

  f = fixture({parentWorker: true}); await tick(); await f.click();
  assert.equal(f.actions.includes('get-unspecified-registration'), false);
  assert.equal(f.registrations.length, 1, 'explicit registration is shared by refresh and Enable');
  assert.deepEqual(f.actions.filter(a => a.startsWith('browser-') || a.startsWith('server-')), ['server-subscribe']);
  console.log('PASS: a parent-site worker is never selected for the KCMC subscription');

  f = fixture({replacingWorker: true}); await tick();
  const replacement = f.click(); await tick();
  assert.equal(f.requests.length, 0, 'another active script at the app scope is not reused');
  f.activate(); await replacement;
  assert.equal(f.requests.length, 1);
  console.log('PASS: replacement waits for the matching KCMC script to activate');

  for (const permission of ['default', 'denied']) {
    f = fixture({permission}); await tick(); await f.show();
    assert.equal(f.requests.length, 0);
    assert.equal(f.displays.length, 0);
    assert.equal(f.actions.includes('permission'), false, 'display test never requests notification permission');
    assert.match(f.displayStatus.textContent, /Enable notifications first/);
    assert.equal(f.display.disabled, false);
  }
  console.log('PASS: display test requires existing permission without prompting or changing subscriptions');

  for (const appURL of ['https://fixture.example.invalid/app/', 'https://fixture.example.invalid/']) {
    f = fixture({appURL}); await tick();
    assert.equal(f.displays.length, 0, 'loading settings never displays a notification');
    await f.show(); await f.show();
    assert.equal(f.requests.length, 0, 'local display test never posts to the API');
    assert.equal(f.actions.includes('permission'), false);
    assert.equal(f.displays.length, 2);
    const {title, options} = f.displays[0];
    assert.equal(title, 'KCMC display test');
    assert.equal(options.tag, 'kcmc-display-test');
    assert.equal(options.renotify, true);
    assert.equal(options.data.url, appURL, 'local test opens the public app root without private context');
    assert.equal(options.icon, appURL + 'assets/icons/icon-192.png');
    assert.match(f.displayStatus.textContent, /^Display test requested\./);
    assert.equal(f.display.disabled, false);
  }
  console.log('PASS: explicit repeatable display test stays local and supports root or nested app hosting');

  f = fixture({displayFails: true}); await tick(); await f.show();
  assert.equal(f.displayStatus.textContent, 'Synthetic display rejected');
  assert.equal(f.display.disabled, false);
  assert.equal(f.requests.length, 0);
  console.log('PASS: rejected local display request reports failure and restores the control');

  await workerRuntime();
})().catch(error => { console.error(error); process.exitCode = 1; });
