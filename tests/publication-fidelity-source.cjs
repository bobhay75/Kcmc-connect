#!/usr/bin/env node
// Execute exact editor functions with synthetic DOM and deferred fetch dependencies.
// Chromium plus actual PHP validator acceptance lives in publication-fidelity-browser.py.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const args=process.argv.slice(2);
function option(name,fallback){const index=args.indexOf(name);return index<0?fallback:args[index+1];}
const sourcePath=option('--source',path.join(__dirname,'../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php'));
const selectedCase=option('--case','all');
assert(['all','black','postcard','upload'].includes(selectedCase),'Unknown regression case');
const source=fs.readFileSync(sourcePath,'utf8');
function exact(start){
 const begin=source.indexOf(start);assert(begin>=0,'Missing exact source: '+start);
 const open=source.indexOf('{',begin);let depth=0,quote=null,escaped=false;
 for(let i=open;i<source.length;i++){
  const c=source[i];
  if(quote){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c===quote)quote=null;}
  else if(c==='"'||c==="'"||c==='`')quote=c;
  else if(c==='{')depth++;
  else if(c==='}'&&--depth===0)return source.slice(begin,i+1);
 }
 throw new Error('Unbalanced exact function: '+start);
}
const names=['applyPage','syncProps','rgbToHex','publicationText','itemData','currentProjectName',
 'currentPageData','commitCurrentPage','updatePageControls','renderPageData','showPage',
 'resetPagesFromCanvas','serialize','restoreItem','template','loadProject','addSharedMediaToCanvas'];
if(source.includes('function publicationFill('))names.push('publicationFill');
const declarations=names.map(name=>exact('function '+name+'(')).join('\n');
const handlers=["document.getElementById('newBtn').onclick=","document.getElementById('duplicateBtn').onclick=",
 'addPage.onclick=','duplicatePage.onclick=','deletePage.onclick=','imagePicker.onchange=async'];
const snippets=declarations+'\n'+handlers.map(start=>exact(start)+';').join('\n');
const sizes=source.match(/^const inch=96,sizes=.*;$/m);assert(sizes,'Missing actual page dimensions');

function harness(){
 const env={canvas:[],status:'Ready',requests:[],library:[],refreshes:0};
 const ids=['projectName','newBtn','duplicateBtn','pageIndicator','prevPage','nextPage','addPage','duplicatePage',
  'deletePage','pageSize','orientation','imagePicker','fontFamily','fontSize','textColor','fillColor',
  'borderColor','borderWidth','opacity'];
 const fields=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false}]));
 fields.projectName.value='Original publication';fields.pageSize.value='letter';fields.orientation.value='portrait';
 const page={style:{},querySelectorAll:()=>env.canvas};
 Object.defineProperty(page,'innerHTML',{get:()=>'',set:()=>{env.canvas=[];}});
 const node=(tag)=>({nodeType:1,tagName:tag.toUpperCase(),childNodes:[],alt:'',src:'',
  classList:{contains:()=>false},getAttribute(name){return this[name]||'';}});
 function makeItem(type,x=80,y=80,w=300,h=80){
  const el={dataset:{type},style:{left:x+'px',top:y+'px',width:w+'px',height:h+'px'},
   offsetWidth:w,offsetHeight:h,childNodes:[],classList:{contains:()=>false},
   querySelector:selector=>selector==='img'?el.childNodes.find(n=>n.tagName==='IMG')||null:null,
   insertBefore(n,before){const i=el.childNodes.indexOf(before);el.childNodes.splice(i<0?0:i,0,n);}};
  const handle={nodeType:1,tagName:'SPAN',childNodes:[],classList:{contains:kind=>kind==='handle'}};
  el.childNodes.push(handle);
  Object.defineProperty(el,'firstChild',{get:()=>el.childNodes[0]});
  Object.defineProperty(el,'innerText',{set(value){el.childNodes=[textNode(value,el),handle];}});
  env.canvas.push(el);return el;
 }
 function textNode(value,owner){return {nodeType:3,nodeValue:value,remove(){owner.childNodes.splice(owner.childNodes.indexOf(this),1);}};}
 const document={getElementById:id=>fields[id],createElement:node,
  createTextNode:value=>({nodeType:3,nodeValue:value})};
 function rgb(value,fallback){
  if(/^#[a-f\d]{6}$/i.test(value||''))return 'rgb('+[1,3,5].map(i=>parseInt(value.slice(i,i+2),16)).join(', ')+')';
  return value||fallback;
 }
 const context=vm.createContext({env,fields,page,makeItem,document,JSON,Error,Promise,console,
  FormData:class{constructor(){this.fields=[];}append(key,value){this.fields.push([key,value]);}},
  getComputedStyle:el=>({fontFamily:el.style.fontFamily||'Arial',fontSize:el.style.fontSize||'24px',
   fontWeight:el.style.fontWeight||'400',fontStyle:el.style.fontStyle||'normal',textAlign:el.style.textAlign||'left',
   color:rgb(el.style.color,'rgb(23, 50, 76)'),backgroundColor:rgb(el.style.background,'rgba(0, 0, 0, 0)'),
   borderColor:rgb(el.style.borderColor,'rgb(23, 50, 76)'),borderWidth:el.style.borderWidth||'0px',opacity:el.style.opacity||'1'}),
  fetch:(url,options)=>new Promise((resolve,reject)=>{assert.equal(url,'/synthetic/media');env.requests.push({options,resolve,reject});})});
 vm.runInContext(`
  let selected=null,projectId='pub_original',projectGeneration=0,canvasGeneration=0,currentPageIndex=0,pageState=[];
  const mediaEndpoint='/synthetic/media',csrf='fixture-csrf';
  const pageSize=fields.pageSize,orientation=fields.orientation,imagePicker=fields.imagePicker;
  const fontFamily=fields.fontFamily,fontSize=fields.fontSize,textColor=fields.textColor,fillColor=fields.fillColor;
  const borderColor=fields.borderColor,borderWidth=fields.borderWidth,opacity=fields.opacity;
  const prevPage=fields.prevPage,nextPage=fields.nextPage,addPage=fields.addPage,duplicatePage=fields.duplicatePage,deletePage=fields.deletePage;
  ${sizes[0]}
  function setStatus(value){env.status=value}
  function clearSelection(){selected=null}
  function recordHistory(){}
  function resetHistory(){}
  async function renderSharedMedia(){env.refreshes++}
  ${snippets}
  template('flyer');
  globalThis.readState=()=>({projectId,projectGeneration,canvasGeneration,currentPageIndex,pages:serialize().pages});
 `,context);
 const run=code=>vm.runInContext(code,context);
 return {env,fields,run,state:()=>JSON.parse(JSON.stringify(run('readState()'))),
  upload:()=>fields.imagePicker.onchange({target:{files:[{name:'synthetic.png'}]}}),
  reply:(ok=true)=>{const request=env.requests.at(-1);if(ok)env.library.push('pubmedia_'+'a'.repeat(24));
   request.resolve({ok,json:async()=>ok?{ok:true,media:{id:env.library.at(-1),label:'Synthetic photo'}}:{ok:false,error:'Synthetic upload failure'}});},
  reject:()=>env.requests.at(-1).reject(new Error('Synthetic network failure'))};
}

