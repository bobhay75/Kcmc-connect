(() => {
  'use strict';
  const menu = document.getElementById('siteMenu');
  if (menu) {
    const summary = menu.querySelector('summary');
    const hoverPointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    let openedByHover = false;
    let leaveTimer = null;
    function closeMenu() {
      clearTimeout(leaveTimer);
      openedByHover = false;
      menu.open = false;
    }
    menu.addEventListener('pointerenter', event => {
      clearTimeout(leaveTimer);
      if (event.pointerType !== 'mouse' || !hoverPointer.matches || menu.open) return;
      openedByHover = true;
      menu.open = true;
    });
    menu.addEventListener('pointerleave', () => {
      if (openedByHover && !menu.contains(document.activeElement)) {
        leaveTimer = setTimeout(closeMenu, 200);
      }
    });
    // A click pins a menu that hover just opened; a second click closes it natively.
    summary.addEventListener('click', event => {
      clearTimeout(leaveTimer);
      if (openedByHover) {
        event.preventDefault();
        openedByHover = false;
        menu.open = true;
      }
    });
    menu.addEventListener('focusout', event => {
      if (event.relatedTarget && !menu.contains(event.relatedTarget)) closeMenu();
    });
    menu.addEventListener('click', event => {
      if (event.target.closest('nav a,nav button')) closeMenu();
    });
    document.addEventListener('click', event => {
      if (menu.open && !menu.contains(event.target)) closeMenu();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        closeMenu();
        summary.focus();
      }
    });
    window.addEventListener('hashchange', closeMenu);
  }

  const gallery = document.querySelector('[data-hero-gallery]');
  if (!gallery) return;
  const photos = [...gallery.querySelectorAll('[data-hero-photo]')];
  const controls = gallery.querySelector('[data-hero-controls]');
  const status = gallery.querySelector('[data-hero-status]');
  const toggle = gallery.querySelector('[data-hero-toggle]');
  if (photos.length < 2 || !controls || !toggle) return;
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
      timer = setTimeout(() => { show(current + 1, false); schedule(); }, 420000);
    }
  }
  function show(index, announce, step = 1) {
    const direction = step < 0 ? -1 : 1;
    let next = ((index % photos.length) + photos.length) % photos.length;
    // Skip unavailable frames in the requested direction; keep a usable current frame.
    let remaining = photos.length;
    while (remaining > 0 && (!photos[next].complete || photos[next].naturalWidth === 0)) {
      next = (next + direction + photos.length) % photos.length;
      remaining -= 1;
    }
    if (remaining === 0) return;
    current = next;
    photos.forEach((photo, i) => {
      photo.hidden = i !== current;
      photo.classList.toggle('is-current', i === current);
    });
    if (announce && status) status.textContent = `Photo ${current + 1} of ${photos.length}. ${photos[current].alt || ''}`;
  }
  function manualStep(step) {
    paused = true;
    show(current + step, true, step);
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

/* Tony's visible photo refresh. Public page only; no publishing or private-data access. */
(() => {
  'use strict';
  const home = document.querySelector('[data-view="home"]');
  if (!home || home.querySelector('[data-family-welcome]')) return;
  const kidsPhoto = './assets/visuals/kcmc-kids-summer-group.jpg';
  const youthPage = 'https://www.kimberlingcitymethodist.com/youth';
  const visitPage = 'https://www.kimberlingcitymethodist.com/visit';
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const link = (text, href, className) => {
    const node = make('a', className, text);
    node.href = href;
    if (href.startsWith('https://')) {
      node.target = '_blank';
      node.rel = 'noopener noreferrer';
    }
    return node;
  };

  // Keep the hero as a single rotating image plane; do not inject a second photo into the service card.

  const section = make('section', 'section family-welcome');
  section.setAttribute('data-family-welcome', '');
  section.setAttribute('aria-labelledby', 'family-welcome-title');
  const layout = make('div', 'wrap family-welcome-grid');
  const figure = make('figure', 'family-photo-frame');
  const image = make('img', 'family-photo');
  image.alt = 'Children and adults gathered in front of the stage for the KCMC summer kick-off';
  image.width = 1440;
  image.height = 1080;
  image.loading = 'lazy';
  image.decoding = 'async';
  image.referrerPolicy = 'no-referrer';
  const source = null;
  image.addEventListener('error', () => {
    figure.hidden = true;
    layout.classList.add('family-without-photo');
  }, {once: true});
  image.src = kidsPhoto;
  figure.append(image);
  const copy = make('div', 'family-welcome-copy');
  const eyebrow = make('div', 'eyebrow', 'Kids, youth & families');
  const title = make('h2', '', 'A place to belong. Room to grow.');
  title.id = 'family-welcome-title';
  const description = make('p', 'family-description', 'Faith, friendship, and a warm welcome for your family. Get to know KCMC’s children’s and youth ministries, and let our team help you plan your first visit.');
  const actions = make('div', 'btns');
  const visit = link('Plan your family’s visit', '#visit', 'btn gold');
  visit.dataset.route = 'visit';
  actions.append(visit, link('Explore kids & youth', youthPage, 'btn secondary'));
  copy.append(eyebrow, title, description, actions);
  layout.append(figure, copy);
  section.append(layout);
  const next = home.querySelector('.welcome-next');
  if (next) next.before(section);
  else home.querySelector('[data-hero-gallery]')?.after(section);
})();
