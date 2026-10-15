# Scoped owner and workflow hosting repair v2

This revision replaces the original core installer without changing any of its
21 application payloads, complete preimages, read-only bootstrap prerequisite,
backup roots or release identifiers. It checks complete no-op identities through
the result boundary and checks recorded applied/rolled-back journal leases after
the transaction context exits. During rollback it revalidates completed consumer
restores/deletions before removing each provider and within the final lock
callback; a recreated consumer retains its potentially required providers and
requires manual review. These checks do not make external concurrent writers
atomic with the installer.

This offline Python 3.6+ package installs two disjoint, exact-source code groups.
The first completes the three owner account protections from source PR141. The
second installs the 18 workflow files from PR144 head
`ba7b5df314e1be604d46443025d41b1c8fe732a4`, against canonical baseline
`00fdd469482564a3511a29a27a99502c24a32845`. Both groups are checked before either
can create a backup or modify application code. Unknown or mixed code refuses.

The source changes provide employee punches and administrator period preparation,
review including the designated owner's own timecard, a personal member
dashboard, separate authenticated prayer routes and clearer push subscription
diagnostics. They also prevent another administrator disabling or issuing a new
password reset for the configured designated owner. They preserve existing
roles, account schemas, staff workflows, prayer privacy and bearer reset-token
handling. This installer does not reinterpret or revoke existing reset tokens.

## Exact write scope and complete profiles

The owner group contains only these existing files, in order:

1. `lib/password-lifecycle.php`
2. `admin/users.php`
3. `admin/password-resets.php`

It accepts its complete reviewed before tuple or complete repaired tuple. An
already repaired owner group is skipped without creating an owner backup.

The workflow group installs these files in this order. An asterisk denotes a
file that must be absent in a recognized before profile:

1. `lib/timeclock.php`
2. `lib/push-subscriptions.php`
3. `member/push-settings.js`
4. `admin/prayer-care.php` *
5. `admin/prayer-inbox.php` *
6. `member/prayers.php` *
7. `admin/timeclock-period-close.php` *
8. `admin/home.php` *
9. `admin/prayers.php`
10. `member/prayer-care.php`
11. `member/prayer-team.php`
12. `member/submit-prayer.php`
13. `member/timeclock.php`
14. `admin/timecards.php`
15. `admin/push.php`
16. `member/notifications.php`
17. `admin/index.php`
18. `member/index.php`

Two complete workflow preimages are recognized: `pre_a7`, before the narrow owner
notification-link repair, and `owner_a7`, after that repair. Only the reviewed
`member/notifications.php` preimage differs. These are whole bundle profiles;
files cannot independently choose their preimages. Both converge on the same
18-file after tuple, which is explicitly recognized as one common no-op state.
The owner group's state is independent of the workflow profile.

No live file outside these 21 targets is written. In particular, the fish home
page, worker, other session files, repository checkout, owner configuration,
content, accounts, prayer records and timeclock records remain outside the write
inventory. Application directories must already exist with owned, safe parents;
the installer creates no application directory or blanket permission change.

## Required bootstrap, read only

`lib/bootstrap.php` must be exactly 24,274 bytes with SHA256
`d4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263`.
These are the confirmed post-session canonical93 bytes containing the existing
designated-owner helper. Bootstrap is never staged, backed up or replaced here.
Its complete no-follow identity and metadata lease is checked throughout both
transactions, rollback, lock-context exits and final success boundaries. A later
fresh invocation can capture a new identity only when its bytes and metadata
remain approved; an active transaction cannot silently adopt an identity change.
This code prerequisite does not prove the configured owner ID or actual account
identity. Owner configuration remains a separate operational check.

## Host use and recovery

Run the published, checksum-pinned standalone `installer.py` as the hosting
account, UID2162 / GID2147. It accepts no app root, PHP executable, owner ID,
source, data path or environment override. PHP8.2 CLI discovery uses the reviewed
cPanel/CloudLinux/PATH version-only procedure before backup. Every staged PHP
target is linted with `-n -l`; the one JavaScript target remains
source-pinned and is syntax-checked in CI. No application route or command is
executed during installation.

