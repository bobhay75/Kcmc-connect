# KCMC remaining code repairs

The standalone installer contains the exact reviewed three-PHP repair engine and
the exact single-script skip-link repair engine. Both embedded SHA-256 hashes are
verified before loading their definitions. Runtime installation needs no source
dependencies, downloads, app bootstrap or JavaScript execution.

The fixed host is `/home/bobsome1/public_html/kcmc-connect`, UID 2162/GID 2147.
Scope is exactly `lib/timeclock.php`, `member/activate.php`,
`member/reset-password.php` and `app.js`. Content, accounts, roles, owner settings,
Publisher records and repository files are excluded. The approved bulletin,
events and office hours were observed live on October 14 and require no change.

Default `check` is read-only. Both scopes and their existing journals must pass
before `apply` starts. PHP repairs apply first; the JavaScript repair applies
second. Each group has its own private backup and atomic file replacements.
These groups are independent: a later failure preserves an earlier successful
repair, and the output reports each group's outcome. Repaired groups are no-ops.
Unknown bytes, unsafe links/ownership/modes and unfinished journals refuse.

Keep other code deployments and edits idle while the command runs. Held file
descriptors and full leases preserve detected concurrent changes; `os.replace`
does not provide a kernel compare-and-swap against an uncooperative writer in
the final syscall gap. Unknown or interrupted renames retain manual-review
journals. Do not delete a journal to bypass this refusal.

PHP syntax is checked using the fixed cPanel PHP 8.2 binary with `-n -v` and
`-n -l` against staged code only. JavaScript staging verifies the reviewed bytes;
its syntax and keyboard behavior are checked before release using Node and
Chromium. The host does not claim a JavaScript syntax test when Node is absent.

Private roots are `/home/bobsome1/kcmc-minimal-repair-backups` and
`/home/bobsome1/kcmc-skip-repair-backups`; directories are 0700 and backups and
journals are 0600. Existing code modes 0644/0664 are preserved. Fully verified
applied sessions print a rollback command. Download this same pinned installer
again as `installer.py` before using that command; the launch block removes its
temporary script after execution. Rollback requires one explicit group and its
exact private session basename. Uncertain sessions require review.

`generate_runner.py` reproduces the standalone file from the exact sibling
engines. `test_composition.py` checks default-read-only behavior, all old/repaired
combinations, actual reviewed source reconstruction, independent rollback,
unknown/mixed inputs, failures and diagnostics with private/content sentinels.
The skip engine has 49 additional transaction/provenance cases. The real-stage
fixture uses actual PHP 8.2 on new temporary copies and performs no app execution.

The user's sole-owner/master-administrator direction remains in effect. Code
installation and printed hashes must be verified from the owner terminal output;
source/CI success does not establish a production installation or device result.
