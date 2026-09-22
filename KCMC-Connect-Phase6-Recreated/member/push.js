(()=>{
  'use strict';
  const root=document.querySelector('[data-push-settings]');
  if(!root)return;
  const status=root.querySelector('[data-push-status]');
  const enable=root.querySelector('[data-push-enable]');
  const disable=root.querySelector('[data-push-disable]');
  const api=root.dataset.api||'';
  const swUrl=root.dataset.sw||'';
  const scope=root.dataset.scope||'./';
  const csrf=root.dataset.csrf||'';
  const setStatus=message=>{if(status)status.textContent=message;};
  const decodeKey=value=>{
    const pad='='.repeat((4-(value.length%4))%4);
    const raw=atob((value+pad).replace(/-/g,'+').replace(/_/g,'/'));
    return Uint8Array.from(raw,ch=>ch.charCodeAt(0));
  };
  const supported=()=>window.isSecureContext&&'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window;
  async function config(){
    const response=await fetch(api,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
    if(!response.ok)throw new Error('config');
    return response.json();
  }
  async function registration(){
    return navigator.serviceWorker.register(swUrl,{scope,updateViaCache:'none'});
  }
  async function current(){
    const reg=await registration();
    return {reg,subscription:await reg.pushManager.getSubscription()};
  }
  function render(subscription,ready){
    if(enable){enable.disabled=!ready||!!subscription;enable.hidden=!!subscription;}
    if(disable)disable.hidden=!subscription;
    setStatus(subscription?'Notifications are enabled on this device.':ready?'Notifications are off on this device.':'Notifications are not ready yet.');
  }
  async function refresh(){
    if(!supported()){
      if(enable)enable.disabled=true;
      setStatus('This browser does not currently support KCMC push notifications. On iPhone or iPad, save KCMC Connect to the Home Screen first.');
      return;
    }
    try{
      const [cfg,state]=await Promise.all([config(),current()]);
      render(state.subscription,!!cfg.enabled&&!!cfg.public_key);
    }catch(_){
      if(enable)enable.disabled=true;
      setStatus('Notification settings could not be checked.');
    }
  }
  enable?.addEventListener('click',async()=>{
    enable.disabled=true;
    setStatus('Requesting notification permission…');
    try{
      const permission=await Notification.requestPermission();
      if(permission!=='granted'){
        setStatus(permission==='denied'?'Notifications are blocked in this browser’s settings.':'Notification permission was not granted.');
        return;
      }
      const cfg=await config();
      if(!cfg.enabled||!cfg.public_key)throw new Error('not_ready');
      const {reg,subscription:existing}=await current();
      let subscription=existing;
      if(!subscription){
        subscription=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decodeKey(cfg.public_key)});
      }
      const response=await fetch(api,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({action:'subscribe',csrf,subscription:subscription.toJSON()})});
      if(!response.ok){
        if(!existing)await subscription.unsubscribe().catch(()=>{});
        throw new Error('save');
      }
      render(subscription,true);
    }catch(error){
      setStatus(error?.message==='not_ready'?'Push notifications have not been initialized by an administrator yet.':'Notifications could not be enabled on this device.');
      enable.disabled=false;
    }
  });
  disable?.addEventListener('click',async()=>{
    disable.disabled=true;
    setStatus('Turning off notifications…');
    try{
      const {subscription}=await current();
      if(subscription){
        await fetch(api,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({action:'unsubscribe',csrf,endpoint:subscription.endpoint})}).catch(()=>null);
        await subscription.unsubscribe().catch(()=>false);
      }
      render(null,true);
    }catch(_){
      setStatus('Notifications could not be changed on this device.');
      disable.disabled=false;
    }
  });
  refresh();
})();
