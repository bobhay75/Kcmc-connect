(() => {
  'use strict';
  const fields = ['id', 'title', 'date', 'time', 'location'];

  function canFill(description, expected, current) {
    return typeof description === 'string' && description.trim() === '' &&
      expected !== null && typeof expected === 'object' &&
      current !== null && typeof current === 'object' &&
      fields.every(key => typeof expected[key] === 'string' && expected[key] === current[key]);
  }

  function countChangedValues(baseline, current) {
    if (!Array.isArray(baseline) || !Array.isArray(current) || baseline.length !== current.length) return -1;
    return current.reduce((count, value, index) => count + Number(value !== baseline[index]), 0);
  }

  if (typeof module === 'object' && module.exports) module.exports = { canFill, countChangedValues };
  if (typeof document === 'undefined') return;

  function setupPublishingReviewGuard() {
    const form = document.querySelector('form[action$="admin/save.php"]');
    if (!form) return;
    const submit = form.querySelector('button[type="submit"]');
    if (!submit) return;

    const tracked = [...form.querySelectorAll('input[name], textarea[name], select[name]')]
      .filter(control => !['csrf', 'confirm_publish'].includes(control.name) && control.type !== 'hidden');
    const valueOf = control => (control.type === 'checkbox' || control.type === 'radio')
      ? (control.checked ? control.value : '')
      : control.value;
    const baseline = tracked.map(valueOf);

    const guard = document.createElement('section');
    guard.className = 'panel publishing-review-guard';
    guard.setAttribute('aria-labelledby', 'publishing-review-title');
    guard.innerHTML = '<h2 id="publishing-review-title">Review before publishing</h2>' +
      '<p class="muted"><strong data-publish-change-count>0</strong> changed field(s) in this publishing form.</p>' +
      '<label data-publish-confirm-label><input type="checkbox" name="confirm_publish" value="1" disabled> <span>I reviewed these changes and they are ready to publish.</span></label>' +
      '<p class="muted" role="status" aria-live="polite" data-publish-review-status>No changes detected yet.</p>';
    guard.style.marginBottom = '16px';
    const confirm = guard.querySelector('input[name="confirm_publish"]');
    const confirmLabel = guard.querySelector('[data-publish-confirm-label]');
    const countNode = guard.querySelector('[data-publish-change-count]');
    const reviewStatus = guard.querySelector('[data-publish-review-status]');
    confirm.style.width = 'auto';
    confirm.style.margin = '0';
    confirmLabel.style.display = 'flex';
    confirmLabel.style.alignItems = 'flex-start';
    confirmLabel.style.gap = '10px';
    confirmLabel.style.fontWeight = '700';
    submit.parentNode.insertBefore(guard, submit);

    function changedCount() {
      return countChangedValues(baseline, tracked.map(valueOf));
    }

    function refresh() {
      const count = changedCount();
      countNode.textContent = String(Math.max(0, count));
      confirm.disabled = count <= 0;
      if (count <= 0) confirm.checked = false;
      submit.disabled = count <= 0 || !confirm.checked;
      if (count <= 0) reviewStatus.textContent = 'No changes detected yet.';
      else if (!confirm.checked) reviewStatus.textContent = `${count} changed field${count === 1 ? '' : 's'} detected. Review them, then confirm before publishing.`;
      else reviewStatus.textContent = `${count} changed field${count === 1 ? '' : 's'} reviewed. Publishing is enabled.`;
    }

    form.addEventListener('input', refresh);
    form.addEventListener('change', refresh);
    form.addEventListener('click', () => setTimeout(refresh, 0));
    confirm.addEventListener('change', refresh);
    form.addEventListener('submit', event => {
      refresh();
      if (changedCount() < 1 || !confirm.checked) {
        event.preventDefault();
        reviewStatus.textContent = 'Review the changed fields and confirm that they are ready to publish.';
        guard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        confirm.focus();
      }
    });
    refresh();
  }

  setupPublishingReviewGuard();

  const buttons = [...document.querySelectorAll('[data-use-event-description]')];
  const allButton = document.querySelector('[data-fill-event-descriptions]');
  const status = document.querySelector('[data-description-recovery-status]');
  if (!buttons.length || !status) return;

  function fill(button) {
    const row = button.closest('.row');
    const input = row?.querySelector('textarea[name$="[description]"]');
    const sourceText = button.closest('details')?.querySelector('[data-description-suggestion]');
    if (!row || !input || !sourceText) return false;
    let expected;
    try { expected = JSON.parse(button.dataset.descriptionReference); } catch (_) { return false; }
    const current = Object.fromEntries(fields.map(key => [key, row.querySelector(`[name$="[${key}]"]`)?.value]));
    if (!canFill(input.value, expected, current)) return false;
    const text = sourceText.textContent.trim();
    if (!text) return false;
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    button.closest('details').open = true;
    return true;
  }

  buttons.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      const added = fill(button);
      status.textContent = added
        ? 'Description added to this form only. Review it before using Publish changes. Nothing has been published.'
        : 'Left unchanged: this description is filled, or the event details no longer match the reference.';
      if (added) button.closest('.row').querySelector('textarea[name$="[description]"]').focus();
    });
  });
  if (allButton) {
    allButton.hidden = false;
    allButton.addEventListener('click', () => {
      const added = buttons.reduce((count, button) => count + Number(fill(button)), 0);
      status.textContent = added
        ? `${added} description${added === 1 ? '' : 's'} added to this form only. Review before Publish changes. Nothing has been published.`
        : 'Nothing changed. Filled descriptions and events with changed details were left alone.';
    });
  }
})();
