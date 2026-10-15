# Store-bound payroll totals and explicit reviewer setup

This increment extends the tested employee clock repair. It does not guess Mike Cahill’s account, alter account roles, store banking details, make payments, or submit payroll to a provider.

## Owner setup and access

`admin/payroll-setup.php` is restricted by the existing designated-owner guard. Its private settings default to **off**, with no recipient. The owner selects an existing active account and chooses private queue or email. An account’s display name, ordinary administrator role, or publisher status never selects it automatically. New email delivery or a changed reviewer records the owner-save America/Chicago date as the email activation cutoff. Unchanged active email settings preserve that cutoff; off/on starts a new one. Disabling the channel or deactivating the selected account immediately removes delegated payroll access; the existing owner retains access.

`kcmc_can_review_payroll()` grants only payroll review. Time-card review, approved CSV, and print routes use this capability. The account gains no publisher, private-prayer, account-management, Operations, or owner privileges. The selected ordinary reviewer still cannot approve or resolve their own time card. The owner’s previously approved self-review override stays intact.

Private `payroll-settings.json` is created only when the owner saves setup. Existing time-clock entries, pay-period defaults, account roles, and preserved server config are not migrated or replaced. Setup uses CSRF, a fresh active owner lookup, and exact active recipient IDs. The web screen never sends a payroll email or activates a schedule.

Navigation integration points, owned separately by the compact-workspace increment:

- Include `lib/payroll.php` and use `kcmc_can_review_payroll($user)` to show the Payroll review link to the explicit recipient.
- Route that link to `admin/timecards.php`.
- Show `admin/payroll-setup.php` only to the existing designated owner.
- A selected plain member needs a payroll link without access to unrelated administrator tools.

## Store binding and CLI

`admin/timeclock-period-close.php --diagnose` performs no private-record read, folder creation, queue mutation, mail call, audit write, or schedule operation. It returns the resolved store path and a metadata fingerprint. The fingerprint includes the resolved `timeclock.json` path plus its ordinary private directory’s device, inode, owner, group, and mode. It excludes the changing time-clock file inode/content/timestamps and directory timestamps. Normal atomic Clock In/Out writes therefore preserve it.

The diagnostic refuses symlink path components, unsafe directory permissions/ownership, hardlinks, and unsafe time-clock-file metadata. A scheduled run requires:

```text
php -n /path/to/live/admin/timeclock-period-close.php --run --expect-store <64-character web fingerprint>
```

A missing/mismatched expectation is refused before queue, settings, account, audit, or receipt writes. Existing bootstrap sets private storage to mode0750 on store reads. Authenticated web setup therefore captures0750; scheduled execution refuses any other captured mode before mutation, rather than changing its own binding mid-run. `--diagnose` itself remains read-only even when it reports another safe mode.

Owner setup prepares a shell-quoted cron line tied to its actual live script and web-resolved `KCMC_PRIVATE_DATA_DIR`. It supplies that environment override explicitly, escaping crontab percent syntax separately from POSIX shell quoting. It runs every15minutes, so the app’s existing Chicago date logic handles daylight-saving changes. Preparing the command installs nothing.

The runner closes due periods, then prepares the configured handoff. Queue mode exposes the private cards to the selected recipient. The admin screen remains the missed-run fallback. `payroll-run-status.json` records the runner’s time, matching fingerprint, channel, and numeric counts; it contains no employee names, hours, addresses, or correction text. A runner receipt is not proof that cPanel has installed a recurring schedule.

## Explicit email channel

Email also requires a server-configured payroll sender (`KCMC_PAYROLL_FROM`, optional `KCMC_PAYROLL_FROM_NAME`, or the matching blank `config.example.php` fields in preserved server config). Invitation-mail configuration alone does not enable payroll email. The owner must select email delivery, an active account with a valid email address, and an HTTPS private review address.

Only periods ending on or after the explicit email activation cutoff are eligible for automatic notices. Earlier history stays in the private review queue and is not emailed as a backlog. Legacy email settings with a missing or invalid cutoff refuse sending until the owner re-saves setup. The owner sees this behavior before saving.

Notices contain each employee’s summed completed hours and completed/open shift counts for a closed period, plus a private review link. They omit work descriptions, correction reasons, and banking information. Open shifts remain warnings; no clock-out time is invented.

