# Scoped team workspace and payroll code repair

This Python3.6+ offline package installs one complete 23-file code bundle from
the separately reviewed team/payroll source. It requires the entire earlier
21-file owner/workflow repair to be present. It never reads or writes application
configuration, private records, editorial content, the homepage, its stylesheet,
the worker, the hosting repository or the hosting schedule.

The source adds assigned work and contextual conversations, saved workspace
views, publication draft conflict protection, compact navigation and an explicit
owner-selected payroll reviewer. Payroll starts off until the owner chooses its
reviewer and channel. Code installation neither selects a person nor enables a
channel. The runner is installed and syntax-checked, never run or scheduled here.

## Source status

The code payloads pin reviewed source PR146 head
`131071542f7985eb5d483d8123764df9319a7e37` against exact baseline
`3317aed0c4b6a1619f8f68cced6a73fc4a245055`. `derive_installer.py` verifies
all reviewed input pins and reproduces the standalone installer. Earlier labelled
candidate artifacts are excluded from publication. Source approval, final package
CI and actual hosting execution remain distinct checkpoints.

## Write inventory and prerequisites

`source-runtime-reviewed.json` gives the exact provider-first order and dependency
graph for all 23 live targets: 14 existing replacements and nine absent paths.
`runtime-reviewed.json` carries their entire exact before and after bytes.
`config.example.php` documents optional sender configuration in source but is
excluded from hosting writes; actual `config.php` and environment are preserved.

Six earlier core targets also change in this bundle. Their exact before images
must equal the earlier complete repaired tuple. The remaining 15 core files are
fixed read-only prerequisites, including all three designated-owner protections.
Both their hashes and byte counts must match, and full inode/metadata leases are
captured before any backup and retained through staging, apply, recovery, lock
context exits and final reporting. A same-byte replacement during an active
invocation is a conflict. A later invocation may capture an ordinary new inode
only when the full approved bytes and safe metadata still match.

Bootstrap changes in this release, so it is **not** an exempt or dynamically
adopted read-only prerequisite. Its preimage must be the exact confirmed session
repair (`d4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263`). It is
the first normal code target, with original, candidate and installed leases in
the same durable journal as every other target. Its new helpers precede callers.
The changed publication backend precedes the changed designer so an old open
editor can receive a safe conflict while the code bundle is being installed.

Only a complete before tuple or complete after tuple is recognized. Unknown,
unrepaired or mixed code refuses before creating a backup. Application parents
`lib`, `admin`, `member` and `api` must already be ordinary owned safe directories.
No application directory is created and no directory mode is changed.

## Standalone host use

Use only the final published checksum-pinned installer as UID2162/GID2147:

```sh
python3 -I -B installer.py diagnose
python3 -I -B installer.py check
python3 -I -B installer.py apply
python3 -I -B installer.py check
```

The diagnostic prints only hashes, sizes and metadata for the 23 targets and 15
fixed code prerequisites. It reads no configuration or private data and creates
no backup. PHP8.2 CLI selection performs version-only probes before backup. Every
staged PHP file is hashed and syntax-checked with `-n -l`; staged JS and CSS are
source-pinned. No PHP application code is executed by this package.

Successful apply prints the exact private session and rollback command:

```sh
python3 -I -B installer.py rollback --session repair-EXACT-PRINTED-SESSION
```

The fixed private root is `/home/bobsome1/kcmc-team-payroll-backups`, outside the
web root. Backup directories are 0700, private files 0600. Existing code 0644/0664
modes are retained; newly published code is 0644. A conflict preserves its journal,
recorded installed leases, stages and uncertain names for review. Never delete a
journal or force a mixed bundle into place to bypass a refusal.

## Recovery and limits

The existing-file foundation is byte-identical to the reviewed frozen engine
SHA256 `4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7`.
The PR145 finite extension is preserved byte for byte as
`frozen-workflows-extension.py`, SHA256
`78eb5ffa7cb36ce34dfa6cdf8af80bc11c304f0b7b25bcf75536f893952d0648`.
The new extension SHA256
`a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2`
changes only `provider_needed` and `restore_owned`; AST comparison proves every
other statement/function unchanged. It still overrides the same ten functions
of the frozen engine. Existing replacements retain the unchanged frozen mover;
nine new paths use atomic no-clobber hardlink publication.

Every absent target has an owned parent lease and durable intent before exposure.
The linked stage and target are verified at link count two before the private
stage name is removed. An installed lease is captured at link count one. A raced
name cannot be overwritten. A partial link/unlink or interrupted lease capture is
uncertain: candidate bytes and intent alone never authorize deleting that name.

Recovery restores consumers before providers. Before a provider is changed,
every dependent consumer retains its expected installed or original/absent lease,
including future targets not installed yet and consumers already restored/deleted.
Those checks repeat through the provider final move/unlink callbacks. A concurrent
consumer recreation after a completed restore/deletion marks manual review and
retains its providers. If a consumer cannot be safely removed/restored, changed bootstrap and any potentially required providers remain
installed. A complete explicitly applied session can roll back only while all
installed leases and read-only core prerequisites remain valid. Final success
also verifies the durable result journal against current installed/restored
leases; a late same-byte inode replacement cannot be reported as success. A no-op retains
its initial target leases through engine return and final reporting; it cannot
adopt a newly replaced inode merely because fresh inspection finds approved bytes.

This is not a multi-file atomic deployment. Readers can see an intermediate
compatible bundle or receive a temporary safe failure. Existing-file replacement
and verified rollback deletion retain the ordinary final-check-to-syscall window;
they are not kernel compare-and-swap operations. Other writers can act after the
installer returns. Stop and review the preserved journal on any conflict.

No cron, email, push, approval, timecard close, payment, account-role or private
record operation occurs here. Payroll schedule setup requires separate matching
web/CLI store diagnosis, explicit owner configuration and a preserving schedule
installation. Browser/device acceptance remains separate from code installation.

## Verification

The 27 coordinator/provenance tests cover exact complete source tuples, all single-target
mixed states, every read-only prerequisite, writable bootstrap, same-byte inode
drift at final reporting, no-clobber API publication and uncertain provider
retention. The existing 44 foundation assertions and 28 inherited policy cases
remain. `verify-stage.py` runs nine real PHP8.2 syntax/transaction scenarios in
temporary fixtures, permitting only PHP version and syntax subprocesses. Tests
also preserve synthetic configuration, private/editorial stores, homepage,
worker, repository and unrelated crontab bytes and identities.

Final CI must prove exact Git membership at the pinned before/after commits,
reproducible derivation, package checksums, actual Python3.6 and real PHP8.2.
