# KCMC welcome homepage

Implements Robert's approved navy/gold welcome design: KCMC above a left-facing gold ichthys, a fixed authentic church photograph, Welcome Home, Plan Your Visit and Watch Online, three service times, and Events / Prayer Requests / Church Family links.

## Authentic photograph

`assets/visuals/kcmc-building-original-20261018.jpg` is the exact original supplied as `1000462117.jpg`. SHA256: `064cc83e891de756d47c022725be4e7e1fd1d15119a972aee7e1a58e38c6f226`. No generative architectural edit, repainting, or geometry change is used. The natural sky remains part of the photograph. Desktop framing uses CSS cover; phones show the whole original with the heading and buttons below it.

## Scope

Public homepage, its new stylesheet, public cache asset/version list, manifest icon versions, and two raster icon sizes. Original app routes and the native dropdown remain available. Existing family photos remain below the opening view. No account, role, owner policy, configuration, prayer, timeclock, payroll, content store, delivery or cron code is changed.

The PNGs are deterministic native branding assets built by `tools/build-welcome-icons.py` with white KCMC text above a gold fish whose rounded head is left and tail crossing is right. All pages retain the existing icon paths. Public worker privacy checks and PR155 notification behavior remain intact.

## Verification

`node tests/welcome-home-source.cjs` verifies the original photo identity, fixed hero, style ordering, anonymous cache refresh and retained navigation guard. `python3 tests/pwa-icons-integrity.py` decodes PNGs and checks dimensions, CRCs and malformed payload refusal. The existing app-theme and Tony browser suites now test the approved opening view at phone/desktop widths, retaining their route, private-page, keyboard, touch, content and security coverage. Historical carousel handlers and worker behavioral tests remain unchanged.

Local PHP is unavailable. The managed visual-preview supervisor failed with `bwrap: Can't mount proc on /newroot/proc: Operation not permitted`. Real PHP/browser acceptance must pass in GitHub CI before release approval.

## Release boundary

This is source preparation, not a host installation. The host currently has the scoped PR159 livecalendar repair from the owner-guided transcript. Do not overwrite that installation or apply canonical index.php without a guarded comparison that preserves the installed livecalendar variant and unrelated host records. Prepare and review a scoped backup/rollback installer after exact-head CI. No merge or deployment is included here.