```sh
python3 -I -B installer.py check
python3 -I -B installer.py apply
python3 -I -B installer.py check
```

For unrecognized code or metadata, use the read-only diagnostic:

```sh
python3 -I -B installer.py diagnose
```

It prints only the 21 fixed target hashes, sizes and metadata, plus the one
bootstrap prerequisite. Expected-absent targets print parent metadata. It reads
no private/configuration/editorial records and creates no backup. Do not bypass
a refusal by forcing files, deleting a journal, resetting the checkout or running
an obsolete four-file owner installer after these workflow files are installed.

Apply completes or skips the owner group first, then the workflow group. Each has
its own lock, private journal and recovery session. A later workflow failure does
not automatically downgrade earlier verified owner protection; the refusal names
that earlier success. Apply is not atomic across the two groups. After resolving
the reported issue, a retry rechecks both complete groups and safely skips the
already verified owner group.

A successful group apply prints its exact private session and rollback command.
Use only that printed group/session/profile, for example:

```sh
python3 -I -B installer.py rollback --group workflows --variant pre_a7 --session repair-EXACT-PRINTED-SESSION
python3 -I -B installer.py rollback --group owner --session repair-EXACT-PRINTED-SESSION
```

Private roots outside the web root are fixed at:

- `/home/bobsome1/kcmc-workflows-owner-backups`
- `/home/bobsome1/kcmc-workflows-pre_a7-backups`
- `/home/bobsome1/kcmc-workflows-owner_a7-backups`

Private directories use 0700 and private files 0600. Existing target modes 0644
or 0664 are retained; new code uses 0644. All refusals name these fixed roots,
including failures before a transaction returns its exact session. Durable
journals, installed leases and uncertain intent remain available for manual
review. A late prerequisite change after an applied or rolled-back journal
prevents a success marker without relabelling or discarding that journal.

## Finite absence and dependency extension

The frozen reviewed existing-file engine is preserved byte for byte in
`frozen-minimal-installer.py`, SHA256
`4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7`.
The owner derivation changes fixed metadata/inventory, non-serving `.code`
stage suffixes and exact-stage PHP lint. Its explicit existing-only
`owner-dependency-extension.py` adds `provider_needed` and overrides
`restore_owned` to retain the lifecycle provider if a completed password-reset
consumer reappears; its journal schema and existing-file mover are preserved. The workflow derivation explicitly
overrides ten functions: `inventory`, `verify_lease`, `inspect`, `repair`, `load`,
`lint`, `bundle_lease`, `move_code`, `restore_owned` and `apply`. Existing
replacements still call the unchanged frozen mover. This is an explicit policy
extension for five absent files, rather than an exception hidden in metadata.

An absent target has a pinned parent lease and a durable intent before exposure.
Publication uses same-filesystem `os.link` with directory descriptors and
`follow_symlinks=False`, so a raced-in target causes atomic EEXIST refusal.
The linked source/target identities and bytes are verified at link count two;
only the private stage name is then unlinked. A complete installed lease is
captured after the target returns to link count one, including the changed ctime.
Primitive support and complete before profiles are checked before backup.

A partial link/unlink, changed namespace or interrupted lease capture is
uncertain. Candidate bytes or an intent alone never authorize automatic deletion
of a new target. Rollback removes a new file only from its verified installed
lease, after held-descriptor and final pathname checks. Recovery preserves
uncertain names, stages and journals rather than guessing ownership.

Providers are installed before their consumers using the explicit dependency
map in `source-runtime-reviewed.json`; recovery reverses that order. The new
authenticated prayer entry routes precede changed consumers. In particular,
the care stub can safely call the older authenticated controller during the
transition; the updated controller redirects review access only once the stub is
present. New timeclock and push providers precede their consumers. If any
consumer's installed bytes or removal/restoration are uncertain or conflict with
another writer, recovery conservatively retains potentially required providers.

