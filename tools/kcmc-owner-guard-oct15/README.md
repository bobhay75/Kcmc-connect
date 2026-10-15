# Scoped owner account and notification UI repair

This offline Python 3.6+ package installs exactly the four source-reviewed A5/A7
files from the owner source follow-up merged as
`f0e9514ad73aae1d54be09a2b71b930c744ce581`. It accepts one complete canonical93
before tuple or its complete repaired tuple. Mixed or unknown tuples refuse.

The code prevents another administrator from disabling the configured designated
owner or issuing that owner's password reset, and shows Send update only to the
same designated owner accepted by the existing push destination. Existing roles,
account schema, ordinary staff workflows, owner self-password policy, prayer
privacy, and bearer reset-token handling are preserved.

Only these live files may be replaced, in this order:

1. `lib/password-lifecycle.php`
2. `admin/users.php`
3. `admin/password-resets.php`
4. `member/notifications.php`

## Required bootstrap, read only

`lib/bootstrap.php` must already be exactly 24,274 bytes with SHA256
`d4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263`.
That is the confirmed canonical93 bootstrap after the session repair, containing
the existing designated-owner helper. Bootstrap is never staged, backed up or
replaced by this package. The other three session files, all editorial/private
records, owner configuration, homepage, worker and repository also remain outside
the write inventory.

The wrapper pins bootstrap's complete identity and metadata lease using the
frozen no-follow reader and composes that lease into the existing lock checks.
Checks run before/after the frozen lock callback, through bundle and final rename
checks, after transaction and lock-context exits, and at final success boundaries,
including READY, no-op apply and rollback. Unknown bootstrap code can be diagnosed
by hashes only. Proving these bytes does not verify the owner's configured ID or
actual account identity; that remains a separate owner configuration check.

## Host use

Use the published, checksum-pinned installer as the hosting account, UID2162 /
GID2147. It accepts no root, PHP, source, owner-ID or data-path override. PHP8.2 CLI
is discovered by the existing cPanel/CloudLinux/PATH version-only procedure before
backup or staging; every staged file is hash-checked and linted without executing
application code.

```sh
python3 -I -B installer.py check
python3 -I -B installer.py apply
python3 -I -B installer.py check
```

For unknown/mixed code or prerequisite failures:

```sh
python3 -I -B installer.py diagnose
```

The diagnostic prints only the five fixed code hashes, sizes and metadata. It does
not print source, config, account or editorial records, and creates no backup.

A successful apply prints its exact private session. Roll back only that session
using the printed command:

```sh
python3 -I -B installer.py rollback --variant main93 --session repair-EXACT-PRINTED-SESSION
```

Backups and durable journals are fixed outside the web root at
`/home/bobsome1/kcmc-owner-guard-backups`, directories0700 and private files0600.
Live modes0644/0664 are retained. The complete frozen lock/lease/journal/recovery
engine is preserved, with only metadata, exact four-file inventory, non-serving
`.code` stage suffixes and pinned-stage PHP syntax lint changed.

If bootstrap changes during a transaction, the package stops and preserves the
external edit, durable journal, verified installed identities and uncertain
intent for manual review. Late drift after an applied or rolled-back journal
retains that complete journal phase and its leases; it is not relabelled or
silently discarded. Every refusal names the fixed `PRIVATE_BACKUP_ROOT`, including
when context-exit failure occurs before the engine returns an exact session.

There is no cross-file atomicity claim. Existing no-follow descriptors and final
metadata checks bound concurrent changes, but rename is not a kernel compare and
swap and an external writer can act after the final check. Do not reset, discard,
force apply, delete a journal or overwrite unknown code to bypass a refusal.

## Evidence and verification

Two immutable source fixtures enumerate the exact reversible owner deltas.
`runtime-reviewed.json`, canonical source evidence, the reviewed session fixture
and `prerequisite-reviewed.json` prove all four preimages/targets and the read-only
bootstrap prerequisite. `derive_installer.py` reproducibly embeds only those four
payloads in the standalone installer.

`test_installer.py` exercises all16 before/after combinations, real wrapper paths,
read-only diagnostics, metadata preservation, PHP selection, fourth-file lint
failure, prerequisite loss before replace, post-rename, during rollback, after
applied/rolled-back journals, during frozen lock exit, and after the engine return
boundary. It proves all frozen transaction functions/classes except the approved
lint are unchanged. The44 inherited tests retain the earlier rollback, concurrent
edit, symlink, metadata, journal and private-store protections.

`verify-stage.py --php /path/to/php82` runs real PHP8.2 selection and lint in
isolated temporary fixtures: full apply/no-op/rollback, post-rename prerequisite
loss, late applied-journal drift and guarded rollback drift. No live hosting,
application execution, email, push, private records or network are used by these
fixtures.

The focused GitHub workflow checks current Python, actual pinned Python3.6, exact
canonical source membership, reproducible generation, all package checksums and
real PHP8.2 transactions. Publication and host apply remain separate actions.
