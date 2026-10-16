(() => {
  'use strict';

  const stateKey = 'kcmcAppScreenV1';
  const links = document.querySelectorAll('[data-kcmc-back]');
  const plainObject = (value) => {
    if (value === null || typeof value !== 'object') return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  };
  const appFor = (link) => {
    try {
      const app = new URL(link.dataset.kcmcAppBase, location.href);
      return app.origin === location.origin && app.search === '' && app.hash === ''
        && app.pathname.endsWith('/') ? app : null;
    } catch (_) {
      return null;
    }
  };
  const safePath = (path, app) => {
    if (typeof path !== 'string' || !/^\/[A-Za-z0-9_./-]*$/.test(path)
        || !path.startsWith(app.pathname) || path.includes('//')) return false;
    try {
      const url = new URL(path, app.origin);
      return url.origin === app.origin && url.pathname === path && url.search === '' && url.hash === '';
    } catch (_) {
      return false;
    }
  };
  const markedEntry = (entry, app) => {
    try {
      if (typeof entry.getState !== 'function' || typeof entry.key !== 'string' || entry.key === ''
          || !Number.isInteger(entry.index) || entry.index < 0) return false;
      const state = entry.getState();
      if (!plainObject(state) || !Object.hasOwn(state, stateKey)) return false;
      const marker = state[stateKey];
      return plainObject(marker) && Object.keys(marker).sort().join(',') === 'base,index,key,origin,path,version'
        && marker.version === 1 && marker.base === app.pathname && marker.origin === app.origin
        && marker.key === entry.key && marker.index === entry.index && safePath(marker.path, app);
    } catch (_) {
      return false;
    }
  };

  // Private documents deliberately hide their historical URL. Mark this native
  // entry with only its app boundary and path, preserving unrelated entry state.
  // No query, fragment, account data, extra entry or separate history store is used.
  try {
    const navigation = window.navigation;
    const current = navigation?.currentEntry;
    const app = links.length ? appFor(links[0]) : null;
    if (app && current && typeof current.getState === 'function'
        && typeof navigation.updateCurrentEntry === 'function'
        && typeof current.key === 'string' && current.key !== ''
        && Number.isInteger(current.index) && current.index >= 0 && safePath(location.pathname, app)) {
      const state = current.getState();
      if (state === undefined || state === null || plainObject(state)) {
        navigation.updateCurrentEntry({state: {...(state ?? {}), [stateKey]: {
          version: 1, base: app.pathname, origin: app.origin, path: location.pathname,
          key: current.key, index: current.index,
        }}});
      }
    }
  } catch (_) {
    // Unsupported or unavailable entry state leaves the ordinary local link intact.
  }

  links.forEach((link) => {
    link.addEventListener('click', (event) => {
      // Modified clicks and direct entries keep the ordinary, local fallback link.
      if (event.defaultPrevented || event.button !== 0 || event.metaKey
          || event.ctrlKey || event.shiftKey || event.altKey) return;
      const app = appFor(link);
      if (!app) return;

      // Edge/Chromium can identify the previous entry without exposing a referrer.
      // Check adjacency as well as origin so an omitted external entry is never used.
      let authoritative = false;
      try {
        const navigation = window.navigation;
        if (typeof navigation?.canGoBack === 'boolean' && typeof navigation.entries === 'function'
            && navigation.currentEntry) {
          authoritative = true;
          if (!navigation.canGoBack) return;
          const current = navigation.currentEntry;
          if (typeof current.key !== 'string' || current.key === ''
              || !Number.isInteger(current.index) || current.index < 0) return;
          const entries = navigation.entries();
          const position = entries.findIndex((entry) => entry.key === current.key);
          const previousEntry = position > 0 ? entries[position - 1] : null;
          if (previousEntry && Number.isInteger(current.index)
              && previousEntry.index === current.index - 1 && previousEntry.key !== current.key) {
            if (previousEntry.url === null) {
              if (markedEntry(previousEntry, app)) {
                event.preventDefault();
                history.back();
              }
              return;
            }
            let previous;
            try {
              previous = new URL(previousEntry.url);
            } catch (_) {
              return;
            }
            if (previous.origin === location.origin && previous.pathname.startsWith(app.pathname)
                && previous.href !== location.href) {
              event.preventDefault();
              history.back();
              return;
            }
          }
          // A known unsafe/unavailable previous entry must use the fixed local link.
          return;
        }
      } catch (_) {
        if (authoritative) return;
        // Other browsers retain the referrer check or the ordinary fallback link.
      }

      if (history.length < 2 || !document.referrer) return;
      let previous;
      try {
        previous = new URL(document.referrer);
      } catch (_) {
        return;
      }
      // Restrict enhancement to an actual referrer inside this same app.
      if (previous.origin !== location.origin
          || !previous.pathname.startsWith(app.pathname)
          || (previous.pathname === location.pathname && previous.search === location.search)) return;
      event.preventDefault();
      history.back();
    });
  });
  document.documentElement.dataset.kcmcNavigationReady = 'true';
})();
