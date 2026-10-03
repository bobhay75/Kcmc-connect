# Installed runtime reconciliation — 2026-10-03

This branch reconstructs the already-confirmed installed runtime on main
`2146af219d2fd23136eae1685f91a2a2caec030e`. It is source reconciliation, not a
production deployment or a claim that current host files have been retrieved.

## Evidence and reconstruction

[PR88's October 2 confirmation](https://github.com/bobhay75/Kcmc-connect/pull/88#issuecomment-5960919518)
records the owner's successful six-file Tony delivery and four-page readability
repair, and explicitly separates the newer, uninstalled caption/timing patch.
[Earlier exact-source validation](https://github.com/bobhay75/Kcmc-connect/pull/88#issuecomment-5940039577)
pins the reviewed Tony installer at `2c767fd66299524a126f39c5350de8dac1ce1f85`,
blob `24c473535af4020b65faef52255b47bc25a74bf7`, SHA-256
`0220e1a40b3b17f64988dccb3af48dad4fc87e49bb2947a4d7507de812b71bea`.

Its original pure `transform()` function was applied to pinned main sources and
photo sources `225c564138242f699a1bd31c75b5c78e65268ca7`, without invoking
installation, host access, or rollback. The resulting six files are committed
as runtime, not merely as an unapplied installer.

The four readability files are reconstructed from the saved October 1 installer
`kcmc-readability-fix.sh`, marker `KCMC_READABILITY_FIX_V1_20261001`. Its complete
source is preserved as a non-executable test fixture; only its `items`, `scope`,
`marker` and `css` assignments are evaluated for reconstruction. The resulting
2162-byte CSS block has SHA-256
`d0aa33606a160919369ecc8a6459211028ffc36592937e422cd9a5e9c8841c43`.
Removing that block restores each file byte-for-byte to main.

This is materially different from PR86's separate light-page CSS: the saved
installer scopes its light treatment to cards and preserves the dark outer
page. PR86's four runtime files and palette test are therefore excluded. The
complete source text was recovered from the saved installer (121 lines); a
terminal LF restores its recorded 5996-byte size. Raw materialization returned
HTTP 502, so the reference hash identifies recovered text rather than an
independently downloaded original. No current host-byte equality is claimed.

| Installed change | Runtime files under `KCMC-Connect-Phase6-Recreated/` |
| --- | --- |
| Church-front and family photos | `public-presentation.js`, `public-presentation.css` |
| Staff entry and public care wording | `index.php`, `care.php`, `member/login.php` |
| Installed public cache namespace | `sw.js` |
| Private-page readability | `admin/health.php`, `admin/audit.php`, `admin/timecards.php`, `member/timeclock.php` |

The accompanying JSON manifest records every output SHA-256. The source test
regenerates the six Tony outputs using the hash-verified installer and compares
all ten runtime files against their reviewed sources. It also enforces exact
runtime scope and unchanged authentication PHP, content, config example and
cPanel deployment configuration.

## Deliberately separate

- PR88's caption hiding and seven-minute timing patch are not included. The
  installed eight-second rotation and visible caption behavior remain here.
- [PR90](https://github.com/bobhay75/Kcmc-connect/pull/90)'s bright Contemporary
  Worship revision is not included.
- No event/content reconciliation, credential repair or changed access rules.
- `data/content.json`, config, private stores, prayer/member records, church
  timecards and deployment configuration are unchanged. No host data is copied
  into this branch; all browser account and timeclock fixtures are synthetic.

## Verification and production boundary

`KCMC installed runtime reconciliation` checks the exact PR head, verifies
source provenance/scope, runs existing security and PHP contracts (including
all PHP syntax), production-smoke fixtures, public and signed-in browser
acceptance, photo/fallback checks and focused staff-entry/readability checks.
The PR87 photo browser test is retained unchanged.
Evidence includes source commit, test logs and synthetic-fixture screenshots.
These results do not prove a real production credential works or certify all
site accessibility.

No deployment, merge, live form submission, email or payment is performed.
Before any later approved deployment, compare a fresh private snapshot of the
ten host files against this manifest and preserve any additional host edits.
Keep editorial/private data outside the code replacement. Older main can still
overwrite direct hotfixes until this runtime reconciliation is reviewed and
merged; merging this draft alone is not permission to deploy.
