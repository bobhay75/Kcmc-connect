'use strict';
(() => {
  const root = document.getElementById('push-settings');
  if (!root || root.dataset.enabled !== '1') return;
  const status = document.getElementById('push-status');
  const enable = document.getElementById('push-enable');
  const disable = document.getElementById('push-disable');
  const api = root.dataset.api || '';
  const csrf = root.dataset.csrf || '';
  const publicKey = root.dataset.publicKey || '';

  const setStatus = message => { if (status) status.textContent = message; };
  const decodeKey = value => {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const raw = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  };
  const post = async body => {
    const response = await fetch(api, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({csrf, ...body})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || 'Request failed');
    return data;
  };
  const registration = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      throw new Error('This browser does not support web push.');
    }
    const current = await navigator.serviceWorker.getRegistration();
    return current || navigator.serviceWorker.register('../sw.js');
  };
  const refresh = async () => {
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (sub && Notification.permission === 'granted') setStatus('Notifications are enabled on this device.');
      else if (Notification.permission === 'denied') setStatus('Browser notification permission is blocked for KCMC Connect.');
      else setStatus('Notifications are off on this device.');
    } catch (error) {
      setStatus(error.message || 'Notifications are unavailable in this browser.');
    }
  };

  enable?.addEventListener('click', async () => {
    enable.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Notification permission was not granted.');
      const reg = await registration();
      let sub = await reg.pushManager.getSubscription();
      if (!sub) sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: decodeKey(publicKey)});
      await post({action: 'subscribe', subscription: sub.toJSON()});
      setStatus('Notifications are enabled on this device.');
    } catch (error) {
      setStatus(error.message || 'Could not enable notifications.');
    } finally {
      enable.disabled = false;
    }
  });

  disable?.addEventListener('click', async () => {
    disable.disabled = true;
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (!sub) {
        setStatus('Notifications are already off on this device.');
        return;
      }
      const endpoint = sub.endpoint;
      await post({action: 'unsubscribe', endpoint});
      await sub.unsubscribe();
      setStatus('Notifications are disabled on this device.');
    } catch (error) {
      setStatus(error.message || 'Could not disable notifications.');
    } finally {
      disable.disabled = false;
    }
  });

  refresh();
})();
