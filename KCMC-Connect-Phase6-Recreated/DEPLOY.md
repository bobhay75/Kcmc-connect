# KCMC Connect 3.0 — cPanel Deployment

The standard repository deployment uses the root `.cpanel.yml` file to deploy this directory to `/home/bobsome1/public_html/kcmc-connect/`. For the existing host repair, use the scoped release procedure below and align the repository separately before considering cPanel **Deploy HEAD**.

## Preserved production data

Deployment intentionally preserves:

- `config.php` — optional server-only configuration
- `data/content.json` — live Publishing Desk content
- `data/private/` — member accounts, invitations, prayer requests, login throttles and audit records
- `backups/` — automatic public-content backups

Never copy `data/private/` into Git or a public download. Apache denies web access to both `data/` and `backups/`.

Newsletter page photographs are also prohibited. The standard repository deployment removes the retired August page images; only extracted text and separately approved ministry photos belong in the app. The scoped installer replaces only its allowlisted release files and does not perform that broader removal.

## Existing-host scoped release

The host successfully installed [`61c70f590735522adbfd6be02dab6888924a54fd`](https://github.com/bobhay75/Kcmc-connect/commit/61c70f590735522adbfd6be02dab6888924a54fd), confirmed by the owner receipt and fresh public service-worker, stylesheet, JavaScript and photo reads. Its cache namespace is `kcmc-connect-v3.0.3-public-only-tony-bright-photos-20261007`. Signed-in Publisher workflows and real-device install, offline and push acceptance still need their separate checks.

The October 8 repair is tracked in [PR #108](https://github.com/bobhay75/Kcmc-connect/pull/108) at runtime commit [`f4442fc4cce2121828544b79b8ba3591c5fe0dab`](https://github.com/bobhay75/Kcmc-connect/commit/f4442fc4cce2121828544b79b8ba3591c5fe0dab). Its host installation is still pending.

Follow the [scoped-release instructions](https://github.com/bobhay75/Kcmc-connect/blob/main/tools/kcmc-scoped-release/README.md) and use the separately supplied immutable, checksum-verified launcher. Repository alignment remains a separate step; the scoped installer does not establish that the host checkout is aligned.

1. Close Publisher tabs, allow pending saves/uploads to finish and keep Publisher idle until apply or rollback completes. Confirm web PHP and the host command use the same `KCMC_PRIVATE_DATA_DIR`, or the existing default `data/private` directory. A CLI check does not establish a different PHP-FPM environment.
2. Verify the release launcher against its published SHA-256 and immutable commit. Run the scoped installer preflight before apply. It accepts an exact complete allowlisted baseline, refuses unknown or mixed file versions, verifies staged source bytes and syntax, and checks preserved files.
3. Apply only the 16 allowlisted application files: six code files, the Publisher media endpoint and nine supplied images. The installer privately backs up affected files and `data/content.json` outside `public_html`, installs dependencies before their consumers and replaces the service worker last. It performs no Git operations or broad sync.
4. Save the printed backup/session directory and read the anonymous HTTP verification result. `config.php`, editorial content, accounts, prayer records and other private records are not replaced. Publisher publication/media JSON is fingerprinted under application-compatible locks without copying or restoring it; the two coordination lock files may be created.
5. Use the scoped rollback instructions for a failed code release. Rollback checks file versions and Publisher-store fingerprints, refuses later changes and restores only affected code/assets. It does not restore private/editorial records. Keep Publisher idle and confirm the same web storage selection before any later rollback.
6. Align the host repository separately, only after confirming its checkout is clean, to the reviewed runtime commit without copying live configuration or data into Git. The scoped installation does not advance that repository. Do not use **Deploy HEAD** while it still points to older code; `.cpanel.yml` performs a broad `rsync --delete` that could overwrite the scoped repair.
7. Complete the signed-in Publisher and one-device acceptance checks below. Public readbacks and CI do not establish those results.

Before the separately approved single Hope Keepers insertion, close Publishing Desk tabs, let pending editorial saves finish and keep Publishing Desk idle until the guarded insertion and verification complete. Preserve all other saved events and editorial fields.

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

Follow the remaining [real-device acceptance gate in issue 20](https://github.com/bobhay75/Kcmc-connect/issues/20) on one owner-controlled, authorized mobile device:

1. Sign in and open **Notifications**. Press **Enable notifications** and confirm the browser permission prompt follows that explicit click.
2. From a Pastor or Recovery administrator account on that device, open **Push updates**. Confirm delivery is ready and at least one subscription belongs to the signed-in account.
3. Background KCMC Connect and use **Test my device**. No broadcast is required.
4. Confirm at least one delivery is accepted, the generic notification appears while KCMC Connect is backgrounded, and tapping it opens KCMC Connect.
5. Turn notifications off from the member Notifications page. For an account with only this test device subscribed, confirm its signed-in-account subscription count returns to zero; preserve any other authorized device subscriptions.
6. Confirm no unexpected failed delivery remains. Stale 404/410 endpoints should be removed automatically.

Record the background receipt, tap navigation and unsubscribe/removal observations before closing issue 20 or claiming production push acceptance.

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
4. On one authorized mobile device, install/open the app, close and reopen it, and confirm the active service worker/cache matches the installed release. The confirmed `61c70` cache is `kcmc-connect-v3.0.3-public-only-tony-bright-photos-20261007`; use the October 8 release's pinned namespace after that release is installed. Check its public images and navigation online, then reopen the previously loaded public views offline. Private member/admin/API responses must remain network-only.
5. With an authorized staff account, check Publisher Save, reopen, Duplicate, page changes, photo upload/library selection and print on the installed release. Preserve authored paragraphs and check that a delayed save/upload does not change a different project or page. Record failures; do not treat anonymous route checks as this acceptance.
6. If an owner authorizes a bulletin-note pilot, publish the agreed harmless change and verify it survives the next approved deployment. This is a separate editorial action, not part of the installer's read-only checks.
7. Confirm `config.php`, live `data/content.json`, `data/private/` and `backups/` were preserved.
8. Confirm `/admin/setup.php` redirects to sign-in after the first account exists.
9. Confirm no file or URL under `assets/newsletter/` is present in the deployed app. Report any remaining prohibited assets separately; the scoped installer does not delete files outside its allowlist.
10. Complete the issue 20 one-device Web Push sequence above.

No shared administrator password or secret application backdoor is supported.
