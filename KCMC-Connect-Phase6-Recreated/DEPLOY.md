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
5. From **Member access**, invite each person who should serve as a **Pastor administrator** separately. Each invitation expires after seven days and creates a separate password.
6. Invite members and prayer-team participants only after confirming their email addresses and roles.

The recovery administrator can restore access and publish public content, but the application deliberately prevents that role from reading, submitting or moderating prayer requests.

## Invitation email configuration

Direct invitation email is **disabled by default**. Manual recipient-checked delivery remains available until direct mail is deliberately enabled.

### cPanel-friendly path

Because `config.php` is server-only, denied by Apache and preserved across deployments, shared cPanel hosting may configure direct mail there without committing settings to Git:

```php
<?php
return [
    'church_email' => 'secretary@umckc.org',
    'session_name' => 'KCMC_CONNECT_V3',
    'invitation_mail_enabled' => true,
    'invitation_from' => 'AUTHORIZED-SENDER@YOUR-DOMAIN',
    'invitation_from_name' => 'KCMC Connect',
];
```

Use an address that the hosting account/domain is actually authorized to send as. Do not copy the placeholder address literally.

### Environment-variable path

Environment variables take precedence over `config.php` when present:

1. Set `KCMC_INVITATION_MAIL_ENABLED=1`.
2. Set `KCMC_INVITATION_FROM` to a valid authorized sender address.
3. Optionally set `KCMC_INVITATION_FROM_NAME` (default: `KCMC Connect`).

### Verify before relying on direct mail

1. Create a test invitation to an address you control and explicitly check **Email this invitation now**.
2. Verify the app reports that the configured server mail transport accepted the message.
3. Independently confirm inbox receipt. A successful PHP `mail()` handoff is not proof of final delivery.
4. If delivery fails, disable direct sending and use the existing manual/Gmail handoff until cPanel mail routing, SPF/DKIM and sender authorization are verified.

Never put invitation tokens, SMTP credentials or mail secrets in Git.

## Web Push configuration

Web Push is **fail-closed**. The member Notifications page may exist before delivery is configured, but it will not request browser permission until a valid public VAPID key is present. The admin sender stays disabled until the public key, VAPID subject and matching server-only private key are all available.

This first sender intentionally uses **payloadless Web Push**. The push service receives no prayer text, custom message body or other confidential KCMC content. The service worker displays a fixed generic KCMC update message and opens the public app.

### Generate and store the VAPID key safely

Generate a P-256 (`prime256v1`) keypair on the server or another trusted machine. Store the private PEM **outside** `/home/bobsome1/public_html/kcmc-connect/` and outside the Git repository. A suitable production path is similar to:

`/home/bobsome1/private/kcmc-push-vapid-private.pem`

The application rejects a private-key path inside the deployed KCMC application tree.

Derive the uncompressed public point from that same key and encode the 65-byte `04 || X || Y` value as URL-safe base64 without `=` padding. That encoded value is the VAPID public key used by the browser subscription flow.

### cPanel-friendly config.php path

Add the following keys to the existing server-only `config.php` array. Preserve the invitation-mail settings already in that file.

```php
'push_vapid_public_key' => 'YOUR_URLSAFE_BASE64_PUBLIC_KEY',
'push_vapid_subject' => 'mailto:secretary@umckc.org',
'push_vapid_private_key_file' => '/home/bobsome1/private/kcmc-push-vapid-private.pem',
```

Environment variables may be used instead and take precedence:

- `KCMC_PUSH_VAPID_PUBLIC_KEY`
- `KCMC_PUSH_VAPID_SUBJECT`
- `KCMC_PUSH_VAPID_PRIVATE_KEY_FILE`

The VAPID subject must be either a valid `mailto:` address or an HTTPS URL. Never place the private PEM itself in `config.php`, Git, browser markup, JavaScript or the public web root.

### Controlled Web Push verification

1. Sign in to KCMC Connect on a test device and open **Notifications**.
2. Press **Enable notifications**. Confirm the browser permission prompt appears only after that explicit click.
3. Confirm the page reports an active subscription for that account.
4. From a Pastor or Recovery administrator account, open **Push updates**.
5. Confirm the page reports delivery ready and at least one active subscription.
6. Check the confirmation box and send one generic update.
7. Confirm the device receives the generic KCMC notification and tapping it opens the public KCMC app.
8. Disable notifications on the device and confirm the stored subscription becomes inactive.
9. Repeat one send only if needed to verify a stale endpoint returns 404/410 and is automatically deactivated.

Do not claim production push support until this controlled real-device sequence succeeds.

## Prayer privacy checks

Before launch, verify all of the following:

1. A signed-out visitor sees only the public Prayer & Care gateway and cannot submit or view a request.
2. A member can submit a request. The default audience is pastors and the prayer team.
3. A member request marked for sharing remains pending until a pastor administrator approves it.
4. A Pastor administrator can approve, keep private or close a request.
5. A prayer-team account can view the confidential inbox but cannot approve publication.
6. A recovery-administrator account receives HTTP 403 on prayer-team, prayer-submission and prayer-approval routes and sees no prayer wall.
7. Private responses include `Cache-Control: no-store` and `X-Robots-Tag: noindex`.

## Deployment checks

1. Confirm the homepage, current bulletin and all navigation views.
2. Confirm worship times are 8:00 AM, 9:15 AM and 10:30 AM against the church's current public schedule.
3. Confirm office hours match the last approved Publishing Desk value. Missing hours fall back to Tuesday–Thursday, 9:00 AM–4:00 PM; later corrections or temporary closures must survive public reads and another deployment. Resolve conflicting source schedules before changing the saved value.
4. Confirm Chrome DevTools shows the `kcmc-connect-v3.0.2-public-only` service worker cache.
5. Publish a harmless bulletin-note change and verify it survives another deployment.
6. Confirm `config.php`, `data/private/` and `backups/` were not overwritten.
7. Confirm `/admin/setup.php` redirects to sign-in after the first account exists.
8. Confirm no file or URL under `assets/newsletter/` is present in the deployed app.

No shared administrator password or secret application backdoor is supported.
