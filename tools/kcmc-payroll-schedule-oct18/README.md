# Store-bound payroll schedule tool

This tool implements the managed-crontab transaction described in
`docs/payroll-automation-20261015.md`. It is a separate hosting tool, not an app
update, and has not been run against the live hosting account. It does not change
account roles, payroll settings, PHP configuration, time entries, mail records,
or the hosting repository. It never runs the payroll job or sends a notice.

The production app, PHP and backup paths are fixed:

- `/home/bobsome1/public_html/kcmc-connect`
- `/opt/alt/php82/usr/bin/php`, ordinary root-owned PHP8.2
- `/home/bobsome1/kcmc-payroll-schedule-backups`

The five code hashes in `schedule.py` pin the unchanged payroll runner and its
direct include chain from source commit
`4b108316a3865dba8583b30ec0dd8e2eeae6968e`. An unknown runtime refuses. App files
may be0644 or0664; installer state is0700 directories and0600 files. The tool
uses the current hosting UID2162/GID2147 only.

## Before activation

The owner must select the real active recipient and delivery channel in
Administration → Payroll setup. The tool selects nobody and never identifies
Mike from a display name. Its `--expect-recipient` argument must match the exact
opaque account ID selected there. The owner remains able to access time totals.

Use the private directory and web store fingerprint from authenticated owner
setup. Do not substitute a repository copy or a guessed private directory.
All status/plan operations execute only PHP `-n -v` and the pinned live runner's
`--diagnose`. Diagnosis reads metadata; it does not call application store readers
that create directories or chmod them. Python directly reads the existing
settings, accounts and runner receipt without changing their bytes or modes.

The status prints selected recipient ID, channel, matching-store status, managed
cron presence, minimal last-run time, and unfinished installer session names.
It prints no employee list, names, hours, correction reasons or email addresses.
The proposed managed command does include the private directory, which is needed
for the owner to review the live store binding. Unrelated cron commands are never
printed.

## Email readiness limitation

This version installs **queue-channel schedules only**. It supports read-only
inspection of an existing email selection but refuses email activation. The
preserved PHP config is hashed as opaque bytes and is never parsed or executed.
Setting an environment sender in the interactive shell does not prove that a
future cron process has a configured sender. Therefore status reports
`not_verified_preserved_config_not_executed`; no approval/attestation flag
bypasses that limitation. Actual current CLI sender readiness and authorized
test-notice receipt remain separate evidence needed for email scheduling.

The job itself remains the existing period-close runner. If the owner later
explicitly changes its channel in Payroll setup, that runner honors those saved
settings. This tool does not modify or freeze the app's settings behavior.

## Read-only review

After verifying this package's checksum from a pinned source commit, use the
following **template**, replacing the three labelled values from owner setup.
Do not paste the placeholder values unchanged.

```text
python3 -I -B schedule.py status --private-directory OWNER_WEB_PRIVATE_DIRECTORY --expect-store OWNER_WEB_STORE_FINGERPRINT
python3 -I -B schedule.py plan --private-directory OWNER_WEB_PRIVATE_DIRECTORY --expect-store OWNER_WEB_STORE_FINGERPRINT
```

`status`, `check` and `plan` are read-only. They create no backup, lock, journal,
record, cron task, mail or audit event. `can_apply` explains missing setup. A
plan's SHA256 binds the exact account/settings/config bytes, source hashes,
private-store identity, crontab existence and bytes, and proposed installed bytes.
Changing any of these requires a fresh plan. The last-run receipt is informative
and is intentionally excluded from the plan digest.

## Apply an exact reviewed queue plan

```text
python3 -I -B schedule.py apply --private-directory OWNER_WEB_PRIVATE_DIRECTORY --expect-store OWNER_WEB_STORE_FINGERPRINT --expect-recipient OWNER_SELECTED_ACCOUNT_ID --expect-plan EXACT_PLAN_SHA256
```

The only managed block is bounded by these exact comment lines:

```text
# BEGIN KCMC PAYROLL PERIOD CLOSE v1
# END KCMC PAYROLL PERIOD CLOSE v1
```

Its sole command is derived from the reviewed live PHP/app/private paths and
store fingerprint. It runs every15minutes with umask077 and a private log. It
preserves every byte before and after an existing block and every unrelated job.
Appending after an existing final line without a newline inserts a separating
newline without altering the original bytes. Duplicate, malformed, nested or
unknown-version KCMC payroll markers refuse. The shell arguments are POSIX
quoted; percent characters are separately escaped for crontab processing, just
as in the app's own command generator.
Backslashes and line breaks in the private directory refuse: a backslash before
a percent character could change cron's escape processing despite shell quotes.
An existing managed block must contain only its one scheduled command. The tool
does not add environment declarations that could affect later unrelated jobs.
An inherited cron `SHELL` outside `/bin/sh`, `/bin/bash` or `/bin/dash` refuses
instead of installing incompatible shell syntax.

The standard root-owned `crontab` executable is called directly, with `LC_ALL=C`.
Only status1 with empty stdout and the exact current user's `no crontab for …`
message means no existing crontab. Other read failures refuse; an empty existing
crontab is a different baseline from no crontab.

Apply takes a private nonblocking flock, checks for unfinished journals, rechecks
the plan, and durably saves original existence state/bytes/SHA256 plus proposed
bytes and a journal outside the web root. It rereads settings/store/crontab after
staging and again after the durable install-intent journal, then checks the real
crontab immediately before replacement. The standard install must succeed
without unexpected output, followed by byte-exact crontab readback. An identical
already-installed block is a no-op with no extra backup or crontab write.

The private lock does not lock unrelated cPanel editors. This is not a global
compare-and-swap guarantee. A preinstall conflict preserves the editor's jobs.
An error or uncertain readback preserves the journal and stops; it never tries
to overwrite a later editor with the old backup. Unfinished/uncertain journals
block subsequent apply until privately reviewed.

`INSTALLED_NOT_RUN` proves the expected block was read back. It does not prove
that cron later executed it, that a closed pay period exists, or that Mike saw
anything. Verify an actual later runner receipt with the same fingerprint and
the expected channel. A single receipt still does not prove a recurring schedule.
For email, transport acceptance and inbox receipt remain different evidence.

## Rollback without discarding later changes

```text
python3 -I -B schedule.py rollback --session EXACT_PRIVATE_SESSION_BASENAME
```

Only a verified `applied` journal can roll back. Private backup hashes/modes are
checked, and the current crontab must still exactly equal this session's
installed bytes. A later edit refuses without writing. Existing empty crontabs
are restored as empty; an originally absent crontab is removed with `crontab -r`.
Rollback also requires exact readback. An uncertain rollback keeps its journal;
there is no automatic second restore or journal-reset command.

## Validation

`test_schedule.py` uses an executable fake crontab and synthetic app/private
files. It exercises30 transaction and metadata scenarios, including absent vs
failed reads, exact outside-byte preservation, settings/account/config changes,
mail-readiness refusal, concurrent edits during staging and readback, incomplete
journals, mode/ownership/path checks, private lock contention, idempotence,
conditional rollback, uncertain rollback, and percent/shell quoting. It verifies
that no app record/config bytes or modes change and config is never executed.

`verify_php82.py` repeats the read-only diagnosis and queue apply/no-op/rollback
with actual PHP8.2 and executable fake cron. A separate synthetic-only assertion
compares the derived command byte-for-byte with the app's existing command
generator. Production `schedule.py` still runs only version and `--diagnose`.
Dedicated CI runs the fake transactions on current Python and actual Python3.6,
and actual PHP8.2 in a pinned-base, network-disabled test container.
