# Verified core and team/payroll hosting installation

This code-only release supersedes the pending original PR145 installation block.
It combines a corrected installer for the same 21 core files with the 23-file
team/payroll bundle from approved source PR146 head
`131071542f7985eb5d483d8123764df9319a7e37`.

The original core installer had a reproduced recovery defect: another writer
could recreate a consumer after its restore/deletion was journaled, and rollback
could then remove that consumer's providers. Core v2 revalidates dependent
original/installed/absent leases through provider recovery boundaries. Its owner
group also retains the lifecycle authority helper when a password-reset consumer
is uncertain. All 21 app payloads, preimages, existing backups and journal formats
are preserved. Original source, tests and checksums remain immutable evidence.
Use the v2 installer for supported old core sessions; the original rollback
command is deprecated.

The fixed coordinator verifies **both** downloaded installer byte images before
executing either. The shell block must separately verify the coordinator's own
published checksum before running it:

```sh
python3 -I -B coordinator.py core-installer.py team-installer.py
```

Its decisions use typed complete-state checks, never loose output parsing:

1. If the whole final team/payroll bundle and all 15 unaffected core prerequisites
   are already verified, it holds those initial leases through repeated no-op
   checks. It also checks every core journal for unfinished repair, while skipping
   obsolete core live code tuples. No new backup or code replacement occurs.
2. Otherwise the core's exact complete known before/after profiles must pass.
   Every non-core team/payroll target must also be its exact before bytes or
   expected absence. Static composition proves the six core overlaps and 15
   read-only prerequisites match the core target tuple. Unknown/mixed next code
   refuses before any core backup or replacement.
3. The 17 projected non-core target leases remain guarded across core
   check/apply/check. Then team/payroll check/apply/check runs. Each installer
   preserves its own durable journal, private backup and recovery policy.

If core succeeds and the later team/payroll release refuses, the coordinator
prints `PRIOR_VERIFIED_RELEASES core21`. It does not downgrade the completed core
repair. A retry rechecks both whole bundles. There is no atomicity claim across
files, groups or releases. Concurrent writers can still act in the ordinary
last-check-to-syscall window or after a command returns; uncertain names and
providers remain for manual review.

Configuration, environmental owner settings, roles, private/editorial stores,
homepage, public presentation CSS, service worker and hosting checkout remain
outside the write inventories. The installers never execute application PHP,
register/run cron, send email/push, close/approve timecards or transfer money.
PHP calls are restricted to CLI version and staged syntax checks. Application
directories must already exist with safe ownership/modes.

Payroll reviewer/channel selection, matching web/CLI store diagnosis and any
schedule activation are separate owner actions. No Mike account, email recipient
or payroll provider is guessed. Installation alone does not enable delivery,
advances or direct deposit.

Each successful installer prints exact private sessions and scoped rollback
commands. After team/payroll is installed, roll it back first if recovery is
needed; only then can the corrected core installer validate its original
bootstrap prerequisite and core tuple. Never force a mixed tuple, remove a
journal or run an obsolete core rollback.

The combined CI checks both package checksum inventories, exact source Git
membership, reproducible derivation, Python3.6 compatibility, JavaScript syntax,
214 transaction/integrity tests and 23 real PHP8.2 fixture scenarios. It never
connects to the host or executes application routes. Public smoke tests,
authenticated acceptance and physical-device delivery remain separate evidence.
