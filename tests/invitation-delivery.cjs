'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../KCMC-Connect-Phase6-Recreated/admin/invitation-delivery.js'),'utf8');
function harness(options={}) {
  let document;
  class Element {
    constructor(){this.dataset={};this.attributes={};this.events={};this.hidden=true;this.disabled=true;this.checked=false;this.value='';this.textContent='';}
    addEventListener(name,fn){this.events[name]=fn;}
    setAttribute(key,value){this.attributes[key]=String(value);}
    removeAttribute(key){delete this.attributes[key];if(key==='href')delete this.href;}
    hasAttribute(key){return key in this.attributes;}
    focus(){document.activeElement=this;}
    select(){this.selected=true;}
    fire(name){const e={prevented:false,preventDefault(){this.prevented=true;}};const result=this.events[name]?.(e);return {result,event:e};}
  }
  const confirm=new Element(),status=new Element(),manual=new Element(),message=new Element(),link=new Element(),recipient=new Element();
  link.value='https://bobsome1.com/kcmc-connect/member/activate.php?token='+'a'.repeat(64);
  message.value='Hi Dana Example,\nFor dana@example.invalid only:\n'+link.value;
  recipient.textContent='dana@example.invalid';
  const buttons=['message','link'].map(kind=>{const b=new Element();b.dataset.copyInvitation=kind;return b;});
  const gmail=new Element();gmail.dataset.composeUrl=options.gmailUrl||'https://mail.google.com/mail/?view=cm&fs=1&to=dana%40example.invalid&su=Invitation';gmail.attributes['data-invite-gmail']='';
  const mail=new Element();mail.dataset.composeUrl=options.mailUrl||'mailto:dana%40example.invalid?subject=Invitation';
  const controls=[new Element(),new Element(),new Element()];
  const mapping={'[data-invite-confirm]':confirm,'[data-invite-status]':status,'[data-invite-manual]':manual,'[data-invite-message]':message,'[data-invite-link]':link,'[data-invite-email]':recipient};
  const root={querySelector:s=>mapping[s]||null,querySelectorAll:s=>s==='[data-copy-invitation]'?buttons:s==='[data-compose-url]'?[gmail,mail]:controls};
  const calls=[];
  const navigator=options.noClipboard?{}:{clipboard:{writeText:async text=>{calls.push(text);return options.write?.(text);}}};
  document={activeElement:null,baseURI:'https://bobsome1.com/kcmc-connect/admin/users.php',querySelector:()=>options.noRoot?null:root};
  vm.runInNewContext(source,{document,navigator,window:{isSecureContext:!options.insecure},URL});
  const check=(value=true)=>{confirm.checked=value;confirm.fire('change');};
  const click=async(index=0)=>{const x=buttons[index].fire('click');await x.result;return x.event;};
  return {confirm,status,manual,message,link,recipient,buttons,gmail,mail,controls,calls,document,check,click};
}
test('no clipboard write or compose href before explicit recipient check',()=>{
 const h=harness();assert.deepEqual(h.calls,[]);assert.ok(h.buttons.every(b=>b.disabled));assert.equal(h.gmail.href,undefined);
});
test('recipient confirmation enables controls and uses only fixed compose destinations',()=>{
 const h=harness();h.check();assert.ok(h.buttons.every(b=>!b.disabled));assert.match(h.gmail.href,/^https:\/\/mail.google.com\//);assert.doesNotMatch(h.gmail.href,/token|body=/);
});
test('unsafe compose destinations never become active links',()=>{
 const h=harness({gmailUrl:'javascript:alert(1)',mailUrl:'https://evil.invalid/compose'});h.check();assert.equal(h.gmail.href,undefined);assert.equal(h.mail.href,undefined);assert.equal(h.gmail.attributes['aria-disabled'],'true');assert.equal(h.mail.attributes['aria-disabled'],'true');
});
test('disabled copy and compose clicks do nothing',async()=>{
 const h=harness();await h.click();assert.deepEqual(h.calls,[]);assert.equal(h.gmail.fire('click').event.prevented,true);
});
test('copy email writes the exact recipient-bound message only after click',async()=>{
 const h=harness();h.check();await h.click();assert.deepEqual(h.calls,[h.message.value]);assert.match(h.status.textContent,/Nothing has been sent/);
});
test('copy link writes only that invitation URL',async()=>{
 const h=harness();h.check();await h.click(1);assert.deepEqual(h.calls,[h.link.value]);assert.match(h.status.textContent,/dana@example.invalid/);
});
test('copy uses original validated card, not subsequently edited fields',async()=>{
 const h=harness(),expected=h.message.value;h.check();h.message.value='WRONG RECIPIENT';h.link.value='https://evil.invalid/';await h.click();assert.deepEqual(h.calls,[expected]);
});
for(const mode of ['missing','denied','insecure'])test(`${mode} clipboard exposes and focuses a manual-copy fallback`,async()=>{
 const h=harness({noClipboard:mode==='missing',insecure:mode==='insecure',write:()=>{throw new Error('PRIVATE_ERROR');}});
 h.check();await h.click();assert.equal(h.manual.open,true);assert.equal(h.document.activeElement,h.message);assert.equal(h.message.selected,true);assert.doesNotMatch(h.status.textContent,/PRIVATE_ERROR/);assert.equal(h.buttons[0].disabled,false);
});
test('overlapping clicks cannot create competing clipboard writes',async()=>{
 let done;const h=harness({write:()=>new Promise(resolve=>{done=resolve;})});h.check();const first=h.click();await h.click(1);assert.equal(h.calls.length,1);assert.equal(h.gmail.href,undefined);done();await first;assert.equal(h.buttons[0].disabled,false);
});
test('unchecking the recipient disables every delivery control',()=>{
 const h=harness();h.check();h.check(false);assert.ok(h.buttons.every(b=>b.disabled));assert.equal(h.gmail.href,undefined);assert.equal(h.mail.href,undefined);
});
test('Gmail click never sends, copies or claims delivery',()=>{
 const h=harness();h.check();h.gmail.fire('click');assert.deepEqual(h.calls,[]);assert.match(h.status.textContent,/cannot confirm delivery/);assert.match(h.status.textContent,/full invitation email/);
});
test('successful message copy followed by Gmail gives paste instructions',async()=>{
 const h=harness();h.check();await h.click();h.gmail.fire('click');assert.match(h.status.textContent,/paste the copied email/);assert.match(h.status.textContent,/To: dana@example.invalid/);
});
test('copying just a link cancels copied-full-email status',async()=>{
 const h=harness();h.check();await h.click();await h.click(1);h.gmail.fire('click');assert.match(h.status.textContent,/full invitation email/);
});
test('other email app explains failure without claiming a send',()=>{
 const h=harness();h.check();h.mail.fire('click');assert.match(h.status.textContent,/If nothing opens, use Open Gmail/);assert.match(h.status.textContent,/cannot confirm delivery/);
});
test('pages without an invitation card initialize safely',()=>{assert.doesNotThrow(()=>harness({noRoot:true}));});