A revision digest covers the actual locked totals and counts. A private outbox claim is committed before calling transport, preventing two concurrent runners from sending the same claimed revision. Claims use the existing time-clock-store lock, and the actual locked totals are compared again before claiming. Recipient/channel settings are checked again before transport. Corrected totals produce a new revision; approval-status changes alone do not create duplicate notices.

A transport acceptance is recorded as **accepted by mail transport**, separately from actual inbox delivery. Failed calls and interrupted `sending` claims remain preserved for owner review and are never blindly resent. This does not claim exactly-once external delivery. No automatic expiry steals a claim from an uncertain send. Retrying a failed or interrupted revision requires a separately reviewed owner action; this source increment does not add a resend button that could duplicate mail.

## Hosting cron installer plan

Do not activate a job until the owner has selected the real recipient/channel, reviewed the exact web-generated fingerprint/command, and verified that CLI `--diagnose` matches. For email, first verify the configured sender and actual test-notice receipt with explicit authorization. No such activation or real send was performed while creating this increment.

A scoped hosting installer should:

1. Pin the reviewed helper and live runner hashes; verify the ordinary owner-controlled live app, PHP8.2 CLI, resolved private directory, and expected web fingerprint. Use the live app, never a repository copy.
2. Read the existing crontab with a known locale. Distinguish an absent crontab from an unexpected read failure. Save its exact original bytes, existence state, and SHA256 outside the web root under an owned0700 backup directory; backup/journal files use0600.
3. Recognize exactly one managed block bounded by `# BEGIN KCMC PAYROLL PERIOD CLOSE v1` and the matching END marker. Refuse duplicate/malformed blocks. Preserve every byte outside that block and every unrelated job. An identical managed block is a no-op.
4. Stage the proposed crontab privately and show its fingerprint plus the exact managed command. Do not splice arbitrary text from POST input; derive the line from the reviewed live settings/store binding and selected known PHP path.
5. Under an installer-specific private lock, re-read the current crontab immediately before installation and require the saved baseline hash/existence state. Refuse concurrent edits. Install through the standard `crontab` command, then require exact readback. A private helper lock cannot lock out unrelated cPanel editors, so readback and a conflict-preserving journal are essential; do not claim a global compare-and-swap guarantee.
6. Retain the original backup and recorded installed hash. If installation/readback is uncertain, stop for review rather than overwriting a later editor’s jobs. Rollback may restore the original bytes only while the current crontab still exactly matches this helper’s verified installed version.
7. Verify the actual installed managed block and a subsequent runner receipt using the same store fingerprint. Only then report scheduled period-end handoff enabled. Confirm actual recipient inbox delivery separately from transport acceptance.

This plan preserves existing jobs and makes retries idempotent. A later host package may implement and test it with a fake crontab executable before any authorized hosting activation.

## Validation

- `tests/payroll-automation-contract.php`:43 real PHP assertions for off defaults, exact recipient selection, owner-only setup, unchanged roles/prayer/publishing rights, deactivation/revocation, stable fingerprint across real punches, metadata refusal, shell quoting, email configuration, totals/privacy, correction revisions, idempotence, malformed-history preservation, failed transport, uncertain claims, activation boundaries, same-reviewer preservation, reviewer switches, off/on reset, and invalid legacy activation refusal. Every transport is injected; no real mail is called.
- `tests/payroll-route-contract.py`:11 actual protected-route/CLI scenarios, including delegated member review/export, blocked self-review/setup/publishing, disable revocation, read-only diagnosis, missing/wrong fingerprint, wrong private-store environment, symlink/hardlink/permission refusal, two concurrent PHP workers using fake transport that record only one claim/send, a persistent PHP process refusing an externally replaced store directory, ordinary-recipient navigation and Back links, and selected-pastor discovery in its existing hub with owner-only setup preserved.
- The existing7 time-clock protected-route scenarios now invoke the CLI with its required store expectation and assert the explicit payroll-access denial. Existing employee clock service assertions remain unchanged.
- Current static review-boundary assertions in the MVP/correction contracts name `kcmc_require_payroll_reviewer()`; the immutable phase1 source-proof layer retains the prior literal administrator-role contracts for their original version.

For isolated local validation, only the two root-owned navigation files were copied for inspection; their team-workspace dependency remains owned by the separate composition. `KCMC_NAV_TEST_APP` can point the two navigation scenarios at the complete composed app. All other payroll routes and store/transport tests use the candidate payroll runtime. Canonical composed CI needs no override.
