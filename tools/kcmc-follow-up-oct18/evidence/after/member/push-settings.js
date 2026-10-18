'use strict';
(() => {
  const root = document.getElementById('push-settings');
  if (!root || root.dataset.enabled !== '1') return;
  const status = document.getElementById('push-status');
  const enable = document.getElementById('push-enable');
  const disable = document.getElementById('push-disable');
  const display = document.getElementById('push-display-test');
  const displayStatus = document.getElementById('push-display-status');
  const api = root.dataset.api || '';
  const csrf = root.dataset.csrf || '';
  const publicKey = root.dataset.publicKey || '';
  const workerURL = new URL(root.dataset.worker || '../sw.js', window.location.href);
  const appURL = new URL('./', workerURL);

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
  const activeRegistration = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      throw new Error('This browser does not support web push.');
    }
    // Register this app explicitly; a parent site's worker is not KCMC's worker.
    const reg = await navigator.serviceWorker.register(workerURL.href, {scope: appURL.href, updateViaCache: 'none'});
    const active = () => reg.active && reg.active.scriptURL === workerURL.href;
    if (active()) return reg;
    // A first visit can register the worker before it is ready for PushManager.
    const worker = reg.installing || reg.waiting;
    if (!worker) throw new Error('Notification setup is not ready. Reload this page and try again.');
    await new Promise((resolve, reject) => {
      const finish = error => {
        clearTimeout(timer);
        worker.removeEventListener('statechange', check);
        error ? reject(error) : resolve();
      };
      const check = () => {
        if (active() || (worker.state === 'activated' && worker.scriptURL === workerURL.href)) finish();
        else if (worker.state === 'redundant') finish(new Error('Notification setup failed. Reload this page and try again.'));
      };
      const timer = setTimeout(() => finish(new Error('Notification setup timed out. Reload this page and try again.')), 15000);
      worker.addEventListener('statechange', check);
      check();
    });
    return reg;
  };
  let registrationPromise;
  const registration = () => {
    if (!registrationPromise) registrationPromise = activeRegistration().catch(error => {
      registrationPromise = null;
      throw error;
    });
    return registrationPromise;
  };
  const subscriptionMatches = (sub, key) => {
    // Older browsers do not expose the key; leave their existing subscription alone.
    if (!sub.options || !('applicationServerKey' in sub.options)) return true;
    const stored = sub.options.applicationServerKey;
    if (!stored) return false;
    const bytes = new Uint8Array(stored);
    return bytes.length === key.length && bytes.every((value, index) => value === key[index]);
  };
  const refresh = async () => {
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (sub && Notification.permission === 'granted' && !subscriptionMatches(sub, decodeKey(publicKey))) setStatus('This device uses an older notification key. Press Enable notifications to reconnect it.');
      else if (sub && Notification.permission === 'granted') setStatus('Browser notifications are allowed. Press Enable notifications to confirm this device is registered to your account.');
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
      const key = decodeKey(publicKey);
      if (sub && !subscriptionMatches(sub, key)) {
        // Reconnect only after the explicit Enable click; never replace server keys.
        await post({action: 'unsubscribe', endpoint: sub.endpoint});
        if (!await sub.unsubscribe()) throw new Error('Could not reconnect this device. Reload this page and try again.');
        sub = null;
      }
      if (!sub) sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key});
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
      if (!await sub.unsubscribe()) throw new Error('This browser could not finish turning notifications off. Reload this page and try Disable again.');
      setStatus('Notifications are disabled on this device.');
    } catch (error) {
      setStatus(error.message || 'Could not disable notifications.');
    } finally {
      disable.disabled = false;
    }
  });

  display?.addEventListener('click', async () => {
    display.disabled = true;
    const showStatus = message => { if (displayStatus) displayStatus.textContent = message; };
    try {
      if (!('Notification' in window) || Notification.permission !== 'granted') {
        throw new Error('Enable notifications first to allow a display test.');
      }
      const reg = await registration();
      await reg.showNotification('KCMC display test', {
        body: 'If you can see this, notifications can appear on this device.',
        icon: new URL('assets/icons/icon-192.png', appURL).href,
        badge: new URL('assets/icons/icon-192.png', appURL).href,
        data: {url: appURL.href},
        tag: 'kcmc-display-test',
        renotify: true
      });
      showStatus('Display test requested. Look for “KCMC display test” in your notifications. Seeing it confirms browser display; delivery from KCMC is tested separately.');
    } catch (error) {
      showStatus(error.message || 'Could not request the display test. Reload this page and try again.');
    } finally {
      display.disabled = false;
    }
  });

  refresh();
})();
