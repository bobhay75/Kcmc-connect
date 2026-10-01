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

/* Tony's visible photo refresh. Public page only; no publishing or private-data access. */
(() => {
  'use strict';
  const home = document.querySelector('[data-view="home"]');
  if (!home || home.querySelector('[data-family-welcome]')) return;
  const churchPhoto = 'https://static.wixstatic.com/media/15d3f9_9c56441e59bd4f2a9763d79278fc1da4~mv2.jpg';
  const kidsPhoto = 'https://static.wixstatic.com/media/15d3f9_c62929ab03a84ac19805d8d57512700c~mv2.jpg';
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

  // Keep the existing local hero photo unless the church's published image loads.
  const hero = home.querySelector('[data-hero-gallery]');
  const firstPhoto = hero?.querySelector('[data-hero-photo]');
  const serviceCard = hero?.querySelector('.hero-card');
  if (firstPhoto && serviceCard) {
    const probe = new Image();
    probe.decoding = 'async';
    probe.referrerPolicy = 'no-referrer';
    probe.addEventListener('load', () => {
      if (!probe.naturalWidth) return;
      firstPhoto.src = churchPhoto;
      firstPhoto.width = 1066;
      firstPhoto.height = 532;
      firstPhoto.alt = 'Front of Kimberling City Methodist Church, from the church website';
      firstPhoto.dataset.caption = 'Church exterior • from KCMC’s published Visit page';
      const caption = hero.querySelector('[data-hero-caption]');
      if (!firstPhoto.hidden && caption) caption.textContent = firstPhoto.dataset.caption;
      const details = make('div', 'hero-service-info');
      while (serviceCard.firstChild) details.append(serviceCard.firstChild);
      const figure = make('figure', 'hero-church-window');
      const image = make('img', 'hero-church-photo');
      image.src = churchPhoto;
      image.alt = firstPhoto.alt;
      image.width = 1066;
      image.height = 532;
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', () => figure.remove(), {once: true});
      const source = make('figcaption', 'photo-source');
      source.append(link('Church photo · KCMC Visit page', visitPage, ''));
      figure.append(image, source);
      serviceCard.classList.add('hero-card-with-photo');
      serviceCard.append(figure, details);
    }, {once: true});
    probe.src = churchPhoto;
  }

  const section = make('section', 'section family-welcome');
  section.setAttribute('data-family-welcome', '');
  section.setAttribute('aria-labelledby', 'family-welcome-title');
  const layout = make('div', 'wrap family-welcome-grid');
  const figure = make('figure', 'family-photo-frame');
  const image = make('img', 'family-photo');
  image.alt = 'Children and adults in a group photograph published on KCMC’s youth ministry page';
  image.width = 2048;
  image.height = 1535;
  image.loading = 'lazy';
  image.decoding = 'async';
  image.referrerPolicy = 'no-referrer';
  const source = make('figcaption', 'photo-source');
  source.append(link('Photo · KCMC Youth page', youthPage, ''));
  image.addEventListener('error', () => {
    figure.hidden = true;
    layout.classList.add('family-without-photo');
  }, {once: true});
  image.src = kidsPhoto;
  figure.append(image, source);
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
  else hero?.after(section);
})();