There is no cross-file atomicity claim. Atomic no-clobber publication prevents a
new target overwriting a raced-in name. Existing replacement and leased rollback
deletion still have the ordinary final-check-to-syscall window; they are not
kernel compare-and-swap operations. External writers can also act after the
installer returns. Stop on a conflict and review its preserved journal.

## Scheduling and external acceptance

The new `admin/timeclock-period-close.php` route is installed and syntax-checked
only. Apply never registers or runs cron, sends email/push, closes a period,
approves a card, executes app code or reads/writes private records. Safe scheduler
setup requires a separate read-only diagnosis of the actual configured store and
runtime configuration. Browser/device acceptance and owner configuration remain
separate from this code installation.

## Evidence and checks

`runtime-reviewed.json`, `owner-runtime-reviewed.json` and the source evidence
enumerate every byte of both complete before profiles and their targets. The
immutable A5/A7 reversible source fixtures prove the older owner preimages.
`derive_installer.py` validates exact pins and reproducibly produces the one
standalone installer and `provenance.json`. Optional Git membership proof checks
all canonical before files, exact absence of the five new paths, all 18 targets
at the pinned PR144 head, and unchanged owner/bootstrap source membership.

The 18 composition tests cover both profiles, common-after convergence, mixed
and unknown refusal, both-group preflight, independent owner skip/retry,
hashes-only diagnosis, no-clobber conflicts and prerequisite boundaries. The 28
finite policy tests cover absent-file races, link/unlink uncertainty, lease-only
rollback, provider retention, parents, metadata and finite frozen overrides. The
44 inherited tests retain the original existing-file rollback, symlink,
concurrent-edit, private-store and journal assertions.

`verify-stage.py --php /path/to/php82` runs six real PHP8.2 transaction scenarios
in isolated temporary fixtures: both profiles through both groups/no-op/exact
rollback; uncertain hardlinks; uncertain consumers; late applied-journal
prerequisite drift; and guarded rollback drift. It permits only PHP version and
lint subprocesses. The focused workflow runs current Python, actual pinned
Python3.6, real pinned PHP8.2, JavaScript syntax, canonical Git membership,
generation reproducibility and package checksums. Host apply remains a separate
action after those required checks pass.

## Revision evidence and compatibility

`provenance/original-package` preserves the originally published installer,
derivation, wrapper, extension, tests, stage verifier, README, provenance and
checksum manifest unchanged. Shared payload evidence and reviewed fixtures are
kept once in this package; derivation validates every original checksum against
either its preserved original file or that shared unchanged evidence. The
original checksum manifest is pinned to
`0d74e36e21b117ebbd4bdd73bc60778036b6d416d0cc372c7a129803d6448ee3`.

Only `provider_needed` and `restore_owned` change in the finite extension; an AST
regression verifies all other extension functions remain identical. The frozen
existing-file mover is unchanged. The separate existing-only owner recovery
extension adds the literal password-reset route to lifecycle helper dependency
without changing the owner journal schema. The wrapper adds initial
no-op, journal-result and final two-group lease verification. Original tests
remain unchanged in preserved provenance. The current root provenance test
explicitly verifies the two-function owner recovery extension; all existing
transaction assertions are retained. `test_v2_safety.py` adds faults for this
revision.

A complete repaired host can use this revision as a read-only no-op. A known
complete applied session created by the original installer can be rolled back
with this revision using the same printed group, variant and exact session name.
An explicit regression creates old-format applied sessions with the preserved
original installer and rolls them back with v2. Incomplete or conflicting
sessions still require manual review and are never reset or discarded.

Local validation covers the original 90 transaction/provenance tests, 12 new
safety tests (including six consumer recreation placements and old-session
compatibility), and 11 real PHP8.2 temporary transaction/fault scenarios. Actual
Python3.6 and repository membership checks are CI responsibilities. No command
in these tests touches the hosting account, sends mail/push, schedules payroll,
executes application routes or reads private production records.
