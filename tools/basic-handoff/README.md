# Basic church handoff — review candidate

Status: incomplete; do not merge or deploy. The package is generated into a new local directory and is not an installer.

## Included

Public church information, worship links, visitor and connection forms, events, announcements, bulletin, call-for-prayer contact, and sign-in for existing pastor or recovery administrators. The basic content editor manages contact details, announcements, bulletin, events and post visibility. Admins can review connection and event responses. The existing implementation retains automatic content backups when edits are saved.

## Excluded from the candidate

Member account features and prayer wall, staff time clock and payroll, publication designer (Publisher), team workspace, push subscription and broadcasts, and the associated direct application entry points. Sign-in and sign-out files happen to live under `member/` in the original app; only these two files are retained for administrator authentication. The original source remains in Git history and private stores are not included or erased. No assertion is made that any component is independently owned or licensable.

## Build for review

From the repository root, run `python3 tools/basic-handoff/build.py /path/to/new-directory`. The destination must not already exist. The build rejects source symlinks, omits private stores, backups and configuration, and removes excluded endpoints and libraries. The included content JSON is a repository fixture and may be stale. Never replace current host data with this copy.

## Outstanding release work

1. Confirm PHP syntax and the HTTP acceptance workflow on the exact candidate commit. Exercise login and logout, administrator role denial, content edits, event creation, conflict handling, connections and RSVPs, and backup recovery using synthetic data. Check phone layouts and public navigation.
2. Inventory actual live files, active users, configured writable directories, server rules and scheduled jobs. Compare host and candidate; do not assume Git main equals production. In particular, determine whether payroll or time-clock cron jobs run and plan a reversible disablement without deleting records.
3. Reconcile approved current content, Sunday service links, event artwork and expired announcements from current church-provided sources. Open PRs #163, #164 and #167 contain proposals with separate baselines and must not be blindly merged. Verify mail transport and authorized test-recipient delivery without unsolicited email.
4. Produce and review a host-specific, narrowly scoped deployment and rollback plan. Preserve actual-byte backups of host code, config, editorial content and private stores, and verify host-only edits. The repository's broad rsync with `--delete` is not a safe migration plan for this candidate.
5. Complete a church-facing admin guide and credential-transfer process. Verify production after an approved deployment. Do not send payment demands or make claims of completion until the handoff and hours have been independently reconciled.

The source-level route restriction and package exclusion do not disable old files already present on an existing server. A service-worker update removes the push handler in this candidate, but previously installed workers and browser subscriptions require separate real-device verification.

## Read-only host comparison

After the package is built, `python3 tools/basic-handoff/preflight.py /path/to/installed/app /path/to/review-package` compares a fixed set of application file hashes and reports only whether protected paths exist. It does not read their contents or write to either directory. It does not check scheduled jobs, web-server rules, account access or mail, and it is not an installer. Review every difference; the tool cannot determine whether a host file contains an approved change.

The candidate branch disables the repository's automatic cPanel deployment. This is a guard, not a deployment mechanism. A separate host-specific plan and approval remain necessary.
