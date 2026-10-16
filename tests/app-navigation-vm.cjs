#!/usr/bin/env node
'use strict';
// Exercise the real navigation client without a browser or private account.
// Actual Navigation API redaction, reload and traversal are also tested in the
// real-PHP browser suite; this isolates malformed and unsupported API cases.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/app-navigation.js'), 'utf8');
const origin = 'https://church.example.invalid';
const app = origin + '/app/';
const currentUrl = app + 'member/notifications.php?private_context=synthetic#security';
const namespace = 'kcmcAppScreenV1';
const marker = (overrides = {}) => ({version: 1, base: '/app/', origin, path: '/app/member/timeclock.php', key: 'previous-key', index: 0, ...overrides});
let checks = 0;

function fixture(options = {}) {
  let click;
  let backs = 0;
  let updates = 0;
  const classic = {unrelatedClassic: {exact: ['keep', 7]}};
  const location = new URL(options.currentUrl || currentUrl);
  const link = {
    dataset: {kcmcAppBase: options.base === undefined ? '/app/' : options.base},
    addEventListener(type, listener) { assert.equal(type, 'click'); click = listener; },
  };
  const document = {
    referrer: options.referrer || '', documentElement: {dataset: {}},
    querySelectorAll(selector) { assert.equal(selector, '[data-kcmc-back]'); return [link]; },
  };
  const history = {
    length: options.historyLength === undefined ? 2 : options.historyLength,
    state: classic,
    back() { backs++; },
    pushState() { throw new Error('The navigation client must not write classic history state'); },
    replaceState() { throw new Error('The navigation client must not write classic history state'); },
  };
  const sandbox = {URL, location, document, history};
  sandbox.window = sandbox;
  for (const storage of ['sessionStorage', 'localStorage']) {
    Object.defineProperty(sandbox, storage, {get() { throw new Error('The navigation client must not use browser storage'); }});
  }
  const context = vm.createContext(sandbox);
  const inRealm = value => value === undefined ? undefined : vm.runInContext('JSON.parse(' + JSON.stringify(JSON.stringify(value)) + ')', context);
  let currentState = inRealm(Object.hasOwn(options, 'state') ? options.state : {unrelatedNavigation: {exact: ['keep', 9]}});
  const previous = {
    key: options.previousKey || 'previous-key', index: options.previousIndex === undefined ? 0 : options.previousIndex,
    url: Object.hasOwn(options, 'previousUrl') ? options.previousUrl : null,
    getState() {
      if (options.previousStateThrows) throw new Error('Previous state unavailable');
      return inRealm(Object.hasOwn(options, 'previousState') ? options.previousState : {[namespace]: marker()});
    },
  };
  const current = {
    key: options.currentKey || 'current-key', index: options.currentIndex === undefined ? 1 : options.currentIndex, url: location.href,
    getState() { if (options.stateThrows) throw new Error('Current state unavailable'); return currentState; },
  };
  const navigation = {
    canGoBack: options.canGoBack === undefined ? true : options.canGoBack, currentEntry: current,
    entries() { if (options.entriesThrows) throw new Error('Entries unavailable'); return [previous, current]; },
    updateCurrentEntry({state}) {
      updates++;
      if (options.updateThrows) throw new Error('State update unavailable');
      currentState = state;
    },
  };
  if (options.noUpdate) delete navigation.updateCurrentEntry;
  if (options.noGetState) delete current.getState;
  sandbox.navigation = options.noNavigation ? undefined : navigation;
  vm.runInContext(source, context, {filename: 'app-navigation.js'});
  assert.deepEqual(history.state, {unrelatedClassic: {exact: ['keep', 7]}});
  assert.equal(document.documentElement.dataset.kcmcNavigationReady, 'true');
  return {
    event(eventOptions = {}) {
      const event = {defaultPrevented: false, button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false,
        preventDefault() { this.defaultPrevented = true; }, ...eventOptions};
      click(event);
      return {prevented: event.defaultPrevented, backs, updates};
    },
    state() { return currentState === undefined ? undefined : JSON.parse(JSON.stringify(currentState)); },
    updates() { return updates; },
  };
}

function test(label, run) {
  run(); checks++; console.log('PASS: ' + label);
}
function back(options = {}, event = {}) {
  const result = fixture(options).event(event);
  assert.equal(result.prevented, true); assert.equal(result.backs, 1);
}
function fallback(options = {}, event = {}) {
  const result = fixture(options).event(event);
  assert.equal(result.backs, 0); assert.equal(result.prevented, !!event.defaultPrevented);
}