function black(){
 const h=harness();h.run("page.innerHTML='';globalThis.shape=makeItem('shape');shape.style.background='#000000';selected=shape;syncProps()");
 assert.equal(h.fields.fillColor.value,'#000000','Properties panel changed opaque black to white');
 assert.equal(h.run('itemData(shape).fill'),'#000000','Opaque black serialized as white');
 h.run("shape.style.background='rgba(0, 0, 0, 0)'");
 assert.equal(h.run('itemData(shape).fill'),'#ffffff','Transparent default changed');
 h.run("shape.style.background='#123456'");
 assert.equal(h.run('itemData(shape).fill'),'#123456','Ordinary fill changed');
 console.log('PASS: actual properties/serialization distinguish black, transparency and ordinary fills');
}
function postcard(){
 const h=harness();h.run("template('postcard')");
 assert.equal(h.fields.orientation.value,'landscape');
 assert.equal(h.run('page.style.width'),'576px','Postcard landscape width must be 6 inches');
 assert.equal(h.run('page.style.height'),'384px','Postcard landscape height must be 4 inches');
 assert(h.env.canvas.length>0);
 for(const el of h.env.canvas){assert(parseFloat(el.style.left)+parseFloat(el.style.width)<=576,'Template extends past postcard width');
  assert(parseFloat(el.style.top)+parseFloat(el.style.height)<=384,'Template extends past postcard height');}
 h.run("orientation.value='portrait';applyPage()");
 assert.equal(h.run('page.style.width'),'384px');assert.equal(h.run('page.style.height'),'576px');
 console.log('PASS: actual postcard template fits 6×4 landscape; portrait remains 4×6');
}
async function upload(){
 for(const action of ['Same','New','Load','Duplicate','Page','AddPage','DuplicatePage','DeletePage','Template']){
  for(const response of ['success','server-error','network-error']){
   const h=harness();
   if(action==='Page'||action==='DeletePage')h.run('addPage.onclick();showPage(0)');
   const pending=h.upload();assert.equal(h.env.requests.length,1);
   if(action==='New')h.fields.newBtn.onclick();
   if(action==='Duplicate')h.fields.duplicateBtn.onclick();
   if(action==='Load')h.run("loadProject({id:'pub_other',name:'Other publication',pages:[{pageSize:'half',orientation:'landscape',items:[]}]})");
   if(action==='Page')h.run('showPage(1)');
   if(action==='AddPage')h.fields.addPage.onclick();
   if(action==='DuplicatePage')h.fields.duplicatePage.onclick();
   if(action==='DeletePage')h.fields.deletePage.onclick();
   if(action==='Template')h.run("template('study')");
   const before={state:h.state(),status:h.env.status,name:h.fields.projectName.value};
   if(response==='network-error')h.reject();else h.reply(response==='success');
   await pending;
   const after=h.state();
   assert.equal(after.projectId,before.state.projectId,action+': upload changed project ID');
   assert.equal(h.fields.projectName.value,before.name,action+': upload changed project name');
   if(action==='Same'&&response==='success'){
    assert.equal(h.env.canvas.filter(item=>item.dataset.type==='image').length,1,'Current canvas lost its normal photo insertion');
    assert.equal(h.env.status,'Photo uploaded and added');
   }else if(action!=='Same'){
    assert.deepEqual(after.pages,before.state.pages,action+': stale upload changed publication/page contents');
    assert.equal(h.env.status,before.status,action+': stale upload overwrote current status');
   }else assert.equal(h.env.status,response==='server-error'?'Synthetic upload failure':'Synthetic network failure');
   assert.equal(h.fields.imagePicker.value,'');
   if(response==='success')assert.equal(h.env.refreshes,1,'Successful stale upload did not refresh shared library');
   console.log('PASS:',action,response,'retains context and cleanup'+(response==='success'?'; successful upload remains reusable':''));
  }
 }
}
(async()=>{
 if(selectedCase==='all'||selectedCase==='black')black();
 if(selectedCase==='all'||selectedCase==='postcard')postcard();
 if(selectedCase==='all'||selectedCase==='upload')await upload();
 console.log('Exact editor fidelity checks passed; synthetic dependencies, browser/PHP acceptance remains separate.');
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
