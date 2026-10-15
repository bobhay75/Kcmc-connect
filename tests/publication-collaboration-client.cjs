'use strict';
// Execute the actual editor collaboration functions with synthetic fetch/timers.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const full = fs.readFileSync(path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php'), 'utf8');
const start = full.indexOf('function publicationFingerprint('), end = full.indexOf('async function renderSaved(){', start);
assert.ok(start > 0 && end > start);
const source = full.slice(start, end);
const id = 'pub_' + 'a'.repeat(24);
const clone = value => JSON.parse(JSON.stringify(value));
const response = (status, data) => ({status, ok: status >= 200 && status < 300, async json() { return clone(data); }});
const deferred = () => { let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve}; };

function fixture() {
  const nodes = {'projectName': {value: 'Local draft'}, saveCopyBtn: {hidden: true}, loadLatestBtn: {hidden: true}};
  const timers = new Map(), events = {};
  let nextTimer = 0;
  const f = {requests: [], status: '', renderCount: 0};
  const c = {
    projectEndpoint: '/app/admin/publication-projects.php', csrf: 'synthetic-csrf',
    projectId: id, projectRevision: 1, projectGeneration: 0, saveInFlight: false,
    lastSavedFingerprint: null, remoteChange: false, watchTimer: null, watchInFlight: false, watchStopped: false, watchDelay: 10000,
    currentPageIndex: 0, pageState: [{pageSize: 'letter', orientation: 'portrait', items: [{type: 'text', text: 'Local words\n\n________'}]}],
    saveButton: {disabled: false},
    document: {hidden: false, getElementById(name) { return nodes[name]; }, addEventListener(name, callback) {events[name] = callback;}},
    window: {confirm() { return true; }},
    setTimeout(callback, delay) {timers.set(++nextTimer, {callback, delay}); return nextTimer;},
    clearTimeout(timer) {timers.delete(timer);},
    setStatus(message) {f.status = message;},
    resetHistory() {}, renderPageData() {},
    serialize() {return {id: c.projectId, revision: c.projectRevision, name: nodes.projectName.value, pages: clone(c.pageState)};},
    async renderSaved() {f.renderCount++;},
    async fetch(url, options = {}) {f.requests.push({url, options}); return f.transport(url, options);}
  };
  f.transport = async () => response(500, {ok: false, error: 'Synthetic failure'});
  vm.createContext(c); vm.runInContext(source, c, {filename: 'actual-editor-collaboration.js'});
  c.lastSavedFingerprint = c.publicationFingerprint(c.serialize());
  Object.assign(f, {c, nodes, timers, events});
  return f;
}
function check(label) {console.log('PASS: ' + label);}

(async () => {
  let f = fixture();
  f.transport = async (url, options) => {const p = JSON.parse(options.body); assert.equal(p.revision, 1); assert.equal(p.id, id); assert.equal(p.csrf, 'synthetic-csrf'); return response(200, {ok: true, project: {...p, revision: 2}});};
  await f.c.save(); assert.equal(f.c.projectRevision, 2); assert.equal(f.nodes.saveCopyBtn.hidden, true); check('save sends its loaded revision and adopts only the accepted server revision');

  f = fixture(); const original = clone(f.c.serialize());
  f.transport = async () => response(409, {ok: false, error: 'This publication changed. Your edits are still here.'});
  await f.c.save(); assert.deepEqual(f.c.serialize(), original); assert.equal(f.nodes.saveCopyBtn.hidden, false); assert.match(f.status, /edits are still here/); check('409 preserves the actual editor state and exposes explicit recovery choices');

  f = fixture(); const copiedId = 'pub_' + 'b'.repeat(24);
  f.transport = async (url, options) => {const p = JSON.parse(options.body); assert.equal(p.id, null); assert.equal(p.revision, 0); return response(200, {ok: true, project: {...p, id: copiedId, revision: 1}});};
  await f.c.save(true); assert.equal(f.c.projectId, copiedId); check('Save a copy creates a new project without overwriting the conflicted original');

  f = fixture(); const beforeWatch = clone(f.c.serialize());
  f.transport = async () => response(200, {ok: true, project: {id, revision: 2}});
  await f.c.watchProject(); assert.deepEqual(f.c.serialize(), beforeWatch); assert.equal(f.c.remoteChange, true); check('a remote revision only marks the saved draft stale and never replaces local edits');

  f = fixture(); f.c.document.hidden = true; await f.c.watchProject(); assert.equal(f.requests.length, 0); assert.equal(f.timers.size, 0); check('hidden pages do not poll');

  f = fixture(); let held = deferred(); f.transport = () => held.promise;
  let pending = f.c.watchProject(); await f.c.watchProject(); assert.equal(f.requests.length, 1); held.resolve(response(200, {ok: true, project: {id, revision: 1}})); await pending; assert.equal(f.c.watchInFlight, false); check('polling permits only one request at a time');

  f = fixture(); f.transport = async () => response(401, {ok: false}); await f.c.watchProject(); assert.equal(f.c.watchStopped, true); assert.equal(f.timers.size, 0); assert.match(f.status, /unsaved changes are still here/); check('expired access stops polling while retaining the editor');

  f = fixture(); f.transport = async () => {throw new Error('offline');}; await f.c.watchProject(); assert.equal(f.c.watchDelay, 20000); check('transient polling failures back off');

  f = fixture(); f.c.pageState[0].items[0].text = 'Unsaved before load'; f.c.window.confirm = () => false; await f.c.loadLatest(); assert.equal(f.requests.length, 0); check('declining Load latest does not fetch or discard unsaved changes');

  f = fixture(); held = deferred(); f.transport = () => held.promise; pending = f.c.loadLatest(); f.c.pageState[0].items[0].text = 'Typed while loading'; held.resolve(response(200, {ok: true, projects: [{id, revision: 2, name: 'Remote', pages: []}]})); await pending; assert.equal(f.c.pageState[0].items[0].text, 'Typed while loading'); assert.equal(f.c.projectRevision, 1); check('edits typed while Load latest is pending remain intact');

  for (const saveCompletesFirst of [false, true]) {
    f = fixture(); const get = deferred(), post = deferred();
    f.transport = (url, options) => options.method === 'POST' ? post.promise : get.promise;
    const load = f.c.loadLatest(), save = f.c.save();
    if (saveCompletesFirst) {post.resolve(response(200, {ok: true, project: {id, revision: 2}})); await save;}
    get.resolve(response(200, {ok: true, projects: [{id, revision: 1, name: 'Old remote', pages: []}]})); await load;
    assert.equal(f.nodes.projectName.value, 'Local draft');
    if (!saveCompletesFirst) {post.resolve(response(200, {ok: true, project: {id, revision: 2}})); await save;}
    assert.equal(f.c.projectRevision, 2); assert.equal(f.c.projectGeneration, 0);
    check('late Load latest cannot replace a ' + (saveCompletesFirst ? 'completed' : 'pending') + ' save');
  }

  f = fixture(); f.transport = async () => ({status: 200, redirected: true}); await f.c.save(); assert.match(f.status, /Sign in again/); assert.equal(f.c.projectRevision, 1); check('a sign-in redirect produces a useful error and preserves the draft');
})().catch(error => {console.error(error); process.exitCode = 1;});
