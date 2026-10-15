'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../KCMC-Connect-Phase6-Recreated/admin/publishing-desk.js'), 'utf8');
const reply = (status, data) => ({status, ok: status >= 200 && status < 300, async json() {return data;}});
function fixture() {
  const f = {requests: [], events: [], status: {textContent: ''}, latest: {hidden: true}};
  const fields = {version: {value: 'a'.repeat(64)}, announcement_body: {value: 'Exact unsaved words'}, confirm_publish: {value: '1'}};
  const form = {action: '/app/admin/save.php', elements: {namedItem(name) {return fields[name];}},
    addEventListener(type, callback) {f.submit = callback;}, dispatchEvent(event) {f.events.push(event.type);}};
  f.transport = async () => reply(500, {ok: false, error: 'Synthetic save failed'});
  const context = {document: {querySelector(selector) {return selector === 'form[data-publishing-form]' ? form : selector === '[data-publishing-save-status]' ? f.status : f.latest;}},
    FormData: class {constructor() {this.values = Object.fromEntries(Object.entries(fields).map(([name, field]) => [name, field.value]));}},
    CustomEvent: class {constructor(type) {this.type = type;}},
    async fetch(url, options) {f.requests.push({url, options}); return f.transport(url, options);}
  };
  vm.runInNewContext(source, context);
  f.fields = fields; f.send = (prevented = false) => f.submit({defaultPrevented: prevented, preventDefault() {}});
  return f;
}
(async () => {
  let f = fixture(); await f.send(true); assert.equal(f.requests.length, 0); console.log('PASS: existing review-guard denial is honored');
  f = fixture(); f.transport = async () => reply(409, {ok: false, error: 'Content changed. Your input is still here.'}); await f.send(); assert.equal(f.fields.announcement_body.value, 'Exact unsaved words'); assert.equal(f.fields.version.value, 'a'.repeat(64)); assert.equal(f.latest.hidden, false); assert.match(f.status.textContent, /still here/); console.log('PASS: stale content keeps all input and exposes comparison without replacing its version');
  f = fixture(); let release; f.transport = () => new Promise(resolve => {release = resolve;}); const pending = f.send(); await f.send(); assert.equal(f.requests.length, 1); f.fields.announcement_body.value = 'Typed during save'; release(reply(200, {ok: true, version: 'b'.repeat(64)})); await pending; assert.equal(f.fields.announcement_body.value, 'Typed during save'); assert.equal(f.fields.version.value, 'b'.repeat(64)); assert.deepEqual(f.events, ['kcmc:publish-start', 'kcmc:published', 'kcmc:publish-finished']); assert.equal(f.requests[0].options.body.values.announcement_body, 'Exact unsaved words'); console.log('PASS: single-flight publishing preserves newer input and adopts the exact committed hash');
  f = fixture(); f.transport = async () => {throw new Error('Network unavailable');}; await f.send(); assert.equal(f.fields.announcement_body.value, 'Exact unsaved words'); assert.equal(f.fields.version.value, 'a'.repeat(64)); assert.equal(f.events.includes('kcmc:published'), false); console.log('PASS: network failure never clears input or marks it published');
  f = fixture(); f.transport = async () => ({status: 200, redirected: true}); await f.send(); assert.match(f.status.textContent, /Sign in again/); assert.equal(f.fields.announcement_body.value, 'Exact unsaved words'); console.log('PASS: sign-in redirects retain input and produce a useful message');
})().catch(error => {console.error(error); process.exitCode = 1;});
