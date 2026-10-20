# KCMC Tony functional corrections — review package

This offline package is for the observed PR161-installed host, with independent `main` and `livecalendar` prerequisites. It is not a full application deployment. Preserve the customized livecalendar stylesheet. Unknown or mixed files are refused; there is no force mode.

The exact source changes are pinned in `tests/fixtures/tony-functions-20261020-reviewed.json`. The transaction adapter is derived by explicit replacements from the unchanged PR161 adapter SHA256 `e405bc0cda2b7787d573fa2f436915e5d7c4339e03b511609b867ae9c01a0eb1`. Derivation expands its fixed target set, makes nested backup paths unambiguous, restores every modified target on conditional rollback, and lints every staged PHP file before any live replacement. Original security, locking, metadata, lease, interrupted-journal and unknown-edit refusal behavior is retained.

## Read-only host check

Verify the package SHA256, extract into a new private folder outside public_html, then run the checker in the bobsome1 cPanel Terminal:

```
python3 -I -B check-release.py /home/bobsome1/public_html/kcmc-connect
python3 -I -B install-functions.py check
```

Both commands are read-only and default to refusal for unexpected bytes, ownership, modes, links, prerequisites, or incomplete transactions. Send their output for review. Do not extract over the application or use an old installer with this package.

## Authorized installation only

After Robert reviews the concrete changes and approves this production release, and only when the host reports `livecalendar before`:

```
python3 -I -B install-functions.py apply --expected-variant livecalendar
```

This replaces exactly 12 existing code/assets files and adds the Front Porch photograph and public-features library (14 targets total). It does not read or change config.php, .htaccess, data/content.json, private prayer, accounts, connection requests or mail settings. Actual-byte backups and journal are outside public_html. The script executes PHP lint only, never application code, mail or migrations. sw.js is installed last. No Git operation, network fetch, background task or cron change is performed.

If apply fails, the same transaction attempts a conditional full rollback and refuses unknown concurrent edits. A later explicit rollback requires the exact printed session basename. It restores all 12 original files but conservatively retains added files when additional consumers have not been ruled out; that state is explicitly reported as not an exact original bundle. No cleanup bypass is offered. Inspect any refused recovery before proceeding.

## Read-only mail readiness

After a successful code preflight, run the host's PHP 8.2+ CLI against `mail-readiness.php`. It reads the preserved configuration and returns only enabled/ready flags, never addresses, keys, passwords or private records. It does not send or write anything. CLI environment can differ from Apache's environment, so its result does not certify web requests or inbox delivery. A real delivery test still needs an approved recipient.

## Verified service recordings

The three October 18, 2026 Facebook recordings were opened and verified on October 20. They are dated recordings, not claims of a broadcast currently being live:

- Front Porch Gospel: https://www.facebook.com/KimberlingCityMethodistChurch/videos/1653016829754297/
- Traditional Worship: https://www.facebook.com/KimberlingCityMethodistChurch/videos/1756125088830337/
- Contemporary Worship: https://www.facebook.com/KimberlingCityMethodistChurch/videos/3164538033744471

These serve as defaults until staff publish new direct video URLs. An explicit blank removes a service link. Update all three links through the Publishing Desk when the church publishes the next broadcasts.

## Acceptance still required

Verify public phone/desktop controls and actual staff publishing/connection views. Maintain each service’s separately verified Facebook video URL through the Publishing Desk; never duplicate a shared archive URL. The source does not enable welcome emails: inspect the existing authorized sender settings and verify an approved test recipient's inbox before stating production mail works. Review the bulletin from each week's approved church announcements. User approval to deploy remains separate from successful preflight.
