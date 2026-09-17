# KCMC Connect 3.0 — cPanel Deployment

The repository deploys this directory to `/home/bobsome1/public_html/kcmc-connect/` through the root `.cpanel.yml` file.

## Preserved production data

Deployment intentionally preserves:

- `config.php` — optional server-only configuration
- `data/content.json` — live Publishing Desk content
- `data/private/` — member accounts, invitations, prayer requests, login throttles and audit records
- `backups/` — automatic public-content backups

Never copy `data/private/` into Git or a public download. Apache denies web access to both `data/` and `backups/`.

For production, set `KCMC_PRIVATE_DATA_DIR` to a writable directory outside `public_html`, for example `/home/bobsome1/kcmc-private`. That external directory supersedes the in-tree `data/private/` fallback and holds accounts, invitations, prayers, audit records, Sermon Assistant requests, imported decks and decision history. Give it mode `0750`, keep its files at `0640`, and include it in the private server backup plan. The repository deployment neither replaces nor backs up that external directory.

Newsletter page photographs are also prohibited. Deployment removes the retired August page images; only extracted text and separately approved ministry photos belong in the app.

## First-run recovery setup

1. Confirm PHP 8.1+, HTTPS and writable `data/`, `data/private/` and `backups/` directories.
2. Set a long, random `KCMC_SETUP_KEY` environment variable in cPanel. Do not commit or email it.
3. Open `/kcmc-connect/admin/setup.php` and create the recovery-administrator account.
4. Remove `KCMC_SETUP_KEY` from the server immediately after setup.
5. While signed in as the recovery administrator, open **Member access** and invite Tony Blevins and Barry Smith separately as **Pastor administrator**, using each pastor's verified email address. Each identity-bound invitation expires after seven days and creates a separate password.
6. Invite members and prayer-team participants only after confirming their email addresses and roles.

The recovery administrator can restore access and publish public content, but the application deliberately prevents that role from reading, submitting or moderating prayer requests.

The legacy `/member/first-login.php` endpoint is retained only as a no-store HTTP 410 notice. It cannot accept credentials or create an account. Do not configure or distribute a shared pastor onboarding code.

## Private Sermon Assistant setup

1. Create `KCMC_PRIVATE_DATA_DIR` as an absolute, non-symlink directory outside `/home/bobsome1/public_html/` and confirm PHP can write it without using world-writable permissions. The app rejects a relative, missing or symlinked override, and compares the resolved location with both the application root and PHP's server `DOCUMENT_ROOT` so a sibling directory elsewhere under `public_html` is rejected too.
2. Before enabling that environment variable on an existing installation, put the site in maintenance mode and copy the current `data/private/` contents into the external directory while preserving private ownership and `0640` file permissions. Verify `users.json`, invitations, prayers, login throttles and `audit.ndjson` in the new location before reopening sign-in; otherwise the existing accounts and privacy state will appear absent.
3. Generate a high-entropy `KCMC_SERMON_IMPORT_KEY` of at least 32 characters. Configure it as a server environment secret for KCMC Connect and as an environment secret for the trusted private builder. Those are the only two places that may receive the value; do not commit, upload, email or display it in a browser.
4. Keep the approved PowerPoint archive, Front Porch template and Python builder on a trusted private workstation or worker. Do not install a web endpoint that invokes Python, a shell, cron-on-demand or user-supplied paths.
5. Set cPanel/PHP limits that can safely accommodate the 100 MB application cap: `upload_max_filesize` of at least `100M`, `post_max_size` above the combined multipart request (at least `103M`), and `memory_limit` of at least `256M`. Reduce the application cap or implement streaming before launch if the host cannot provide that memory safely.
6. Sign in as a pastor or recovery administrator, open **Sermon Assistant**, create the ordered request, and download its exact request JSON.
7. Run the private builder against that request. Transfer only its exact editable `.pptx`, `approval.json`, and HMAC-signed `kcmc-import.json` back to KCMC Connect.
8. Upload all three files together. The app rejects an unknown job, stale request, hash mismatch, invalid signature, incomplete item, failed QA, pre-approved manifest or `autopublish:true` result.
9. Sign in as a pastor administrator, download the exact stored deck, visually review it, compare the displayed SHA-256, and re-enter the pastor's current password to approve or request changes.

A recovery administrator may create requests and import correctly signed files, but only a `pastor_admin` may record either decision. The server derives the decision identity and time from the authenticated session. Artifacts remain under `KCMC_PRIVATE_DATA_DIR`; authenticated download streams verified bytes without exposing a filesystem path. A recorded approval does not publish, email, schedule or otherwise distribute a deck.

The builder's optional `approval.html` is an offline convenience only. It is non-authoritative and must not be uploaded or treated as a pastor decision.

## Prayer privacy checks

Before launch, verify all of the following:

1. A signed-out visitor sees only the public Prayer & Care gateway and cannot submit or view a request.
2. A member can submit a request. The default audience is pastors and the prayer team.
3. A member request marked for sharing remains pending until a pastor administrator approves it.
4. Tony or Barry can approve, keep private or close a request.
5. A prayer-team account can view the confidential inbox but cannot approve publication.
6. A recovery-administrator account receives HTTP 403 on prayer-team, prayer-submission and prayer-approval routes and sees no prayer wall.
7. Private responses include `Cache-Control: no-store` and `X-Robots-Tag: noindex`.

## Deployment checks

1. Confirm the homepage, current bulletin and all navigation views.
2. Confirm worship times are 8:00 AM, 9:15 AM and 10:30 AM against the church's current public schedule.
3. Confirm Chrome DevTools shows the `kcmc-connect-v3.0.0` service worker cache.
4. Publish a harmless bulletin-note change and verify it survives another deployment.
5. Confirm `config.php`, `data/private/` and `backups/` were not overwritten.
6. Confirm `/admin/setup.php` redirects to sign-in after the first account exists.
7. Confirm no file or URL under `assets/newsletter/` is present in the deployed app.
8. Confirm a signed-out request for `/admin/service-decks.php` reaches sign-in with `Cache-Control: no-store` and `X-Robots-Tag: noindex`.
9. Confirm the public content API contains no Sermon Assistant job, request, deck, manifest or approval data.
10. Confirm both administrator roles can prepare and import, but a recovery administrator receives HTTP 403 when attempting either pastor decision.
11. Import a deliberately altered or wrongly signed test package and confirm it is rejected without changing the job; then import the exact signed three-file package.
12. Confirm every request, imported artifact and decision record is below the external `KCMC_PRIVATE_DATA_DIR`, and no deck is reachable by a direct public URL.
13. Confirm pastor approval requires current-password reauthentication and the exact reviewed deck hash, and that approval causes no public-content change.

No shared administrator password, shared onboarding secret or secret application backdoor is supported.