test('current-entry marker contains only path identity and preserves unrelated Navigation and classic state', () => {
  const f = fixture();
  assert.equal(f.updates(), 1);
  const state = f.state();
  assert.deepEqual(state.unrelatedNavigation, {exact: ['keep', 9]});
  assert.deepEqual(state[namespace], marker({path: '/app/member/notifications.php', key: 'current-key', index: 1}));
  assert.deepEqual(Object.keys(state[namespace]).sort(), ['base', 'index', 'key', 'origin', 'path', 'version']);
  assert.ok(!JSON.stringify(state[namespace]).includes('private_context'));
  assert.ok(!JSON.stringify(state[namespace]).includes('security'));
});
test('redacted adjacent private entry with a valid owned marker enables Back', () => back());
test('visible safe same-app entry does not need a marker', () => back({previousUrl: app + 'member/timeclock.php', previousState: null}));
test('redacted entry without an owned marker uses the real fallback', () => fallback({previousState: {unrelated: true}}));
test('redacted entry with unavailable state uses fallback', () => fallback({previousStateThrows: true}));
for (const [label, change] of Object.entries({version: {version: 2}, base: {base: '/other/'}, origin: {origin: 'https://outside.example.invalid'}, key: {key: 'different-key'}, index: {index: 9}})) {
  test('redacted marker rejects mismatched ' + label, () => fallback({previousState: {[namespace]: marker(change)}}));
}
for (const invalid of ['/outside/timeclock.php', '//outside.example.invalid/app/', '/app/../outside/', '/app/member/timeclock.php?context=private', '/app/member/timeclock.php#private', '/app/member/\\outside', '/app/member/\nunsafe']) {
  test('redacted marker rejects unsafe path ' + JSON.stringify(invalid), () => fallback({previousState: {[namespace]: marker({path: invalid})}}));
}
test('known external URL remains authoritative even with a valid marker', () => fallback({previousUrl: 'https://outside.example.invalid/app/member/timeclock.php'}));
test('known out-of-app URL cannot be rescued by its marker', () => fallback({previousUrl: origin + '/app-other/member/timeclock.php'}));
test('malformed visible previous URL uses fallback', () => fallback({previousUrl: 'http://['}));
test('recognized API entries failure stays closed even with a safe referrer', () => fallback({entriesThrows: true, referrer: app + 'member/timeclock.php'}));
test('a different private entry at the same path still permits Back', () => back({previousState: {[namespace]: marker({path: '/app/member/notifications.php'})}}));
test('nonadjacent entry cannot be used as the previous history item', () => fallback({previousIndex: -2}));
test('nonintegral current index uses fallback', () => fallback({currentIndex: 1.5}));
test('duplicate current and previous keys cannot authorize traversal', () => fallback({previousKey: 'current-key'}));
test('short history with canGoBack false uses fallback', () => fallback({canGoBack: false, historyLength: 1}));
test('unsupported Navigation API retains safe same-app referrer behavior', () => back({noNavigation: true, referrer: app + 'member/timeclock.php'}));
test('unsupported Navigation API with no referrer keeps fallback', () => fallback({noNavigation: true}));
test('unsupported Navigation API never follows an external referrer', () => fallback({noNavigation: true, referrer: 'https://outside.example.invalid/app/'}));
test('unsupported Navigation API never uses a sibling app referrer', () => fallback({noNavigation: true, referrer: origin + '/app-other/'}));
for (const state of [[], ['unrelated'], 'unrelated', 7, true]) {
  test('unrelated nonobject Navigation state is preserved ' + JSON.stringify(state), () => {
    const f = fixture({state}); assert.equal(f.updates(), 0); assert.deepEqual(f.state(), state);
  });
}
for (const state of [null, undefined]) {
  test('fresh Navigation state may receive only the app marker ' + String(state), () => {
    const f = fixture({state}); assert.equal(f.updates(), 1); assert.deepEqual(Object.keys(f.state()), [namespace]);
  });
}
test('unavailable state reader never destroys existing state', () => { const f = fixture({noGetState: true}); assert.equal(f.updates(), 0); });
test('throwing state reader is harmless', () => { const f = fixture({stateThrows: true}); assert.equal(f.updates(), 0); });
test('unavailable state updater is harmless', () => { const f = fixture({noUpdate: true}); assert.equal(f.updates(), 0); });
test('throwing state update leaves original state intact', () => {
  const f = fixture({updateThrows: true}); assert.deepEqual(f.state(), {unrelatedNavigation: {exact: ['keep', 9]}});
});
for (const event of [{ctrlKey: true}, {metaKey: true}, {shiftKey: true}, {altKey: true}, {button: 1}, {defaultPrevented: true}]) {
  test('modified or already handled click is not intercepted ' + JSON.stringify(event), () => fallback({}, event));
}
test('off-origin app base cannot enable Back or marker updates', () => { const f = fixture({base: 'https://outside.example.invalid/app/'}); assert.equal(f.updates(), 0); assert.equal(f.event().backs, 0); });
test('malformed app base is harmless', () => fallback({base: 'http://['}));
console.log(checks + ' navigation state, privacy and safe-fallback scenarios passed.');
