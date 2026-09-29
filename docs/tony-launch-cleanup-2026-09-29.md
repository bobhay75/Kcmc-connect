# KCMC: Tony launch cleanup — 29 September 2026

## Scope
Apply the recovered meeting directions without changing the church name, authentication/roles, private stores, giving processor, hosting, or unrelated projects. The recovered transcript covers approximately 13:14–31:24; the opening portion remains unverified. This is not authorization to expose member data or publish a new directory.

## Public changes
- Warm welcome, accessible native dropdown, prominent existing church giving destination.
- No bridge artwork or monthly-newsletter content in public output. The old newsletter URL redirects to current updates. Original stored content is preserved.
- The source exclusion is the existing monthly `news` object and announcement ID `sep-news-16`, not a keyword ban on newsletters. Mary Lou’s Friday updates remain allowed.
- Message terminology replaces visible sermon labels. Existing technical IDs are retained for compatibility.
- Replace stale featured-video claims and the unverified short link with the official Facebook archive. Do not describe archive-link checks as playback validation.
- Rotating supplied photos: eight-second interval, pause/previous/next, reduced-motion stopped by default, no-JavaScript static image, historical captions.
- Keep note text and blank spaces unchanged; Publishing Desk states that only author-supplied and approved answers may be published. This does not retroactively correct notes without their originals.

## Photo provenance
Derived from the owner’s supplied screenshots, cropped only to remove phone/Facebook interface, resized and compressed. No people or attendance were generated or added.

| Local photo | Source file | Date visible on source |
| --- | --- | --- |
| `kcmc-building-2024.webp` | `1000001725.jpg` | May 29, 2024 |
| `kcmc-worship-2017.webp` | `1000001731.jpg` | June 5, 2017 |
| `kcmc-stage-2014.webp` | `1000001733.jpg` | October 29, 2014 |

These are archival, not proof of current attendance or coverage of all three current services. Obtain current approved photos for the final church launch and confirm church photo-permission practice, especially for children and individual interviews. Do not reintroduce a bridge image from the other supplied screenshots.

## Verification
Run `bash tests/security-contract.sh`, `bash tests/production-smoke-contract.sh`, `php tests/tony-launch-cleanup-contract.php`, and the two browser harnesses in `.github/workflows/tony-launch-cleanup.yml`. Tests use local fixtures, never real private records or production writes. CI uploads its exact commit, logs and mobile/desktop screenshots. Browser acceptance requires Playwright Chromium; PHP contracts require cURL and OpenSSL.

## Deployment gate and rollback
The cloud cPanel browser was not authenticated during this work. Do not report these changes as live until deployment and readback succeed.

1. Authenticate on the existing server249 cPanel account; inspect only `/home/bobsome1/repositories/Kcmc-connect-live` and `/home/bobsome1/public_html/kcmc-connect/`.
2. Record the live and repository revision, check for host-only edits, and back up affected live code plus `data/content.json` outside `public_html`. Keep backups private.
3. Inspect the tested PR diff at the approved commit. Deploy only the reviewed KCMC code, preserve `config.php`, `data/private/`, backups and live content. Do not use a blind full-file content overwrite.
4. `.cpanel.yml` excludes existing `data/content.json`. Consequently deploying this code does not itself add the repository’s missing public event records. Reconcile those separately against a private backup, by exact IDs and source evidence; preserve all host-only records and resolve conflicts before writing.
5. Run the read-only `tools/production-smoke.sh` on the live app, verify new service-worker activation on a test device, open every public route and giving/archive link, and check the four private readability screens with an authorized account. Do not make a donation, submit forms or send invitations as part of a read-only check.
6. For rollback restore the backed-up affected code and service worker; do not roll back private stores or overwrite live editorial content. Confirm login and public routes again.

The final migration onto church-controlled hosting, a name change, new directories, new ministries and any live outreach remain separate approval decisions. Tony controls Services/Announcements/Dropbox archive cleanup.

## Official link verification
The church website `https://www.kimberlingcitymethodist.com/giving` links to `https://www.simplechurchgiving.net/app/giving/umckc`; this destination is retained. The website also lists the current 8:00, 9:15 and 10:30 Sunday service times. No giving transaction was made. Facebook playback still requires manual acceptance because automated retrieval may be restricted.
