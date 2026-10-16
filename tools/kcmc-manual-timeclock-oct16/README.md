# Manual time clock without approvals

This package derives the exact five-file delta from themed baseline
`b0321c38d9750314c7d56896d3a818b6d7680228` to source commit
`05cb55e87f3157c9f0cdf0051da19bd5361e7c99`. Source and hosting-package CI must
pass before publication for installation. A successful hosting receipt remains
separate from source review and local temporary-copy tests.

The fixed host is `/home/bobsome1/public_html/kcmc-connect` as UID2162/GID2147.
Only these five existing code files may be replaced:

- `lib/timeclock.php`
- `member/timeclock.php`
- `admin/timecards.php`
- `admin/timecards-export.php`
- `admin/timecards-print.php`

The complete final theme and functional code inventory outside those paths is
read-only. The finite public `main` and `livecalendar` tuples remain distinct.
Private/editorial records, configuration, the hosting repository, punches,
schedule, messages, email, payroll delivery and account roles are untouched.
Only PHP8.2 CLI version and staged syntax checks may execute.

The standalone installer accepts a complete themed five-file preimage or its
complete final image. It uses the unchanged reviewed transaction engine and
corrected extension, with no new files. The existing timeclock library installs
before its four consumers and remains installed if any consumer becomes
uncertain during recovery. Every replacement is
guarded by source hashes, inode/metadata leases, safe existing parent descriptors,
private backups and durable journal intents. Rollback restores only verified
owned replacements. Unknown/mixed code and unfinished journals stop safely.

The coordinator also supports the complete pre-theme image by first running the
previous pinned theme installer. Its first step classifies the whole five-file
tuple. A final manual image verifies all final guards and old theme journals,
then skips the obsolete theme installer. A before image must match the old
theme's complete before/after state; unknown state never falls through to an
older installer. The two paths outside the old theme write inventory remain
leased read-only throughout that phase. A completed theme installation stays
installed if the later manual repair refuses; there is no automatic downgrade.

After the manual repair, use this coordinator instead of re-running the old
theme helper. Existing live private records are not migrated or rewritten.

The one-block cPanel command downloads two exact installers and this
coordinator, verifies every checksum before compiling either installer, then
checks/applies/checks each needed code release. Successful hosting output is
required before claiming the repair is installed.

`test_installer.py` covers both exact public variants, all three supported entry
states, every target and read-only guard, mixed/unknown code, existing-file
transactions, safe rollback, no-op inode leases, staged tampering, ambiguous
interruptions, and both old journal roots before any helper is entered. Its Git
proof verifies the complete five-file runtime delta and existing modes against
the exact two source objects. `verify-stage.py` runs real PHP8.2 staged syntax,
transactions and pre-theme through manual installation in temporary roots.
The previous foundation's 44 and policy extension's 28 tests run unchanged.
