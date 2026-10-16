(() => {
  'use strict';

  document.querySelectorAll('[data-kcmc-back]').forEach((link) => {
    link.addEventListener('click', (event) => {
      // Modified clicks and direct entries keep the ordinary, local fallback link.
      if (event.defaultPrevented || event.button !== 0 || event.metaKey
          || event.ctrlKey || event.shiftKey || event.altKey) return;
      let app;
      try {
        app = new URL(link.dataset.kcmcAppBase, location.href);
      } catch (_) {
        return;
      }
      if (app.origin !== location.origin) return;

      // Edge/Chromium can identify the previous entry without exposing a referrer.
      // Check adjacency as well as origin so an omitted external entry is never used.
      try {
        const navigation = window.navigation;
        if (typeof navigation?.canGoBack === 'boolean' && typeof navigation.entries === 'function'
            && navigation.currentEntry) {
          if (!navigation.canGoBack) return;
          const current = navigation.currentEntry;
          const entries = navigation.entries();
          const position = entries.findIndex((entry) => entry.key === current.key);
          const previousEntry = position > 0 ? entries[position - 1] : null;
          if (previousEntry && Number.isInteger(current.index)
              && previousEntry.index === current.index - 1 && previousEntry.url) {
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
