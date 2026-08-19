(() => {
  'use strict';
  const OFFICE_EMAIL = 'secretary@umckc.org';
  const views = [...document.querySelectorAll('[data-view]')];
  const routeLinks = [...document.querySelectorAll('[data-route]')];
  const allowed = new Set(views.map(v => v.dataset.view));
  const normalize = () => {
    const raw = location.hash.replace(/^#/, '').trim().toLowerCase();
    return allowed.has(raw) ? raw : 'home';
  };
  function renderRoute(){
    const route = normalize();
    views.forEach(v => v.classList.toggle('active', v.dataset.view === route));
    routeLinks.forEach(a => { const active=a.dataset.route===route; a.classList.toggle('active',active); if(active) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    document.title = route === 'home' ? 'KCMC Connect' : `${route[0].toUpperCase()+route.slice(1)} • KCMC Connect`;
    window.scrollTo({top:0,behavior:'instant'});
  }
  window.addEventListener('hashchange', renderRoute);
  renderRoute();

  let deferredPrompt = null;
  const installBtn = document.getElementById('installBtn');
  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferredPrompt=e; if(installBtn) installBtn.style.display='inline-flex'; });
  installBtn?.addEventListener('click', async () => { if(!deferredPrompt) return; deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt=null; installBtn.style.display='none'; });
  window.addEventListener('appinstalled', () => { if(installBtn) installBtn.style.display='none'; });

  const modal = document.getElementById('imageModal');
  const modalImg = modal?.querySelector('img');
  let modalReturnFocus = null;
  document.querySelectorAll('[data-img]').forEach(btn => btn.addEventListener('click', () => {
    modalReturnFocus=btn; modalImg.src=btn.dataset.img; modal.classList.add('open'); document.body.style.overflow='hidden'; modal.querySelector('button')?.focus();
  }));
  const closeModal=()=>{ modal?.classList.remove('open'); document.body.style.overflow=''; modalReturnFocus?.focus(); };
  modal?.querySelector('button')?.addEventListener('click',closeModal);
  modal?.addEventListener('click',e=>{if(e.target===modal)closeModal();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

  // Forms are production-safe for the current static host: validate locally and hand off a fully composed request to the church office email.
  // Replace sendFormByEmail() with a ChMS/API endpoint later to enable staff dashboards and automatic confirmation emails without changing the forms.
  function sendFormByEmail(form){
    const status=form.querySelector('.form-status');
    if(!form.checkValidity()){ form.reportValidity(); status.textContent='Please complete the required fields.'; status.className='form-status error'; return; }
    const data=new FormData(form);
    const lines=[];
    for(const [key,value] of data.entries()) if(String(value).trim()) lines.push(`${key}: ${value}`);
    const subject=form.dataset.subject || 'KCMC Connect Form';
    const href=`mailto:${OFFICE_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`;
    status.textContent='Opening your email app with this request ready to send…'; status.className='form-status success';
    window.location.href=href;
  }
  document.querySelectorAll('[data-kcmc-form]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();sendFormByEmail(form);}));

  const eventName=document.getElementById('eventName'), eventDisplay=document.getElementById('eventDisplay');
  document.querySelectorAll('.event-rsvp').forEach(btn=>btn.addEventListener('click',()=>{
    const card=btn.closest('.event-card'), name=card?.dataset.event || '';
    if(eventName) eventName.value=name; if(eventDisplay) eventDisplay.value=name;
    document.getElementById('eventForm')?.scrollIntoView({behavior:'smooth',block:'center'});
  }));
  function toICSDate(date,time){
    const [y,m,d]=date.split('-').map(Number); const match=time.match(/(\d+):(\d+)\s*(AM|PM)/i); if(!match)return `${y}${String(m).padStart(2,'0')}${String(d).padStart(2,'0')}`;
    let h=Number(match[1]); const min=Number(match[2]); const ap=match[3].toUpperCase(); if(ap==='PM'&&h!==12)h+=12;if(ap==='AM'&&h===12)h=0;
    return `${y}${String(m).padStart(2,'0')}${String(d).padStart(2,'0')}T${String(h).padStart(2,'0')}${String(min).padStart(2,'0')}00`;
  }
  document.querySelectorAll('.add-calendar').forEach(btn=>btn.addEventListener('click',()=>{
    const card=btn.closest('.event-card'); if(!card)return; const start=toICSDate(card.dataset.date,card.dataset.time);
    const ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//KCMC Connect//EN','BEGIN:VEVENT',`DTSTART:${start}`,`SUMMARY:${card.dataset.event}`,'LOCATION:57 Kimberling City Center Lane, Kimberling City, MO 65686','END:VEVENT','END:VCALENDAR'].join('\r\n');
    const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([ics],{type:'text/calendar'})); a.download=`kcmc-${card.dataset.date}-${card.dataset.event.toLowerCase().replace(/[^a-z0-9]+/g,'-')}.ics`; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }));

  const sermonSearch=document.getElementById('sermonSearch'), sermonFilter=document.getElementById('sermonFilter');
  function filterSermons(){ const q=(sermonSearch?.value||'').trim().toLowerCase(), type=sermonFilter?.value||'all'; document.querySelectorAll('.sermon-card').forEach(card=>{card.hidden=!!((q&&!card.dataset.search.includes(q))||(type!=='all'&&card.dataset.type!==type));}); }
  sermonSearch?.addEventListener('input',filterSermons); sermonFilter?.addEventListener('change',filterSermons);

  const preferred=document.getElementById('preferredService');
  if(preferred){ preferred.value=localStorage.getItem('kcmcPreferredService')||''; preferred.addEventListener('change',()=>localStorage.setItem('kcmcPreferredService',preferred.value)); }

  const banner=document.getElementById('offlineBanner');
  const updateOnline=()=>banner?.classList.toggle('show',!navigator.onLine);
  window.addEventListener('online',updateOnline); window.addEventListener('offline',updateOnline); updateOnline();

  if('serviceWorker' in navigator) window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));
})();
