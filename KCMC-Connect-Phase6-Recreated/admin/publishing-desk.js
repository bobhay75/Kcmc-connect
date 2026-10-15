'use strict';
(() => {
  const form = document.querySelector('form[data-publishing-form]');
  if (!form) return;
  const status = document.querySelector('[data-publishing-save-status]');
  const latest = document.querySelector('[data-publishing-latest]');
  let saving = false;
  form.addEventListener('submit', async event => {
    if (event.defaultPrevented) return; // Preserve the existing changed-fields review guard.
    event.preventDefault();
    if (saving) return;
    saving = true;
    latest.hidden = true;
    const payload = new FormData(form);
    form.dispatchEvent(new CustomEvent('kcmc:publish-start'));
    status.textContent = 'Publishing…';
    try {
      const response = await fetch(form.action, {method: 'POST', credentials: 'same-origin', headers: {'Accept': 'application/json'}, body: payload});
      if (response.redirected || response.status === 401 || response.status === 403) throw new Error('Sign in again to continue. Your input is still here.');
      const data = await response.json();
      if (!response.ok || !data.ok) {
        if (response.status === 409 || response.status === 428) latest.hidden = false;
        throw new Error(data.error || 'The changes were not published. Your input is still here.');
      }
      form.elements.namedItem('version').value = data.version;
      form.dispatchEvent(new CustomEvent('kcmc:published'));
      status.textContent = 'Published. Your previous content was backed up. Any further edits still need review.';
    } catch (error) {
      status.textContent = error.message || 'The changes were not published. Your input is still here.';
    } finally {
      saving = false;
      form.dispatchEvent(new CustomEvent('kcmc:publish-finished'));
    }
  });
})();
