'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'KCMC-Connect-Phase6-Recreated/app.js'),'utf8');

test('install keyboard handler exits when the dialog is absent',()=>{
  assert.match(source,/if\(!installSheet\|\|installSheet\.hidden\)return;/);
  assert.doesNotMatch(source,/if\(installSheet\?\.hidden\)return;/);
});

test('preferred-service storage failures are contained',()=>{
  assert.match(source,/try\{preferred\.value=localStorage\.getItem\('kcmcPreferredService'\)\|\|'';\}catch\(_\)\{preferred\.value='';\}/);
  assert.match(source,/addEventListener\('change',\(\)=>\{try\{localStorage\.setItem\('kcmcPreferredService',preferred\.value\);\}catch\(_\)\{\}\}\)/);
});

test('service worker registration remains after optional preference setup',()=>{
  const preferenceIndex=source.indexOf("const preferred=document.getElementById('preferredService')");
  const registrationIndex=source.indexOf("navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'})");
  assert.ok(preferenceIndex>=0,'preferred-service setup is missing');
  assert.ok(registrationIndex>preferenceIndex,'service worker registration must remain after guarded optional storage setup');
});
