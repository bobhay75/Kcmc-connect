<?php
require_once __DIR__ . '/../lib/bootstrap.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KCMC Publication Designer</title>
<style>
:root{--ink:#17324c;--paper:#fff;--line:#d7e0e5;--gold:#8b6a2d;--bg:#eef2f4}
*{box-sizing:border-box}body{margin:0;font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--ink)}
button,input,select,textarea{font:inherit}.shell{min-height:100vh;display:grid;grid-template-rows:auto 1fr}
.topbar{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 16px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.brand{display:flex;gap:10px;align-items:center}.brand strong{font-size:1.05rem}.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn{border:1px solid #b9c6ce;background:#fff;color:var(--ink);padding:9px 12px;border-radius:9px;font-weight:700;cursor:pointer}.btn.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
.workspace{display:grid;grid-template-columns:250px minmax(0,1fr) 280px;min-height:0}.panel{background:#fff;border-right:1px solid var(--line);padding:14px;overflow:auto}.panel.right{border-right:0;border-left:1px solid var(--line)}
.panel h2{font-size:1rem;margin:4px 0 12px}.field{display:grid;gap:5px;margin:0 0 12px}.field input,.field select,.field textarea{width:100%;padding:8px;border:1px solid #bdc9d0;border-radius:8px;background:#fff;color:#17324c}
.templates{display:grid;gap:8px}.template{border:1px solid #cfd8dd;border-radius:10px;padding:10px;text-align:left;background:#fff;cursor:pointer}.template:hover{background:#f5f8fa}.media-card{display:grid;grid-template-columns:56px 1fr;gap:9px;align-items:center}.media-card img{width:56px;height:46px;object-fit:cover;border-radius:7px;background:#e9eef2}
.canvas-wrap{overflow:auto;padding:28px;display:grid;place-items:start center;background:linear-gradient(45deg,#e7ecef 25%,transparent 25%),linear-gradient(-45deg,#e7ecef 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#e7ecef 75%),linear-gradient(-45deg,transparent 75%,#e7ecef 75%);background-size:24px 24px;background-position:0 0,0 12px,12px -12px,-12px 0}
.page{position:relative;background:#fff;box-shadow:0 8px 26px rgba(0,0,0,.16);transform-origin:top center}
.item{position:absolute;min-width:40px;min-height:28px;border:0 solid transparent;overflow:hidden}.item.selected{box-shadow:0 0 0 2px rgba(30,111,168,.16)}.item[contenteditable="true"]:focus{outline:none}
.item[data-type="text"]{white-space:pre-wrap;padding:6px}
.item img{width:100%;height:100%;object-fit:cover;display:block}.handle{position:absolute;width:16px;height:16px;background:#1e6fa8;border:2px solid #fff;border-radius:50%;right:2px;bottom:2px;cursor:nwse-resize;touch-action:none;user-select:none;display:none}.selected .handle{display:block}
.toolbar{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:12px}.page-nav{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center;margin:8px 0}.page-nav .small{text-align:center}.print-pages{display:none}.status{font-size:.85rem;color:#607080}.small{font-size:.82rem;color:#607080}.hidden{display:none!important}
@media(max-width:900px){.workspace{grid-template-columns:1fr}.panel.right{border-left:0;border-top:1px solid var(--line)}.panel{border-right:0;border-bottom:1px solid var(--line)}}
@media print{body{background:#fff}.topbar,.panel,.canvas-wrap{display:none!important}.workspace{display:block}.print-pages{display:block}.print-pages .page{box-shadow:none;margin:0 auto;transform:none!important;break-after:page;page-break-after:always}.print-pages .page:last-child{break-after:auto;page-break-after:auto}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar">
  <div class="brand"><a href="<?=kcmc_h(kcmc_url('admin/'))?>" class="btn">← Publishing Desk</a><strong>Publication Designer</strong><span class="status" id="status" role="status" aria-live="polite" aria-atomic="true">Ready</span></div>
  <div class="actions">
    <label class="field" style="margin:0;min-width:220px"><span class="small">Project name</span><input id="projectName" maxlength="80" value="Untitled publication" aria-label="Project name"></label>
    <button class="btn" id="newBtn">New</button>
    <button class="btn" id="undoBtn" type="button" disabled title="Undo (Ctrl/Cmd+Z)">Undo</button>
    <button class="btn" id="redoBtn" type="button" disabled title="Redo (Ctrl/Cmd+Shift+Z or Ctrl+Y)">Redo</button>
    <button class="btn" id="duplicateBtn">Duplicate</button>
    <button class="btn" id="saveBtn">Save</button>
    <button class="btn primary" id="printBtn">Print / Save PDF</button>
  </div>
</header>
<div class="workspace">
<aside class="panel">
  <h2>Templates</h2>
  <div class="templates" id="templates">
    <button class="template" data-template="flyer"><strong>Event Flyer</strong><br><span class="small">Bold title, image, details</span></button>
    <button class="template" data-template="bulletin"><strong>Sunday Bulletin</strong><br><span class="small">Service-ready one-page layout</span></button>
    <button class="template" data-template="newsletter"><strong>Newsletter</strong><br><span class="small">Two-column update sheet</span></button>
    <button class="template" data-template="postcard"><strong>Invitation / Postcard</strong><br><span class="small">Simple front-side invite</span></button>
    <button class="template" data-template="memorial"><strong>Memorial Program</strong><br><span class="small">Respectful service program</span></button>
    <button class="template" data-template="study"><strong>Bible Study Handout</strong><br><span class="small">Title, scripture, notes</span></button>
  </div>
  <hr>
  <h2>Add</h2>
  <div class="toolbar">
    <button class="btn" id="addText">Text</button>
    <button class="btn" id="addShape">Shape</button>
    <button class="btn" id="addImage">Photo</button>
    <button class="btn" id="deleteItem">Delete</button>
  </div>
  <input class="hidden" type="file" id="imagePicker" accept="image/jpeg,image/png,image/webp">
  <h2>KCMC Photos</h2>
  <div class="templates" id="assetLibrary">
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-congregation-gathering.jpg'))?>" data-alt="People seated around tables facing the KCMC worship stage"><strong>Congregation gathering</strong><br><span class="small">Church, kids &amp; family photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-family-outdoor-event.jpg'))?>" data-alt="Children and adults enjoying balloons and an inflatable slide at a Kimberling City outdoor event"><strong>Outdoor family event</strong><br><span class="small">Church, kids &amp; family photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-bridge-logo.jpg'))?>" data-alt="Kimberling City Methodist Church logo with a blue bridge and black cross"><strong>Bridge and cross logo</strong><br><span class="small">Bridge artwork</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-kids-safari.jpg'))?>" data-alt="Children seated in a decorated safari cart inside KCMC"><strong>Kids safari activity</strong><br><span class="small">Church, kids &amp; family photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-kids-game-room.jpg'))?>" data-alt="Children playing foosball and other table games in the KCMC game room"><strong>Kids game room</strong><br><span class="small">Church, kids &amp; family photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-kids-summer-group.jpg'))?>" data-alt="Children and adults gathered in front of the stage for the KCMC summer kick-off"><strong>Summer kids and family group</strong><br><span class="small">Church, kids &amp; family photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-church-wordmark.jpg'))?>" data-alt="Kimberling City United Methodist Church wordmark over a church exterior photo, with Loving God Loving Others"><strong>Church photo wordmark</strong><br><span class="small">Publication / branding only</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-bridge-wordmark.png'))?>" data-alt="Kimberling City Methodist Church bridge and cross logo over a sunset bridge photograph"><strong>Bridge photo wordmark</strong><br><span class="small">Bridge artwork</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-bridge-logo-composite.png'))?>" data-alt="Sunset bridge photograph with the Kimberling City Methodist Church logo inset at lower right"><strong>Bridge photo with inset logo</strong><br><span class="small">Bridge artwork</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-building-2024.webp'))?>"><strong>Church Exterior</strong><br><span class="small">KCMC building</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-worship-2017.webp'))?>"><strong>Worship</strong><br><span class="small">Church worship photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-ministry-group.jpg'))?>"><strong>Church Family</strong><br><span class="small">Ministry group photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-stage-2014.webp'))?>"><strong>Sanctuary Stage</strong><br><span class="small">KCMC stage photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/trunk-or-treat-2026.webp'))?>"><strong>Trunk or Treat</strong><br><span class="small">Approved event graphic</span></button>
  </div>
  <h2>Shared Photos</h2>
  <p class="small">Use Photo above to upload a JPEG, PNG, or WEBP up to 5 MB. Uploaded church photos can be reused by authorized KCMC admins.</p>
  <div class="templates" id="sharedMediaLibrary"><span class="small">Loading shared photos…</span></div>
  <div class="field"><label>Page size<select id="pageSize"><option value="letter">Letter 8.5×11</option><option value="half">Half sheet 5.5×8.5</option><option value="postcard">Postcard 6×4</option></select></label></div>
  <div class="field"><label>Orientation<select id="orientation"><option value="portrait">Portrait</option><option value="landscape">Landscape</option></select></label></div>
  <h2>Pages</h2>
  <div class="page-nav"><button class="btn" id="prevPage" aria-label="Previous page">←</button><span class="small" id="pageIndicator">Page 1 of 1</span><button class="btn" id="nextPage" aria-label="Next page">→</button></div>
  <div class="toolbar">
    <button class="btn" id="addPage">Add page</button>
    <button class="btn" id="duplicatePage">Duplicate page</button>
    <button class="btn" id="deletePage">Delete page</button>
  </div>
  <p class="small">Up to 12 pages per publication. Projects and uploaded church photos are shared between authorized KCMC admins.</p>
</aside>
<main class="canvas-wrap">
  <div id="page" class="page" aria-label="publication canvas"></div>
</main>
<aside class="panel right">
  <h2>Selected item</h2>
  <div id="noSelection" class="small">Select an item on the page.</div>
  <div id="properties" class="hidden">
    <div class="field"><label>Font<select id="fontFamily"><option>Arial</option><option>Arial Narrow</option><option>Georgia</option><option>Times New Roman</option><option>Verdana</option></select></label></div>
    <div class="field"><label>Font size<input id="fontSize" type="number" min="8" max="120" value="24"></label></div>
    <div class="toolbar">
      <button class="btn" id="boldBtn"><strong>B</strong></button>
      <button class="btn" id="italicBtn"><em>I</em></button>
      <button class="btn" data-align="left">Left</button>
      <button class="btn" data-align="center">Center</button>
      <button class="btn" data-align="right">Right</button>
    </div>
    <div class="field"><label>Text color<input id="textColor" type="color" value="#17324c"></label></div>
    <div class="field"><label>Fill color<input id="fillColor" type="color" value="#ffffff"></label></div>
    <div class="field"><label>Border color<input id="borderColor" type="color" value="#17324c"></label></div>
    <div class="field"><label>Border width<input id="borderWidth" type="number" min="0" max="12" value="0"></label></div>
    <div class="field"><label>Opacity<input id="opacity" type="range" min="10" max="100" value="100"></label></div>
    <h3 style="margin:14px 0 8px">Arrange</h3>
    <div class="toolbar">
      <button class="btn" id="duplicateItemBtn" type="button">Duplicate object</button>
      <button class="btn" id="bringFrontBtn" type="button">Bring to front</button>
      <button class="btn" id="bringForwardBtn" type="button">Bring forward</button>
      <button class="btn" id="sendBackwardBtn" type="button">Send backward</button>
      <button class="btn" id="sendBackBtn" type="button">Send to back</button>
    </div>
  </div>
  <hr>
  <h2>Saved projects</h2>
  <div id="savedList" class="templates"></div>
</aside>
</div>
<div id="printPages" class="print-pages" aria-hidden="true"></div>
</div>
<script>
(()=>{
const page=document.getElementById('page'),status=document.getElementById('status'),saveButton=document.getElementById('saveBtn'),undoButton=document.getElementById('undoBtn'),redoButton=document.getElementById('redoBtn');
const projectEndpoint=<?=json_encode(kcmc_url('admin/publication-projects.php'), JSON_UNESCAPED_SLASHES)?>;
const mediaEndpoint=<?=json_encode(kcmc_url('admin/publication-media.php'), JSON_UNESCAPED_SLASHES)?>;
const csrf=<?=json_encode(kcmc_csrf(), JSON_UNESCAPED_SLASHES)?>;
const pageSize=document.getElementById('pageSize'),orientation=document.getElementById('orientation');
const imagePicker=document.getElementById('imagePicker'),sharedMediaLibrary=document.getElementById('sharedMediaLibrary');
const props=document.getElementById('properties'),noSel=document.getElementById('noSelection');
let selected=null,drag=null,projectId=null,currentPageIndex=0,pageState=[],projectGeneration=0,canvasGeneration=0,saveInFlight=false,undoStack=[],redoStack=[],historyRestoring=false;
const inch=96,sizes={letter:[8.5,11],half:[5.5,8.5],postcard:[4,6]};
function setStatus(t){status.textContent=t}
function updateHistoryButtons(){undoButton.disabled=undoStack.length===0;redoButton.disabled=redoStack.length===0}
function updateArrangeButtons(){
 const disabled=!selected;
 for(const id of ['duplicateItemBtn','bringFrontBtn','bringForwardBtn','sendBackwardBtn','sendBackBtn']) document.getElementById(id).disabled=disabled;
}
function snapshotDocument(){
 commitCurrentPage();
 return JSON.stringify({projectName:currentProjectName(),currentPageIndex,pageState});
}
function recordHistory(){
 if(historyRestoring)return;
 const snapshot=snapshotDocument();
 if(undoStack[undoStack.length-1]!==snapshot)undoStack.push(snapshot);
 if(undoStack.length>60)undoStack.shift();
 redoStack=[];
 updateHistoryButtons();
}
function restoreHistory(snapshot,label){
 const state=JSON.parse(snapshot);
 historyRestoring=true;
 document.getElementById('projectName').value=String(state.projectName||'Untitled publication').slice(0,80);
 pageState=Array.isArray(state.pageState)&&state.pageState.length?state.pageState:[{pageSize:'letter',orientation:'portrait',items:[]}];
 currentPageIndex=Math.max(0,Math.min(Number(state.currentPageIndex)||0,pageState.length-1));
 renderPageData(pageState[currentPageIndex]);
 historyRestoring=false;
 updateHistoryButtons();
 setStatus(label);
}
function undo(){
 if(!undoStack.length)return;
 const current=snapshotDocument(),previous=undoStack.pop();
 redoStack.push(current);
 restoreHistory(previous,'Undo');
}
function redo(){
 if(!redoStack.length)return;
 const current=snapshotDocument(),next=redoStack.pop();
 undoStack.push(current);
 restoreHistory(next,'Redo');
}
function resetHistory(){undoStack=[];redoStack=[];updateHistoryButtons()}
function applyPage(target=page,sizeValue=pageSize.value,orientationValue=orientation.value){let [w,h]=sizes[sizeValue]||sizes.letter;if(orientationValue==='landscape')[w,h]=[h,w];target.style.width=(w*inch)+'px';target.style.height=(h*inch)+'px'}
function finishTextEdit(el){if(el?.dataset.type==='text'){el.classList.remove('editing');el.contentEditable='false';ensureItemHandle(el)}}
function clearSelection(){if(selected){finishTextEdit(selected);selected.classList.remove('selected')}selected=null;drag=null;props.classList.add('hidden');noSel.classList.remove('hidden');updateArrangeButtons()}
// A template or Select All can replace text children, including the old handle.
// Recreate it on selection/input; delegated events never retain a detached handle.
function ensureItemHandle(el){
 let handle=el.querySelector(':scope > .handle');
 if(!handle){handle=document.createElement('span');handle.className='handle';el.appendChild(handle)}
 handle.contentEditable='false';handle.setAttribute('aria-hidden','true');return handle;
}
function select(el){if(selected!==el)clearSelection();selected=el;if(!el.classList.contains('editing'))ensureItemHandle(el);el.classList.add('selected');props.classList.remove('hidden');noSel.classList.add('hidden');syncProps();updateArrangeButtons()}
function beginTextEdit(el){
 if(el.dataset.type!=='text')return;
 recordHistory();select(el);drag=null;el.querySelectorAll('.handle').forEach(handle=>handle.remove());el.contentEditable='true';el.classList.add('editing');el.focus({preventScroll:true});
 const range=document.createRange();range.selectNodeContents(el);range.collapse(false);
 const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
 setStatus('Editing text — press Escape when finished.');
}
function makeItem(type,x=80,y=80,w=300,h=80){const el=document.createElement('div');el.className='item';el.dataset.type=type;Object.assign(el.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px'});if(type==='text'){el.contentEditable='true';el.innerText='Double-click and type';el.style.fontFamily='Arial';el.style.fontSize='28px';el.style.padding='6px'}else if(type==='shape'){el.style.background='#e9eef2';el.style.border='2px solid #17324c'}const handle=document.createElement('span');handle.className='handle';el.appendChild(handle);wire(el,handle);page.appendChild(el);select(el);return el}
function wire(el){
 el.tabIndex=0;if(el.dataset.type==='text'){el.contentEditable='false';el.setAttribute('aria-label','Text box — double-click or press Enter to edit')}
 el.addEventListener('focus',()=>select(el));
 el.addEventListener('mousedown',e=>{
  if(e.button!==0)return;
  const resizing=e.target instanceof Element&&e.target.closest('.handle');
  select(el);
  // Native mouse selection/caret placement must remain available while typing.
  if(!resizing&&el.classList.contains('editing'))return;
  const r=el.getBoundingClientRect(),pr=page.getBoundingClientRect();
  drag=resizing?{mode:'resize',el,sx:e.clientX,sy:e.clientY,sw:r.width,sh:r.height,history:false}:{mode:'move',el,dx:e.clientX-r.left,dy:e.clientY-r.top,pr,history:false};
  e.preventDefault();el.focus({preventScroll:true});
 });
 el.addEventListener('dblclick',e=>{if(!(e.target instanceof Element&&e.target.closest('.handle'))&&el.dataset.type==='text'){e.preventDefault();beginTextEdit(el)}});
 el.addEventListener('keydown',e=>{
  if(e.key==='Escape'){e.preventDefault();finishTextEdit(el);drag=null;setStatus('Text finished — drag the box to move it.');return}
  if(!el.classList.contains('editing')&&(e.key==='Enter'||e.key==='F2')&&el.dataset.type==='text'){e.preventDefault();beginTextEdit(el);return}
  if(!el.classList.contains('editing')&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
   e.preventDefault();recordHistory();const step=e.shiftKey?10:1,axis=['ArrowLeft','ArrowRight'].includes(e.key)?'left':'top';
   el.style[axis]=Math.max(0,(parseFloat(el.style[axis])||0)+(['ArrowLeft','ArrowUp'].includes(e.key)?-step:step))+'px';
  }
 });
 el.addEventListener('input',()=>{if(!el.classList.contains('editing'))ensureItemHandle(el)});
 el.addEventListener('blur',()=>finishTextEdit(el));
 // Pasted text remains literal; no external images or HTML enter the editor.
 el.addEventListener('paste',e=>{
  if(el.dataset.type!=='text')return;e.preventDefault();
  if(!el.classList.contains('editing'))return;
  const text=e.clipboardData?.getData('text/plain')||'',selection=window.getSelection();
  if(!selection.rangeCount||!el.contains(selection.anchorNode)||!el.contains(selection.focusNode))return;
  const range=selection.getRangeAt(0);range.deleteContents();const node=document.createTextNode(text);range.insertNode(node);range.setStartAfter(node);range.collapse(true);selection.removeAllRanges();selection.addRange(range);
 });
 el.addEventListener('drop',e=>{if(el.dataset.type==='text')e.preventDefault()});
}
document.addEventListener('mousemove',e=>{if(!drag)return;if(!drag.history){recordHistory();drag.history=true}if(drag.mode==='move'){const x=Math.max(0,e.clientX-drag.pr.left-drag.dx),y=Math.max(0,e.clientY-drag.pr.top-drag.dy);drag.el.style.left=x+'px';drag.el.style.top=y+'px'}else{drag.el.style.width=Math.max(40,drag.sw+e.clientX-drag.sx)+'px';drag.el.style.height=Math.max(28,drag.sh+e.clientY-drag.sy)+'px'}});
document.addEventListener('mouseup',()=>drag=null);page.addEventListener('mousedown',e=>{if(e.target===page)clearSelection()});
function syncProps(){if(!selected)return;const cs=getComputedStyle(selected);fontFamily.value=cs.fontFamily.replaceAll('"','').split(',')[0];fontSize.value=parseInt(cs.fontSize)||24;textColor.value=rgbToHex(cs.color);fillColor.value=publicationFill(cs.backgroundColor);borderColor.value=rgbToHex(cs.borderColor);borderWidth.value=parseInt(cs.borderWidth)||0;opacity.value=Math.round((parseFloat(cs.opacity)||1)*100)}
function rgbToHex(v){const m=v.match(/\d+/g);if(!m||m.length<3)return '#17324c';return '#'+m.slice(0,3).map(n=>(+n).toString(16).padStart(2,'0')).join('')}
function publicationFill(v){const alpha=v.match(/^rgba\([^)]*,\s*([\d.]+)\s*\)$/);return v==='transparent'||(alpha&&Number(alpha[1])===0)?'#ffffff':rgbToHex(v)}
function template(name){page.innerHTML='';clearSelection();pageSize.value=name==='postcard'?'postcard':'letter';orientation.value=name==='postcard'?'landscape':'portrait';applyPage();
 if(name==='flyer'){const h=makeItem('text',70,70,650,90);h.innerText='YOU ARE INVITED';h.style.fontSize='52px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',100,190,590,150);t.innerText='Event Name\nDate • Time • Location';t.style.textAlign='center';const b=makeItem('shape',100,390,590,260);b.style.background='#e9eef2'}
 if(name==='bulletin'){const h=makeItem('text',70,55,650,70);h.innerText='KIMBERLING CITY METHODIST CHURCH';h.style.fontSize='32px';h.style.fontWeight='700';h.style.textAlign='center';const l=makeItem('text',70,145,650,720);l.innerText='Welcome\n\nPrelude\nOpening Hymn\nPrayer\nScripture\nMessage\nOffering\nClosing Hymn\nBenediction';l.style.fontSize='22px'}
 if(name==='newsletter'){const h=makeItem('text',60,50,670,70);h.innerText='KCMC NEWS & NOTES';h.style.fontSize='40px';h.style.fontWeight='700';h.style.textAlign='center';const c1=makeItem('text',70,150,300,700);c1.innerText='FROM THE CHURCH\n\nAdd updates here.';const c2=makeItem('text',420,150,300,700);c2.innerText='COMING UP\n\nAdd events and announcements here.'}
 if(name==='postcard'){const h=makeItem('text',50,55,475,80);h.innerText='COME JOIN US';h.style.fontSize='42px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',65,160,445,130);t.innerText='Kimberling City Methodist Church\nSunday Worship\n8:00 • 9:15 • 10:30';t.style.textAlign='center'}
 if(name==='memorial'){const h=makeItem('text',90,70,610,85);h.innerText='A SERVICE OF REMEMBRANCE';h.style.fontSize='34px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',110,190,570,600);t.innerText='Name\nDates\n\nPrelude\nWelcome\nScripture\nRemembrances\nMessage\nPrayer\nClosing';t.style.textAlign='center';t.style.fontSize='22px'}
 if(name==='study'){const h=makeItem('text',70,55,650,70);h.innerText='BIBLE STUDY';h.style.fontSize='38px';h.style.fontWeight='700';const t=makeItem('text',70,150,650,720);t.innerText='Scripture:\n\nMain idea:\n\nNotes:\n\nQuestions:\n1.\n2.\n3.';t.style.fontSize='22px'}
 clearSelection();resetPagesFromCanvas();setStatus('Template loaded')}
// Serialize only plain text. BRs and editable block lines must survive without
// copying HTML or counting the resize handle as publication content.
function publicationText(root){
 const blocks=new Set(['DIV','P','LI','H1','H2','H3','H4','H5','H6','BLOCKQUOTE']);
 function children(parent){
  let text='',previousBlock=false,previousParagraph=false;
  for(const node of parent.childNodes){
   if(node.nodeType!==1&&node.nodeType!==3)continue;
   if(node.nodeType===1&&node.classList.contains('handle'))continue;
   const tag=node.nodeType===1?node.tagName:'',block=blocks.has(tag),paragraph=tag==='P';
   const value=node.nodeType===3?node.nodeValue:tag==='BR'?'\n':children(node);
   if(text&&(block||previousBlock)){
    const required=paragraph||previousParagraph?2:1;
    const trailing=(text.match(/\n*$/)||[''])[0].length;
    text+='\n'.repeat(Math.max(0,required-trailing));
   }
   text+=value;previousBlock=block;previousParagraph=paragraph;
  }
  return text;
 }
 return children(root);
}
function itemData(el){const cs=getComputedStyle(el),img=el.querySelector('img');return {
 type:el.dataset.type||'text',x:parseFloat(el.style.left)||0,y:parseFloat(el.style.top)||0,w:parseFloat(el.style.width)||el.offsetWidth,h:parseFloat(el.style.height)||el.offsetHeight,
 fontFamily:cs.fontFamily.replaceAll('"','').split(',')[0],fontSize:parseFloat(cs.fontSize)||24,fontWeight:cs.fontWeight==='700'||parseInt(cs.fontWeight)>=700?'700':'400',fontStyle:cs.fontStyle==='italic'?'italic':'normal',
 textAlign:['left','center','right'].includes(cs.textAlign)?cs.textAlign:'left',color:rgbToHex(cs.color),fill:publicationFill(cs.backgroundColor),
 borderColor:rgbToHex(cs.borderColor),borderWidth:parseFloat(cs.borderWidth)||0,opacity:parseFloat(cs.opacity)||1,
 ...(el.dataset.type==='text'?{text:publicationText(el)}:{ }),
 ...(el.dataset.type==='image'?(el.dataset.mediaId?{mediaId:el.dataset.mediaId,alt:img?.alt||'KCMC photo'}:{src:img?.getAttribute('src')||'',alt:img?.alt||'KCMC photo'}):{ })
}}
function currentProjectName(){return document.getElementById('projectName').value.trim().slice(0,80)||'Untitled publication'}
function currentPageData(){return {pageSize:pageSize.value,orientation:orientation.value,items:[...page.querySelectorAll('.item')].map(itemData)}}
function commitCurrentPage(){if(pageState.length===0)pageState=[currentPageData()];else pageState[currentPageIndex]=currentPageData()}
function updatePageControls(){const count=Math.max(1,pageState.length);document.getElementById('pageIndicator').textContent='Page '+(currentPageIndex+1)+' of '+count;prevPage.disabled=currentPageIndex<=0;nextPage.disabled=currentPageIndex>=count-1;deletePage.disabled=count<=1;addPage.disabled=count>=12;duplicatePage.disabled=count>=12}
function renderPageData(p){canvasGeneration++;pageSize.value=p?.pageSize||'letter';orientation.value=p?.orientation||'portrait';applyPage();page.innerHTML='';(p?.items||[]).forEach(restoreItem);clearSelection();updatePageControls()}
function showPage(index){commitCurrentPage();if(index<0||index>=pageState.length)return;currentPageIndex=index;renderPageData(pageState[index]);setStatus('Page '+(index+1)+' of '+pageState.length)}
function resetPagesFromCanvas(){canvasGeneration++;pageState=[currentPageData()];currentPageIndex=0;updatePageControls()}
function serialize(){commitCurrentPage();return {id:projectId,name:currentProjectName(),pages:pageState.map(p=>({pageSize:p.pageSize,orientation:p.orientation,items:p.items}))}}
function restoreItem(item){const el=makeItem(item.type,item.x,item.y,item.w,item.h);el.style.fontFamily=item.fontFamily||'Arial';el.style.fontSize=(item.fontSize||24)+'px';el.style.fontWeight=item.fontWeight||'400';el.style.fontStyle=item.fontStyle||'normal';el.style.textAlign=item.textAlign||'left';el.style.color=item.color||'#17324c';el.style.background=item.fill||'#ffffff';el.style.borderColor=item.borderColor||'#17324c';el.style.borderStyle=(item.borderWidth||0)>0?'solid':'none';el.style.borderWidth=(item.borderWidth||0)+'px';el.style.opacity=item.opacity??1;
 if(item.type==='text'){el.childNodes.forEach(n=>{if(!(n.nodeType===1&&n.classList?.contains('handle')))n.remove()});el.insertBefore(document.createTextNode(item.text||''),el.firstChild)}
 if(item.type==='image'){const img=document.createElement('img');if(item.mediaId){el.dataset.mediaId=item.mediaId;img.src=mediaEndpoint+'?id='+encodeURIComponent(item.mediaId)}else{img.src=item.src||''}img.alt=item.alt||'KCMC photo';el.insertBefore(img,el.firstChild)}
 return el}
async function save(){
 if(saveInFlight)return;
 const p=serialize(),generation=projectGeneration;
 saveInFlight=true;saveButton.disabled=true;setStatus('Saving…');
 try{
  const r=await fetch(projectEndpoint,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({...p,csrf})});
  const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'Save failed');
  if(generation===projectGeneration){projectId=j.project.id;setStatus('Saved for KCMC admins')}
  await renderSaved();
 }catch(err){if(generation===projectGeneration)setStatus(err.message||'Save failed')}
 finally{saveInFlight=false;saveButton.disabled=false}
}
function loadProject(p){projectGeneration++;projectId=p.id;document.getElementById('projectName').value=String(p.name||'Untitled publication').slice(0,80);const legacy={pageSize:p.pageSize||'letter',orientation:p.orientation||'portrait',items:Array.isArray(p.items)?p.items:[]};pageState=(Array.isArray(p.pages)&&p.pages.length?p.pages:[legacy]).slice(0,12).map(pg=>({pageSize:pg.pageSize||'letter',orientation:pg.orientation||'portrait',items:Array.isArray(pg.items)?pg.items:[]}));currentPageIndex=0;renderPageData(pageState[0]);resetHistory();setStatus('Loaded '+p.name+' • '+pageState.length+' page'+(pageState.length===1?'':'s'))}
async function renderSaved(){const box=document.getElementById('savedList');box.innerHTML='<span class="small">Loading…</span>';try{const r=await fetch(projectEndpoint,{credentials:'same-origin'}),j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'Could not load projects');box.innerHTML='';(j.projects||[]).forEach(p=>{const b=document.createElement('button');b.className='template';b.innerHTML='<strong>'+escapeHtml(p.name)+'</strong><br><span class="small">'+new Date(p.updated).toLocaleString()+'</span>';b.onclick=()=>loadProject(p);box.appendChild(b)});if(!(j.projects||[]).length)box.innerHTML='<span class="small">No shared projects yet.</span>'}catch(err){box.innerHTML='<span class="small">'+escapeHtml(err.message||'Could not load projects')+'</span>'}}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
document.getElementById('templates').addEventListener('click',e=>{const b=e.target.closest('[data-template]');if(b){recordHistory();template(b.dataset.template)}});
document.getElementById('addText').onclick=()=>{recordHistory();makeItem('text')};document.getElementById('addShape').onclick=()=>{recordHistory();makeItem('shape')};
function addSharedMediaToCanvas(media){recordHistory();const el=makeItem('image',80,80,320,220);el.dataset.mediaId=media.id;const img=document.createElement('img');img.src=media.url||mediaEndpoint+'?id='+encodeURIComponent(media.id);img.alt=media.label||'KCMC shared photo';el.insertBefore(img,el.firstChild);setStatus('Shared photo added')}
async function renderSharedMedia(){sharedMediaLibrary.innerHTML='<span class="small">Loading shared photos…</span>';try{const r=await fetch(mediaEndpoint,{credentials:'same-origin'}),j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'Could not load shared photos');sharedMediaLibrary.innerHTML='';for(const media of (j.media||[])){const b=document.createElement('button');b.type='button';b.className='template media-card';const img=document.createElement('img');img.src=media.url;img.alt='';const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=media.label||'Church photo';const small=document.createElement('span');small.className='small';small.textContent=(media.width||0)+'×'+(media.height||0)+' • '+Math.max(1,Math.round((media.bytes||0)/1024))+' KB';copy.append(strong,document.createElement('br'),small);b.append(img,copy);b.onclick=()=>addSharedMediaToCanvas(media);sharedMediaLibrary.appendChild(b)}if(!(j.media||[]).length)sharedMediaLibrary.innerHTML='<span class="small">No shared uploads yet.</span>'}catch(err){sharedMediaLibrary.innerHTML='<span class="small">'+escapeHtml(err.message||'Could not load shared photos')+'</span>'}}
document.getElementById('addImage').onclick=()=>imagePicker.click();
imagePicker.onchange=async e=>{const file=e.target.files[0];if(!file)return;const generation=projectGeneration,canvas=canvasGeneration,isCurrent=()=>generation===projectGeneration&&canvas===canvasGeneration;setStatus('Uploading photo…');const form=new FormData();form.append('csrf',csrf);form.append('photo',file);try{const r=await fetch(mediaEndpoint,{method:'POST',credentials:'same-origin',body:form}),j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'Upload failed');if(isCurrent())addSharedMediaToCanvas(j.media);await renderSharedMedia();if(isCurrent())setStatus('Photo uploaded and added')}catch(err){if(isCurrent())setStatus(err.message||'Upload failed')}finally{imagePicker.value=''}};
document.getElementById('assetLibrary').addEventListener('click',e=>{const b=e.target.closest('[data-asset]');if(!b)return;recordHistory();const el=makeItem('image',80,80,320,220);const img=document.createElement('img');img.src=b.dataset.asset;img.alt=b.dataset.alt||b.querySelector('strong')?.textContent||'KCMC photo';el.insertBefore(img,el.firstChild);setStatus('KCMC photo added')});
document.getElementById('deleteItem').onclick=()=>{if(selected){recordHistory();selected.remove();clearSelection();setStatus('Object deleted')}};
document.getElementById('newBtn').onclick=()=>{projectGeneration++;projectId=null;document.getElementById('projectName').value='Untitled publication';page.innerHTML='';clearSelection();template('flyer');resetHistory();setStatus('New publication')};
document.getElementById('duplicateBtn').onclick=()=>{commitCurrentPage();const name=currentProjectName();projectGeneration++;projectId=null;document.getElementById('projectName').value=name.slice(0,73)+' - Copy';setStatus('Independent copy ready — click Save')};
prevPage.onclick=()=>showPage(currentPageIndex-1);nextPage.onclick=()=>showPage(currentPageIndex+1);
addPage.onclick=()=>{commitCurrentPage();if(pageState.length>=12)return;recordHistory();pageState.push({pageSize:pageSize.value,orientation:orientation.value,items:[]});currentPageIndex=pageState.length-1;renderPageData(pageState[currentPageIndex]);setStatus('Blank page added')};
duplicatePage.onclick=()=>{commitCurrentPage();if(pageState.length>=12)return;recordHistory();const copy=JSON.parse(JSON.stringify(pageState[currentPageIndex]));pageState.splice(currentPageIndex+1,0,copy);currentPageIndex++;renderPageData(copy);setStatus('Page duplicated')};
deletePage.onclick=()=>{commitCurrentPage();if(pageState.length<=1)return;recordHistory();pageState.splice(currentPageIndex,1);currentPageIndex=Math.min(currentPageIndex,pageState.length-1);renderPageData(pageState[currentPageIndex]);setStatus('Page deleted')};
function duplicateSelectedItem(){
 if(!selected)return;
 recordHistory();
 const data=itemData(selected);
 data.x=Math.max(0,(Number(data.x)||0)+12);data.y=Math.max(0,(Number(data.y)||0)+12);
 const copy=restoreItem(data);select(copy);setStatus('Object duplicated');
}
function arrangeSelected(action){
 if(!selected)return;
 const item=selected,previous=item.previousElementSibling,next=item.nextElementSibling;
 if(action==='front'&&next){recordHistory();page.appendChild(item);setStatus('Brought to front')}
 else if(action==='forward'&&next){recordHistory();page.insertBefore(next,item);setStatus('Brought forward')}
 else if(action==='backward'&&previous){recordHistory();page.insertBefore(item,previous);setStatus('Sent backward')}
 else if(action==='back'&&previous){recordHistory();page.insertBefore(item,page.firstElementChild);setStatus('Sent to back')}
 item.focus({preventScroll:true});
}
function buildPrintPage(p){const out=document.createElement('div');out.className='page';applyPage(out,p.pageSize,p.orientation);for(const item of (p.items||[])){const el=document.createElement('div');el.className='item';el.dataset.type=item.type;Object.assign(el.style,{left:item.x+'px',top:item.y+'px',width:item.w+'px',height:item.h+'px',fontFamily:item.fontFamily||'Arial',fontSize:(item.fontSize||24)+'px',fontWeight:item.fontWeight||'400',fontStyle:item.fontStyle||'normal',textAlign:item.textAlign||'left',color:item.color||'#17324c',background:item.fill||'#ffffff',borderColor:item.borderColor||'#17324c',borderStyle:(item.borderWidth||0)>0?'solid':'none',borderWidth:(item.borderWidth||0)+'px',opacity:item.opacity??1});if(item.type==='text')el.textContent=item.text||'';else if(item.type==='image'){const img=document.createElement('img');img.src=item.mediaId?mediaEndpoint+'?id='+encodeURIComponent(item.mediaId):(item.src||'');img.alt=item.alt||'KCMC photo';el.appendChild(img)}out.appendChild(el)}return out}
async function renderPrintPages(){commitCurrentPage();const box=document.getElementById('printPages');box.innerHTML='';pageState.forEach(p=>box.appendChild(buildPrintPage(p)));const images=[...box.querySelectorAll('img')];await Promise.all(images.map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.onload=resolve;img.onerror=resolve})))}
undoButton.onclick=undo;redoButton.onclick=redo;
document.getElementById('duplicateItemBtn').onclick=duplicateSelectedItem;
document.getElementById('bringFrontBtn').onclick=()=>arrangeSelected('front');
document.getElementById('bringForwardBtn').onclick=()=>arrangeSelected('forward');
document.getElementById('sendBackwardBtn').onclick=()=>arrangeSelected('backward');
document.getElementById('sendBackBtn').onclick=()=>arrangeSelected('back');
document.getElementById('saveBtn').onclick=save;document.getElementById('printBtn').onclick=async()=>{setStatus('Preparing all pages…');await renderPrintPages();setStatus('Print dialog ready');window.print()};
pageSize.onfocus=recordHistory;orientation.onfocus=recordHistory;
pageSize.onchange=()=>{applyPage();commitCurrentPage()};orientation.onchange=()=>{applyPage();commitCurrentPage()};
fontFamily.onchange=()=>{if(selected){recordHistory();selected.style.fontFamily=fontFamily.value}};fontSize.oninput=()=>{if(selected){recordHistory();selected.style.fontSize=fontSize.value+'px'}};
boldBtn.onclick=()=>{if(selected){recordHistory();selected.style.fontWeight=getComputedStyle(selected).fontWeight==='700'?'400':'700'}};italicBtn.onclick=()=>{if(selected){recordHistory();selected.style.fontStyle=getComputedStyle(selected).fontStyle==='italic'?'normal':'italic'}};
document.querySelectorAll('[data-align]').forEach(b=>b.onclick=()=>{if(selected){recordHistory();selected.style.textAlign=b.dataset.align}});
textColor.oninput=()=>{if(selected){recordHistory();selected.style.color=textColor.value}};fillColor.oninput=()=>{if(selected){recordHistory();selected.style.background=fillColor.value}};borderColor.oninput=()=>{if(selected){recordHistory();selected.style.borderColor=borderColor.value}};borderWidth.oninput=()=>{if(selected){recordHistory();selected.style.borderStyle='solid';selected.style.borderWidth=borderWidth.value+'px'}};opacity.oninput=()=>{if(selected){recordHistory();selected.style.opacity=opacity.value/100}};
document.addEventListener('keydown',e=>{
 const editing=document.activeElement instanceof Element&&document.activeElement.closest('.item.editing');
 if(editing)return;
 const mod=e.ctrlKey||e.metaKey;
 if(mod&&!e.shiftKey&&e.key.toLowerCase()==='z'){e.preventDefault();undo()}
 else if((mod&&e.shiftKey&&e.key.toLowerCase()==='z')||(e.ctrlKey&&!e.shiftKey&&e.key.toLowerCase()==='y')){e.preventDefault();redo()}
 else if(mod&&!e.shiftKey&&e.key.toLowerCase()==='d'&&selected){e.preventDefault();duplicateSelectedItem()}
});
applyPage();template('flyer');updatePageControls();updateArrangeButtons();resetHistory();renderSaved();renderSharedMedia();
})();
</script>
</body></html>