const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const scriptPath = path.join(root, 'KCMC-Connect-Phase6-Recreated/admin/event-descriptions.js');
const script = fs.readFileSync(scriptPath, 'utf8');
const { countChangedValues } = require(scriptPath);

function check(condition, message) {
  if (!condition) {
    console.error(`FAIL: ${message}`);
    process.exit(1);
  }
  console.log(`PASS: ${message}`);
}

check(typeof countChangedValues === 'function', 'changed-field counter is exported for deterministic testing');
check(countChangedValues(['a', 'b'], ['a', 'b']) === 0, 'unchanged values produce zero changes');
check(countChangedValues(['a', 'b'], ['x', 'b']) === 1, 'one edited field produces one change');
check(countChangedValues(['a', 'b', 'c'], ['x', 'y', 'c']) === 2, 'multiple edited fields are counted independently');
check(countChangedValues(['a'], ['a', 'b']) === -1, 'shape mismatch fails closed');

for (const marker of [
  'Review before publishing',
  'data-publish-change-count',
  'name="confirm_publish"',
  'I reviewed these changes and they are ready to publish.',
  "form.addEventListener('submit'",
  'submit.disabled = count <= 0 || !confirm.checked',
  "form.addEventListener('input', refresh)",
  "form.addEventListener('change', refresh)",
]) {
  check(script.includes(marker), `Publishing Desk guard contains ${marker}`);
}

check(script.includes("input.dispatchEvent(new Event('input', { bubbles: true }))"), 'description helper notifies review guard after programmatic changes');
console.log('Publishing review JavaScript contract passed.');
