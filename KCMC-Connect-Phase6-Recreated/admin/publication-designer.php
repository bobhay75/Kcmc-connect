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
.brand{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.brand strong{font-size:1.05rem}.project-name{display:flex;gap:6px;align-items:center;font-size:.85rem}.project-name input{width:min(26vw,260px);min-width:130px;padding:8px;border:1px solid #bdc9d0;border-radius:8px}.actions{display:flex;gap:8px;flex-wrap:wrap}
.btn{border:1px solid #b9c6ce;background:#fff;color:var(--ink);padding:9px 12px;border-radius:9px;font-weight:700;cursor:pointer}.btn.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
.workspace{display:grid;grid-template-columns:250px minmax(0,1fr) 280px;min-height:0}.panel{background:#fff;border-right:1px solid var(--line);padding:14px;overflow:auto}.panel.right{border-right:0;border-left:1px solid var(--line)}
.panel h2{font-size:1rem;margin:4px 0 12px}.field{display:grid;gap:5px;margin:0 0 12px}.field input,.field select,.field textarea{width:100%;padding:8px;border:1px solid #bdc9d0;border-radius:8px;background:#fff;color:#17324c}
.templates{display:grid;gap:8px}.template{border:1px solid #cfd8dd;border-radius:10px;padding:10px;text-align:left;background:#fff;cursor:pointer}.template:hover{background:#f5f8fa}
.canvas-wrap{overflow:auto;padding:28px;display:grid;place-items:start center;background:linear-gradient(45deg,#e7ecef 25%,transparent 25%),linear-gradient(-45deg,#e7ecef 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#e7ecef 75%),linear-gradient(-45deg,transparent 75%,#e7ecef 75%);background-size:24px 24px;background-position:0 0,0 12px,12px -12px,-12px 0}
.page{position:relative;background:#fff;box-shadow:0 8px 26px rgba(0,0,0,.16);transform-origin:top center}
.item{position:absolute;min-width:40px;min-height:28px;border:1px dashed transparent;overflow:hidden}.item.selected{border-color:#1e6fa8;box-shadow:0 0 0 2px rgba(30,111,168,.16)}.item[contenteditable="true"]:focus{outline:none}
.item img{width:100%;height:100%;object-fit:cover;display:block}.handle{position:absolute;width:12px;height:12px;background:#1e6fa8;border:2px solid #fff;border-radius:50%;right:-7px;bottom:-7px;cursor:nwse-resize;display:none}.selected .handle{display:block}
.toolbar{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:12px}.status{font-size:.85rem;color:#607080}.small{font-size:.82rem;color:#607080}.hidden{display:none!important}
@media(max-width:900px){.workspace{grid-template-columns:1fr}.panel.right{border-left:0;border-top:1px solid var(--line)}.panel{border-right:0;border-bottom:1px solid var(--line)}}
@media print{body{background:#fff}.topbar,.panel{display:none!important}.workspace{display:block}.canvas-wrap{padding:0;background:#fff;overflow:visible}.page{box-shadow:none;margin:0;transform:none!important}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar">
  <div class="brand"><a href="<?=kcmc_h(kcmc_url('admin/'))?>" class="btn">← Publishing Desk</a><strong>Publication Designer</strong><label class="project-name">Name <input id="projectName" type="text" maxlength="80" value="Untitled publication" aria-label="Publication name"></label><span class="status" id="status" role="status" aria-live="polite">Ready</span></div>
  <div class="actions">
    <button class="btn" id="newBtn">New</button>
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
  <input class="hidden" type="file" id="imagePicker" accept="image/*">
  <h2>KCMC Photos</h2>
  <div class="templates" id="assetLibrary">
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-building-2024.webp'))?>"><strong>Church Exterior</strong><br><span class="small">KCMC building</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-worship-2017.webp'))?>"><strong>Worship</strong><br><span class="small">Church worship photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-ministry-group.jpg'))?>"><strong>Church Family</strong><br><span class="small">Ministry group photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/kcmc-stage-2014.webp'))?>"><strong>Sanctuary Stage</strong><br><span class="small">KCMC stage photo</span></button>
    <button class="template" data-asset="<?=kcmc_h(kcmc_url('assets/visuals/trunk-or-treat-2026.webp'))?>"><strong>Trunk or Treat</strong><br><span class="small">Approved event graphic</span></button>
  </div>
  <div class="field"><label>Page size<select id="pageSize"><option value="letter">Letter 8.5×11</option><option value="half">Half sheet 5.5×8.5</option><option value="postcard">Postcard 6×4</option></select></label></div>
  <div class="field"><label>Orientation<select id="orientation"><option value="portrait">Portrait</option><option value="landscape">Landscape</option></select></label></div>
  <p class="small">Projects save in this browser only in v1. No church records or private member data are touched.</p>
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
  </div>
  <hr>
  <h2>Saved projects</h2>
  <div id="savedList" class="templates"></div>
</aside>
</div>
</div>
<script>
(()=>{
const page=document.getElementById('page'),status=document.getElementById('status');
const pageSize=document.getElementById('pageSize'),orientation=document.getElementById('orientation');
const props=document.getElementById('properties'),noSel=document.getElementById('noSelection'),projectName=document.getElementById('projectName');
let selected=null,drag=null,projectId=null;
const inch=96,sizes={letter:[8.5,11],half:[5.5,8.5],postcard:[6,4]};
function setStatus(t){status.textContent=t}
function applyPage(){let [w,h]=sizes[pageSize.value];if(orientation.value==='landscape')[w,h]=[h,w];page.style.width=(w*inch)+'px';page.style.height=(h*inch)+'px'}
function clearSelection(){if(selected)selected.classList.remove('selected');selected=null;props.classList.add('hidden');noSel.classList.remove('hidden')}
function select(el){clearSelection();selected=el;el.classList.add('selected');props.classList.remove('hidden');noSel.classList.add('hidden');syncProps()}
function makeItem(type,x=80,y=80,w=300,h=80){const el=document.createElement('div');el.className='item';el.dataset.type=type;Object.assign(el.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px'});if(type==='text'){el.contentEditable='true';el.innerText='Double-click and type';el.style.fontFamily='Arial';el.style.fontSize='28px';el.style.padding='6px'}else if(type==='shape'){el.style.background='#e9eef2';el.style.border='2px solid #17324c'}const handle=document.createElement('span');handle.className='handle';el.appendChild(handle);wire(el,handle);page.appendChild(el);select(el);return el}
function wire(el,handle){el.addEventListener('mousedown',e=>{if(e.target===handle)return;if(e.button!==0)return;select(el);const r=el.getBoundingClientRect(),pr=page.getBoundingClientRect();drag={mode:'move',el,dx:e.clientX-r.left,dy:e.clientY-r.top,pr};e.preventDefault()});handle.addEventListener('mousedown',e=>{const r=el.getBoundingClientRect();drag={mode:'resize',el,sx:e.clientX,sy:e.clientY,sw:r.width,sh:r.height};e.stopPropagation();e.preventDefault()})}
document.addEventListener('mousemove',e=>{if(!drag)return;if(drag.mode==='move'){const x=Math.max(0,e.clientX-drag.pr.left-drag.dx),y=Math.max(0,e.clientY-drag.pr.top-drag.dy);drag.el.style.left=x+'px';drag.el.style.top=y+'px'}else{drag.el.style.width=Math.max(40,drag.sw+e.clientX-drag.sx)+'px';drag.el.style.height=Math.max(28,drag.sh+e.clientY-drag.sy)+'px'}});
document.addEventListener('mouseup',()=>drag=null);page.addEventListener('mousedown',e=>{if(e.target===page)clearSelection()});
function syncProps(){if(!selected)return;const cs=getComputedStyle(selected);fontFamily.value=cs.fontFamily.replaceAll('"','').split(',')[0];fontSize.value=parseInt(cs.fontSize)||24;textColor.value=rgbToHex(cs.color);fillColor.value=rgbToHex(cs.backgroundColor)==='#000000'?'#ffffff':rgbToHex(cs.backgroundColor);borderColor.value=rgbToHex(cs.borderColor);borderWidth.value=parseInt(cs.borderWidth)||0;opacity.value=Math.round((parseFloat(cs.opacity)||1)*100)}
function rgbToHex(v){const m=v.match(/\d+/g);if(!m||m.length<3)return '#17324c';return '#'+m.slice(0,3).map(n=>(+n).toString(16).padStart(2,'0')).join('')}
function template(name){page.innerHTML='';clearSelection();pageSize.value=name==='postcard'?'postcard':'letter';orientation.value=name==='postcard'?'landscape':'portrait';applyPage();
 if(name==='flyer'){const h=makeItem('text',70,70,650,90);h.innerText='YOU ARE INVITED';h.style.fontSize='52px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',100,190,590,150);t.innerText='Event Name\nDate • Time • Location';t.style.textAlign='center';const b=makeItem('shape',100,390,590,260);b.style.background='#e9eef2'}
 if(name==='bulletin'){const h=makeItem('text',70,55,650,70);h.innerText='KIMBERLING CITY METHODIST CHURCH';h.style.fontSize='32px';h.style.fontWeight='700';h.style.textAlign='center';const l=makeItem('text',70,145,650,720);l.innerText='Welcome\n\nPrelude\nOpening Hymn\nPrayer\nScripture\nMessage\nOffering\nClosing Hymn\nBenediction';l.style.fontSize='22px'}
 if(name==='newsletter'){const h=makeItem('text',60,50,670,70);h.innerText='KCMC NEWS & NOTES';h.style.fontSize='40px';h.style.fontWeight='700';h.style.textAlign='center';const c1=makeItem('text',70,150,300,700);c1.innerText='FROM THE CHURCH\n\nAdd updates here.';const c2=makeItem('text',420,150,300,700);c2.innerText='COMING UP\n\nAdd events and announcements here.'}
 if(name==='postcard'){const h=makeItem('text',50,55,475,80);h.innerText='COME JOIN US';h.style.fontSize='42px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',65,160,445,130);t.innerText='Kimberling City Methodist Church\nSunday Worship\n8:00 • 9:15 • 10:30';t.style.textAlign='center'}
 if(name==='memorial'){const h=makeItem('text',90,70,610,85);h.innerText='A SERVICE OF REMEMBRANCE';h.style.fontSize='34px';h.style.fontWeight='700';h.style.textAlign='center';const t=makeItem('text',110,190,570,600);t.innerText='Name\nDates\n\nPrelude\nWelcome\nScripture\nRemembrances\nMessage\nPrayer\nClosing';t.style.textAlign='center';t.style.fontSize='22px'}
 if(name==='study'){const h=makeItem('text',70,55,650,70);h.innerText='BIBLE STUDY';h.style.fontSize='38px';h.style.fontWeight='700';const t=makeItem('text',70,150,650,720);t.innerText='Scripture:\n\nMain idea:\n\nNotes:\n\nQuestions:\n1.\n2.\n3.';t.style.fontSize='22px'}
 clearSelection();setStatus('Template loaded')}
function currentProjectName(){return projectName.value.trim().slice(0,80)||'Untitled publication'}
function save(){const p={id:projectId||crypto.randomUUID(),name:currentProjectName(),pageSize:pageSize.value,orientation:orientation.value,html:page.innerHTML,updated:new Date().toISOString()};const all=JSON.parse(localStorage.getItem('kcmc-publications-v1')||'[]').filter(x=>x.id!==p.id);all.unshift(p);localStorage.setItem('kcmc-publications-v1',JSON.stringify(all.slice(0,30)));projectId=p.id;projectName.value=p.name;renderSaved();setStatus('Saved in this browser')}
function duplicate(){const source=currentProjectName();projectId=null;projectName.value=source.slice(0,72)+' - Copy';save();setStatus('Independent copy saved in this browser')}
function sanitizeSavedMarkup(markup){const parsed=new DOMParser().parseFromString(String(markup||''),'text/html');const clean=document.createDocumentFragment();const allowed=new Set(['DIV','SPAN','IMG','BR','B','STRONG','I','EM','U']);const styleProps=new Set(['position','left','top','width','height','min-width','min-height','overflow','font-family','font-size','font-weight','font-style','text-align','color','background','background-color','border','border-color','border-style','border-width','padding','opacity','object-fit','display']);function safeStyle(raw){return String(raw||'').split(';').map(part=>{const i=part.indexOf(':');if(i<1)return '';const key=part.slice(0,i).trim().toLowerCase(),value=part.slice(i+1).trim();if(!styleProps.has(key)||!value||value.length>120||/[<>]|url\s*\(|expression|javascript:|@import/i.test(value))return '';return key+':'+value}).filter(Boolean).join(';')}function copy(node,parent){if(node.nodeType===Node.TEXT_NODE){parent.appendChild(document.createTextNode(node.nodeValue||''));return}if(node.nodeType!==Node.ELEMENT_NODE)return;const tag=node.tagName;if(!allowed.has(tag)){node.childNodes.forEach(child=>copy(child,parent));return}const el=document.createElement(tag.toLowerCase());const style=safeStyle(node.getAttribute('style'));if(style)el.setAttribute('style',style);if(tag==='DIV'&&node.classList.contains('item')){el.className='item';const type=node.getAttribute('data-type');if(['text','image','shape'].includes(type))el.dataset.type=type;if(type==='text'&&node.getAttribute('contenteditable')==='true')el.contentEditable='true'}else if(tag==='SPAN'&&node.classList.contains('handle'))el.className='handle';if(tag==='IMG'){const src=node.getAttribute('src')||'';let safe=false;if(/^data:image\/(?:png|jpeg|gif|webp);base64,/i.test(src))safe=true;else{try{const u=new URL(src,location.href);safe=u.origin===location.origin&&/^https?:$/.test(u.protocol)}catch{safe=false}}if(!safe)return;el.setAttribute('src',src);el.setAttribute('alt',(node.getAttribute('alt')||'').slice(0,160))}parent.appendChild(el);node.childNodes.forEach(child=>copy(child,el))}parsed.body.childNodes.forEach(node=>copy(node,clean));return clean}
function load(id){const all=JSON.parse(localStorage.getItem('kcmc-publications-v1')||'[]');const p=all.find(x=>x.id===id);if(!p)return;projectId=p.id;projectName.value=String(p.name||'Untitled publication').slice(0,80);pageSize.value=sizes[p.pageSize]?p.pageSize:'letter';orientation.value=p.orientation==='landscape'?'landscape':'portrait';applyPage();page.replaceChildren(sanitizeSavedMarkup(p.html));page.querySelectorAll('.item').forEach(el=>{let h=el.querySelector('.handle');if(!h){h=document.createElement('span');h.className='handle';el.appendChild(h)}wire(el,h)});clearSelection();setStatus('Loaded '+projectName.value)}
function renderSaved(){const all=JSON.parse(localStorage.getItem('kcmc-publications-v1')||'[]'),box=document.getElementById('savedList');box.innerHTML='';all.forEach(p=>{const b=document.createElement('button');b.className='template';b.innerHTML='<strong>'+escapeHtml(p.name)+'</strong><br><span class="small">'+new Date(p.updated).toLocaleString()+'</span>';b.onclick=()=>load(p.id);box.appendChild(b)})}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
document.getElementById('templates').addEventListener('click',e=>{const b=e.target.closest('[data-template]');if(b)template(b.dataset.template)});
document.getElementById('addText').onclick=()=>makeItem('text');document.getElementById('addShape').onclick=()=>makeItem('shape');
document.getElementById('addImage').onclick=()=>imagePicker.click();imagePicker.onchange=e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{const el=makeItem('image',80,80,320,220);const img=document.createElement('img');img.src=r.result;el.insertBefore(img,el.firstChild)};r.readAsDataURL(f);imagePicker.value=''};
document.getElementById('assetLibrary').addEventListener('click',e=>{const b=e.target.closest('[data-asset]');if(!b)return;const el=makeItem('image',80,80,320,220);const img=document.createElement('img');img.src=b.dataset.asset;img.alt=b.querySelector('strong')?.textContent||'KCMC photo';el.insertBefore(img,el.firstChild);setStatus('KCMC photo added')});
document.getElementById('deleteItem').onclick=()=>{if(selected){selected.remove();clearSelection()}};
document.getElementById('newBtn').onclick=()=>{projectId=null;projectName.value='Untitled publication';page.innerHTML='';clearSelection();template('flyer')};
document.getElementById('duplicateBtn').onclick=duplicate;
document.getElementById('saveBtn').onclick=save;document.getElementById('printBtn').onclick=()=>window.print();
pageSize.onchange=applyPage;orientation.onchange=applyPage;
fontFamily.onchange=()=>selected&&(selected.style.fontFamily=fontFamily.value);fontSize.oninput=()=>selected&&(selected.style.fontSize=fontSize.value+'px');
boldBtn.onclick=()=>selected&&(selected.style.fontWeight=getComputedStyle(selected).fontWeight==='700'?'400':'700');italicBtn.onclick=()=>selected&&(selected.style.fontStyle=getComputedStyle(selected).fontStyle==='italic'?'normal':'italic');
document.querySelectorAll('[data-align]').forEach(b=>b.onclick=()=>selected&&(selected.style.textAlign=b.dataset.align));
textColor.oninput=()=>selected&&(selected.style.color=textColor.value);fillColor.oninput=()=>selected&&(selected.style.background=fillColor.value);borderColor.oninput=()=>selected&&(selected.style.borderColor=borderColor.value);borderWidth.oninput=()=>selected&&(selected.style.borderStyle='solid',selected.style.borderWidth=borderWidth.value+'px');opacity.oninput=()=>selected&&(selected.style.opacity=opacity.value/100);
applyPage();template('flyer');renderSaved();
})();
</script>
</body></html>