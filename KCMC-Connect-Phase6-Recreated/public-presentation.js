(() => {
  'use strict';
  const menu = document.getElementById('siteMenu');
  if (menu) {
    const summary = menu.querySelector('summary');
    menu.addEventListener('click', event => {
      if (event.target.closest('nav a,nav button')) menu.open = false;
    });
    document.addEventListener('click', event => {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        summary.focus();
      }
    });
    window.addEventListener('hashchange', () => { menu.open = false; });
  }

  const gallery = document.querySelector('[data-hero-gallery]');
  if (!gallery) return;
  const photos = [...gallery.querySelectorAll('[data-hero-photo]')];
  const controls = gallery.querySelector('[data-hero-controls]');
  const caption = gallery.querySelector('[data-hero-caption]');
  const status = gallery.querySelector('[data-hero-status]');
  const toggle = gallery.querySelector('[data-hero-toggle]');
  if (photos.length < 2 || !controls || !caption || !toggle) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let current = 0;
  let paused = motion.matches;
  let hovering = false;
  let timer = null;
  photos.forEach(photo => { photo.loading = 'eager'; });
  controls.hidden = false;

  function onHome() {
    return gallery.closest('[data-view]')?.classList.contains('active') !== false;
  }
  function schedule() {
    clearTimeout(timer);
    timer = null;
    toggle.textContent = paused ? 'Play photos' : 'Pause photos';
    if (!paused && !hovering && !document.hidden && onHome()) {
      timer = setTimeout(() => { show(current + 1, false); schedule(); }, 8000);
    }
  }
  function show(index, announce) {
    const next = (index + photos.length) % photos.length;
    // Never replace a usable frame with a broken or not-yet-loaded image.
    if (!photos[next].complete || photos[next].naturalWidth === 0) return;
    current = next;
    photos.forEach((photo, i) => {
      photo.hidden = i !== current;
      photo.classList.toggle('is-current', i === current);
    });
    caption.textContent = photos[current].dataset.caption || '';
    if (announce && status) status.textContent = `Photo ${current + 1} of ${photos.length}. ${caption.textContent}`;
  }
  function manualStep(step) {
    paused = true;
    show(current + step, true);
    schedule();
  }
  gallery.querySelector('[data-hero-previous]')?.addEventListener('click', () => manualStep(-1));
  gallery.querySelector('[data-hero-next]')?.addEventListener('click', () => manualStep(1));
  toggle.addEventListener('click', () => { paused = !paused; schedule(); });
  // Focusing content stops automatic changes until explicitly restarted.
  gallery.addEventListener('focusin', event => {
    clearTimeout(timer);
    if (event.target !== toggle) { paused = true; schedule(); }
  });
  gallery.addEventListener('mouseenter', () => { hovering = true; schedule(); });
  gallery.addEventListener('mouseleave', () => { hovering = false; schedule(); });
  document.addEventListener('visibilitychange', schedule);
  window.addEventListener('hashchange', schedule);
  motion.addEventListener('change', () => { paused = true; schedule(); });
  schedule();
})();
