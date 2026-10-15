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

function fixture({firstVisit = false, oldKey = false, unsubscribeFails = false, denied = false, saveFails = false} = {}) {
  const actions = [], requests = [], handlers = {};
  const status = {textContent: ''};
  const enable = {disabled: false, addEventListener(type, fn) { handlers.enable = fn; }};
  const disable = {disabled: false, addEventListener(type, fn) { handlers.disable = fn; }};
  const root = {dataset: {enabled: '1', api: '/app/api/push-subscription.php', csrf: 'synthetic-csrf', publicKey}};
  const listeners = new Set();
  const worker = {state: 'installing', addEventListener(type, fn) { listeners.add(fn); }, removeEventListener(type, fn) { listeners.delete(fn); }};
  const subscription = (old = false) => ({
    endpoint: old ? 'https://push.example.invalid/old' : 'https://push.example.invalid/new',
    options: {applicationServerKey: Uint8Array.from(old ? [4, ...Array(64).fill(99)] : key).buffer},
    toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'synthetic', auth: 'synthetic'}}; },
    async unsubscribe() { actions.push('browser-unsubscribe'); if (unsubscribeFails) return false; currentSub = null; return true; }
  });
  let currentSub = firstVisit ? null : subscription(oldKey);
  const reg = {
    active: firstVisit ? null : {}, installing: firstVisit ? worker : null,
    pushManager: {
      async getSubscription() { return currentSub; },
      async subscribe(options) {
        assert.ok(reg.active, 'subscription must wait for worker activation');
        assert.deepEqual(Array.from(options.applicationServerKey), Array.from(key));
        actions.push('browser-subscribe'); currentSub = subscription(); return currentSub;
      }
    }
  };
  const Notification = {permission: denied ? 'denied' : 'granted', async requestPermission() { actions.push('permission'); return this.permission; }};
  let registered = !firstVisit;
  const navigator = {serviceWorker: {
    async getRegistration() { return registered ? reg : null; },
    async register() { registered = true; actions.push('register'); return reg; }
  }};
  const context = {
    Uint8Array, setTimeout, clearTimeout, atob: value => Buffer.from(value, 'base64').toString('binary'),
    document: {getElementById(id) { return {'push-settings': root, 'push-status': status, 'push-enable': enable, 'push-disable': disable}[id]; }},
    navigator, Notification, window: {PushManager: {}, Notification},
    async fetch(url, options) {
      assert.equal(url, '/app/api/push-subscription.php');
      assert.equal(options.credentials, 'same-origin');
      const body = JSON.parse(options.body); requests.push(body); actions.push('server-' + body.action);
      assert.equal(body.csrf, 'synthetic-csrf');
      return {ok: !saveFails, async json() { return saveFails ? {ok: false, error: 'Synthetic save rejected'} : {ok: true}; }};
    }
  };
  vm.runInNewContext(source, context, {filename: 'actual-push-settings.js'});
  return {actions, requests, status, enable, disable,
    click: () => handlers.enable(), off: () => handlers.disable(),
    activate() { worker.state = 'activated'; reg.active = {}; for (const listener of [...listeners]) listener(); },
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
})().catch(error => { console.error(error); process.exitCode = 1; });
