(() => {
  'use strict';
  const root = document.querySelector('[data-invitation-delivery]');
  if (!root) return;
  const confirm = root.querySelector('[data-invite-confirm]');
  const status = root.querySelector('[data-invite-status]');
  const manual = root.querySelector('[data-invite-manual]');
  const message = root.querySelector('[data-invite-message]');
  const link = root.querySelector('[data-invite-link]');
  const recipient = root.querySelector('[data-invite-email]');
  const buttons = [...root.querySelectorAll('[data-copy-invitation]')];
  const compose = [...root.querySelectorAll('[data-compose-url]')];
  if (!confirm || !status || !manual || !message || !link || !recipient) return;
  // Snapshot only the server-verified card, never a form for the next recipient,
  // current URL, document title, query parameters or clipboard contents.
  const payload = Object.freeze({message: message.value, link: link.value});
  const email = recipient.textContent.trim();
  const destinations = new Map(compose.map(a => [a, a.dataset.composeUrl]));
  let copying = false;
  let copiedMessage = false;
  const update = () => {
    buttons.forEach(button => { button.disabled = !confirm.checked || copying; });
    compose.forEach(a => {
      if (confirm.checked && !copying) {
        a.href = destinations.get(a);
        a.removeAttribute('aria-disabled');
        a.removeAttribute('tabindex');
      } else {
        a.removeAttribute('href');
        a.setAttribute('aria-disabled', 'true');
        a.setAttribute('tabindex', '-1');
      }
    });
  };
  const selectManually = (field, kind) => {
    copiedMessage = false;
    field.value = payload[kind];
    manual.open = true;
    field.focus();
    field.select();
    status.textContent = `Automatic copying is unavailable. The ${kind === 'message' ? 'email' : 'link'} for ${email} is selected; use your device’s Copy command. Nothing has been sent.`;
  };
  buttons.forEach(button => button.addEventListener('click', async () => {
    if (!confirm.checked || copying) return;
    const kind = button.dataset.copyInvitation;
    if (kind !== 'message' && kind !== 'link') return;
    const field = kind === 'message' ? message : link;
    copying = true;
    update();
    try {
      if (!window.isSecureContext || typeof navigator.clipboard?.writeText !== 'function') {
        selectManually(field, kind);
        return;
      }
      await navigator.clipboard.writeText(payload[kind]);
      // Copying only a link replaces the previously copied complete message.
      copiedMessage = kind === 'message';
      status.textContent = `${kind === 'message' ? 'Invitation email' : 'Private link'} copied for ${email}. ${kind === 'message' ? 'Open Gmail and paste it into the message body.' : 'Paste it only into a message to this recipient.'} Nothing has been sent.`;
    } catch (_) {
      copiedMessage = false;
      selectManually(field, kind);
    } finally {
      copying = false;
      update();
    }
  }));
  compose.forEach(a => a.addEventListener('click', event => {
    if (!confirm.checked || copying) { event.preventDefault(); return; }
    const isGmail = a.hasAttribute('data-invite-gmail');
    status.textContent = `${isGmail ? 'In Gmail' : 'In your email app'}, ${copiedMessage ? 'paste the copied email' : 'paste the full invitation email from the manual-copy section'}, check To: ${email}, and click Send. ${isGmail ? 'If no compose window opens, open Gmail manually.' : 'If nothing opens, use Open Gmail or copy manually.'} This page cannot confirm delivery.`;
  }));
  confirm.addEventListener('change', () => {
    copiedMessage = false;
    update();
    status.textContent = confirm.checked ? `Recipient checked: ${email}. Copy the invitation email, then open Gmail. Nothing has been sent.` : 'Check the recipient before copying or opening an email app. Nothing has been sent.';
  });
  root.querySelectorAll('[data-invite-confirm-label],[data-invite-actions],[data-invite-compose]').forEach(el => { el.hidden = false; });
  update();
})();
