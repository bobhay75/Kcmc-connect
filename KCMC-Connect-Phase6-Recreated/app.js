(() => {
  'use strict';
  const OFFICE_EMAIL = 'secretary@umckc.org';
  const views = [...document.querySelectorAll('[data-view]')];
  const routeLinks = [...document.querySelectorAll('[data-route]')];
  const allowed = new Set(views.map(v => v.dataset.view));
  const normalize = () => { const raw=location.hash.replace(/^#/,'').trim().toLowerCase(); return allowed.has(raw)?raw:'home'; };
  function renderRoute(){ const route=normalize(); views.forEach(v=>v.classList.toggle('active',v.dataset.view===route)); routeLinks.forEach(a=>{const active=a.dataset.route===route;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}); document.title=route==='home'?'KCMC Connect':`${route[0].toUpperCase()+route.slice(1)} • KCMC Connect`; window.scrollTo({top:0,behavior:'instant'}); }
  window.addEventListener('hashchange',renderRoute); renderRoute();

  document.querySelectorAll('.phase6-bulletin-fab').forEach(link=>{link.href='bulletin.php';link.textContent='Latest Bulletin';});

  async function hydrateCurrentStory(){
    let top=null; try{const response=await fetch('./api/content.php',{cache:'no-store'});if(response.ok){const payload=await response.json();const announcements=Array.isArray(payload?.announcements)?payload.announcements:[];const now=Date.now();top=announcements.filter(item=>{if(item?.status&&item.status!=='published')return false;const start=item?.starts_at?Date.parse(item.starts_at):-Infinity,end=item?.expires_at?Date.parse(item.expires_at):Infinity;return now>=start&&now<end;}).sort((a,b)=>(Number(b?.priority)||0)-(Number(a?.priority)||0))[0]||null;}}catch(_){}
    const announcement=document.querySelector('.phase6-announcement'); const href=top?.link||(announcement?.textContent?.toLowerCase().includes('backpack blessing')?'backpack-blessing.php':'');
    if(announcement&&href){announcement.classList.add('is-actionable');announcement.setAttribute('role','link');announcement.setAttribute('tabindex','0');announcement.setAttribute('aria-label',`${top?.title||'Current KCMC story'} — open story`);announcement.title='Open this story';const open=()=>{window.location.href=href;};announcement.addEventListener('click',open);announcement.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});}
    const visualStory=document.querySelector('[data-view="home"] .visual-story'); if(visualStory&&!document.getElementById('backpackBlessingFeature')){const feature=document.createElement('a');feature.id='backpackBlessingFeature';feature.className='backpack-feature';feature.href='backpack-blessing.php';feature.innerHTML=`<img src="./assets/visuals/backpack-hero.webp" alt="Children and ministry leaders during KCMC's Back-to-School Backpack Blessing" loading="eager" decoding="async"><span class="backpack-feature-copy"><span class="eyebrow">KCMC in Action • Launch Kids</span><strong>Back-to-School Backpack Blessing</strong><span>KCMC prayed over local students, their backpacks, teachers and families as a new school year begins.</span><b>See the story →</b></span>`;visualStory.appendChild(feature);}
    if(!document.getElementById('backpackFeatureStyles')){const style=document.createElement('style');style.id='backpackFeatureStyles';style.textContent=`.phase6-announcement.is-actionable{cursor:pointer}.phase6-announcement.is-actionable:hover strong{text-decoration:underline}.phase6-announcement.is-actionable:focus-visible{outline:3px solid currentColor;outline-offset:-3px}.backpack-feature{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(260px,.85fr);text-decoration:none;color:inherit;background:linear-gradient(135deg,rgba(14,40,59,.98),rgba(23,62,86,.96));border:1px solid rgba(255,255,255,.12);border-radius:24px;overflow:hidden;box-shadow:0 18px 48px rgba(0,0,0,.2)}.backpack-feature img{width:100%;height:100%;min-height:300px;object-fit:cover;display:block}.backpack-feature-copy{display:flex;flex-direction:column;justify-content:center;gap:12px;padding:34px}.backpack-feature-copy strong{font-family:Georgia,serif;font-size:clamp(2rem,4vw,3.25rem);line-height:1.02;font-weight:400}.backpack-feature-copy>span:not(.eyebrow){line-height:1.65;opacity:.86}.backpack-feature-copy b{margin-top:6px}.backpack-feature:hover .backpack-feature-copy b{text-decoration:underline}@media(max-width:760px){.backpack-feature{grid-template-columns:1fr}.backpack-feature img{min-height:0;aspect-ratio:16/9}.backpack-feature-copy{padding:24px}}`;document.head.appendChild(style);}
  }
  hydrateCurrentStory();

  // PWA installation: Chromium can open its native prompt; iOS requires Safari's Share menu.
  let deferredPrompt=null;
  let installationCompleted=false;
  let installReturnFocus=null;
  const installButtons=[...document.querySelectorAll('[data-install-app]')];
  const installCallout=document.querySelector('[data-install-callout]');
  const installMessage=document.querySelector('[data-install-message]');
  const installSheet=document.getElementById('installSheet');
  const installSheetCard=installSheet?.querySelector('.install-sheet-card');
  const installSheetCopy=installSheet?.querySelector('[data-install-sheet-copy]');
  const installNativeButton=installSheet?.querySelector('[data-install-native]');
  const userAgent=navigator.userAgent||'';
  const isIOS=/iPad|iPhone|iPod/i.test(userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  const isIOSSafari=isIOS&&/Safari/i.test(userAgent)&&!/CriOS|FxiOS|EdgiOS|OPiOS/i.test(userAgent);
  const isAndroid=/Android/i.test(userAgent);
  const isStandalone=()=>window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;

  function updateInstallUI(){
    const installed=isStandalone()||installationCompleted;
    installButtons.forEach(button=>{button.hidden=installed;});
    if(installCallout)installCallout.hidden=installed;
    if(installMessage){
      if(isIOS)installMessage.textContent='Add KCMC Connect to your iPhone or iPad Home Screen.';
      else if(deferredPrompt)installMessage.textContent='Install KCMC Connect now for quick, app-like access.';
      else if(isAndroid)installMessage.textContent='Add KCMC Connect to your Android Home Screen.';
      else installMessage.textContent='Install KCMC Connect on this computer for quick access.';
    }
  }

  function closeInstallSheet(){
    if(!installSheet||installSheet.hidden)return;
    installSheet.hidden=true;
    document.documentElement.classList.remove('install-sheet-open');
    installReturnFocus?.focus();
    installReturnFocus=null;
  }

  function showInstallSheet(trigger){
    if(!installSheet||!installSheetCopy||!installNativeButton)return;
    installReturnFocus=trigger||document.activeElement;
    installNativeButton.hidden=true;
    if(deferredPrompt){
      installSheet.querySelector('[data-install-eyebrow]').textContent='Ready to install';
      installSheet.querySelector('#installSheetTitle').textContent='Install KCMC Connect';
      installSheetCopy.innerHTML='<p>Your browser is ready. Select the button below, then confirm the native install prompt.</p>';
      installNativeButton.hidden=false;
    }else if(isIOS){
      installSheet.querySelector('[data-install-eyebrow]').textContent='iPhone & iPad';
      installSheet.querySelector('#installSheetTitle').textContent='Add KCMC to your Home Screen';
      installSheetCopy.innerHTML=isIOSSafari
        ?'<ol class="install-sheet-steps"><li><span>Tap the <strong>Share <span class="install-sheet-share" aria-label="Share icon">↑</span></strong> button in Safari.</span></li><li><span>Scroll and tap <strong>Add to Home Screen</strong>.</span></li><li><span>Tap <strong>Add</strong>.</span></li></ol>'
        :'<ol class="install-sheet-steps"><li><span>Open this page in <strong>Safari</strong>.</span></li><li><span>Tap <strong>Share</strong>, then <strong>Add to Home Screen</strong>.</span></li><li><span>Tap <strong>Add</strong>.</span></li></ol>';
    }else if(isAndroid){
      installSheet.querySelector('[data-install-eyebrow]').textContent='Android';
      installSheet.querySelector('#installSheetTitle').textContent='Add KCMC to your Home Screen';
      installSheetCopy.innerHTML='<p>Open this page in <strong>Chrome</strong>, open the browser menu, then choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.</p>';
    }else{
      installSheet.querySelector('[data-install-eyebrow]').textContent='Desktop';
      installSheet.querySelector('#installSheetTitle').textContent='Install KCMC Connect';
      installSheetCopy.innerHTML='<p>Use your browser’s <strong>Install app</strong> command. In Chrome or Edge, look for the install icon near the address bar or open the browser menu.</p>';
    }
    installSheet.hidden=false;
    document.documentElement.classList.add('install-sheet-open');
    installSheetCard?.focus();
  }

  async function requestInstall(trigger){
    if(isStandalone())return;
    if(!deferredPrompt){showInstallSheet(trigger);return;}
    const promptEvent=deferredPrompt;
    deferredPrompt=null;
    await promptEvent.prompt();
    const choice=await promptEvent.userChoice;
    installationCompleted=choice?.outcome==='accepted';
    updateInstallUI();
  }

  installButtons.forEach(button=>button.addEventListener('click',()=>requestInstall(button)));
  installNativeButton?.addEventListener('click',async()=>{const trigger=installReturnFocus;closeInstallSheet();await requestInstall(trigger);});
  installSheet?.querySelector('[data-install-close]')?.addEventListener('click',closeInstallSheet);
  installSheet?.addEventListener('click',event=>{if(event.target===installSheet)closeInstallSheet();});
  document.addEventListener('keydown',event=>{
    if(installSheet?.hidden)return;
    if(event.key==='Escape'){closeInstallSheet();return;}
    if(event.key==='Tab'){
      const focusable=[...installSheet.querySelectorAll('button:not([hidden]),a[href],[tabindex]:not([tabindex="-1"])')];
      if(!focusable.length)return;
      const first=focusable[0],last=focusable[focusable.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();deferredPrompt=event;updateInstallUI();});
  window.addEventListener('appinstalled',()=>{deferredPrompt=null;installationCompleted=true;closeInstallSheet();updateInstallUI();});
  window.matchMedia('(display-mode: standalone)').addEventListener?.('change',updateInstallUI);
  updateInstallUI();

  const modal=document.getElementById('imageModal'),modalImg=modal?.querySelector('img');let modalReturnFocus=null;document.querySelectorAll('[data-img]').forEach(btn=>btn.addEventListener('click',()=>{modalReturnFocus=btn;modalImg.src=btn.dataset.img;modal.classList.add('open');document.body.style.overflow='hidden';modal.querySelector('button')?.focus();}));const closeModal=()=>{modal?.classList.remove('open');document.body.style.overflow='';modalReturnFocus?.focus();};modal?.querySelector('button')?.addEventListener('click',closeModal);modal?.addEventListener('click',e=>{if(e.target===modal)closeModal();});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

  function sendFormByEmail(form){const status=form.querySelector('.form-status');if(!form.checkValidity()){form.reportValidity();status.textContent='Please complete the required fields.';status.className='form-status error';return;}const data=new FormData(form),lines=[];for(const [key,value] of data.entries())if(String(value).trim())lines.push(`${key}: ${value}`);const subject=form.dataset.subject||'KCMC Connect Form';status.textContent='Opening your email app with this request ready to send…';status.className='form-status success';window.location.href=`mailto:${OFFICE_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`;}
  document.querySelectorAll('[data-kcmc-form]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();sendFormByEmail(form);}));
  const eventName=document.getElementById('eventName'),eventDisplay=document.getElementById('eventDisplay');document.querySelectorAll('.event-rsvp').forEach(btn=>btn.addEventListener('click',()=>{const card=btn.closest('.event-card'),name=card?.dataset.event||'';if(eventName)eventName.value=name;if(eventDisplay)eventDisplay.value=name;document.getElementById('eventForm')?.scrollIntoView({behavior:'smooth',block:'center'});}));
  function toICSDate(date,time){const [y,m,d]=date.split('-').map(Number);const match=time.match(/(\d+):(\d+)\s*(AM|PM)/i);if(!match)return`${y}${String(m).padStart(2,'0')}${String(d).padStart(2,'0')}`;let h=Number(match[1]);const min=Number(match[2]),ap=match[3].toUpperCase();if(ap==='PM'&&h!==12)h+=12;if(ap==='AM'&&h===12)h=0;return`${y}${String(m).padStart(2,'0')}${String(d).padStart(2,'0')}T${String(h).padStart(2,'0')}${String(min).padStart(2,'0')}00`;}
  document.querySelectorAll('.add-calendar').forEach(btn=>btn.addEventListener('click',()=>{const card=btn.closest('.event-card');if(!card)return;const start=toICSDate(card.dataset.date,card.dataset.time),ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//KCMC Connect//EN','BEGIN:VEVENT',`DTSTART:${start}`,`SUMMARY:${card.dataset.event}`,'LOCATION:57 Kimberling City Center Lane, Kimberling City, MO 65686','END:VEVENT','END:VCALENDAR'].join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([ics],{type:'text/calendar'}));a.download=`kcmc-${card.dataset.date}-${card.dataset.event.toLowerCase().replace(/[^a-z0-9]+/g,'-')}.ics`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}));
  const sermonSearch=document.getElementById('sermonSearch'),sermonFilter=document.getElementById('sermonFilter');function filterSermons(){const q=(sermonSearch?.value||'').trim().toLowerCase(),type=sermonFilter?.value||'all';document.querySelectorAll('.sermon-card').forEach(card=>{card.hidden=!!((q&&!card.dataset.search.includes(q))||(type!=='all'&&card.dataset.type!==type));});}sermonSearch?.addEventListener('input',filterSermons);sermonFilter?.addEventListener('change',filterSermons);
  const preferred=document.getElementById('preferredService');if(preferred){preferred.value=localStorage.getItem('kcmcPreferredService')||'';preferred.addEventListener('change',()=>localStorage.setItem('kcmcPreferredService',preferred.value));}
  const banner=document.getElementById('offlineBanner');const updateOnline=()=>banner?.classList.toggle('show',!navigator.onLine);window.addEventListener('online',updateOnline);window.addEventListener('offline',updateOnline);updateOnline();
  if('serviceWorker'in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).catch(()=>{}));
})();
