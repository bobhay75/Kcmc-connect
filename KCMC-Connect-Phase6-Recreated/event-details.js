/* Progressive enhancement: original artwork remains a link without JavaScript. */
(() => {
  'use strict';
  if (!window.HTMLDialogElement) return;
  const dialog = document.createElement('dialog');
  dialog.className = 'event-detail-dialog';
  dialog.setAttribute('aria-labelledby', 'eventDetailTitle');
  dialog.innerHTML = '<div class="event-detail-toolbar"><button type="button" autofocus>Close</button></div><img class="event-detail-image" alt=""><div class="event-detail-copy"><h2 id="eventDetailTitle"></h2><p class="event-detail-schedule"></p><p class="event-detail-location"></p><p class="event-detail-description"></p><a class="event-detail-original" target="_blank" rel="noopener noreferrer">Open original slide in a new tab</a></div>';
  document.body.append(dialog);
  let opener;
  const close = dialog.querySelector('button');
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { if (opener?.isConnected) opener.focus(); });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-event-details]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const card = link.closest('.event-card, .eventx');
    const sourceImage = link.querySelector('img');
    if (!card || !sourceImage) return;
    const title = card.querySelector('h3, h2')?.textContent || 'Event details';
    const date = card.querySelector('time')?.textContent || '';
    const schedule = card.querySelector('.event-when, small')?.textContent || '';
    const location = card.querySelector('.detail')?.textContent || '';
    const description = card.querySelector('.event-description')?.textContent || '';
    dialog.querySelector('h2').textContent = title;
    const image = dialog.querySelector('img');
    image.src = sourceImage.src;
    image.alt = sourceImage.alt;
    dialog.querySelector('.event-detail-schedule').textContent = card.matches('.event-card') ? date + ' · ' + schedule : schedule;
    dialog.querySelector('.event-detail-location').textContent = location;
    dialog.querySelector('.event-detail-description').textContent = description;
    dialog.querySelector('.event-detail-original').href = link.href;
    opener = link;
    dialog.showModal();
    event.preventDefault();
  });
})();
