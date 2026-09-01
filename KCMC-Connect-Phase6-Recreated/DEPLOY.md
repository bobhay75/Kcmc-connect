# KCMC Connect 3.0 — cPanel Deployment

The repository deploys this directory to `/home/bobsome1/public_html/kcmc-connect/` through the root `.cpanel.yml` file.

## Preserved production data

Deployment intentionally preserves:

- `config.php` — optional server-only configuration
- `data/content.json` — live Publishing Desk content
- `data/private/` — member accounts, invitations, prayer requests, login throttles and audit records
- `backups/` — automatic public-content backups

Never copy `data/private/` into Git or a public download. Apache denies web access to both `data/` and `backups/`.

Newsletter page photographs are also prohibited. Deployment removes the retired August page images; only extracted text and separately approved ministry photos belong in the app.

## First-run recovery setup

1. Confirm PHP 8.1+, HTTPS and writable `data/`, `data/private/` and `backups/` directories.
2. Set a long, random `KCMC_SETUP_KEY` environment variable in cPanel. Do not commit or email it.
3. Open `/kcmc-connect/admin/setup.php` and create the recovery-administrator account.
4. Remove `KCMC_SETUP_KEY` from the server immediately after setup.
5. From **Member access**, invite Tony Blevins and Barry Smith separately as **Pastor administrator**. Each invitation expires after seven days and creates a separate password.
6. Invite members and prayer-team participants only after confirming their email addresses and roles.

The recovery administrator can restore access and publish public content, but the application deliberately prevents that role from reading, submitting or moderating prayer requests.

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

No shared administrator password or secret application backdoor is supported.
