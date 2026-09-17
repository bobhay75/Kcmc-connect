(() => {
  'use strict';
  const fields = ['id', 'title', 'date', 'time', 'location'];

  function canFill(description, expected, current) {
    return typeof description === 'string' && description.trim() === '' &&
      expected !== null && typeof expected === 'object' &&
      current !== null && typeof current === 'object' &&
      fields.every(key => typeof expected[key] === 'string' && expected[key] === current[key]);
  }
  if (typeof module === 'object' && module.exports) module.exports = { canFill };
  if (typeof document === 'undefined') return;

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
    // Recheck the live form: the user may have edited text or the event since page load.
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
