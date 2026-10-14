# Minimal timecard and token-session repair

Approving or returning a submitted period changed its status but left matching
shift statuses unchanged. The service modified a temporary array. It now updates
the stored entries, preserves correction and adjustment history, and refuses
malformed entries without rewriting the store. The existing own-review policy
is also enforced by the shared service before opening storage.

On an anonymous invitation or reset visit, creating the CSRF field after output
could prevent the browser receiving its session cookie when output buffering was
disabled. Both pages now start the configured session before rendering. Their
existing account, role, token, password and CSRF checks are retained.

The application change is exactly three files: `lib/timeclock.php`,
`member/activate.php` and `member/reset-password.php`. Account roles, designated
owner configuration, giving, authored public content and private record formats
are unchanged. The user remains the sole project owner and master administrator.
Broader credential and personal-device drafts are outside this repair.

Validation uses actual PHP 8.2: six timecard groups, six HTTP cases with output
buffering disabled, and four previous-source controls reproducing the defects.
The HTTP cases use only temporary synthetic accounts and tokens, include valid
CSRF denial probes, and send no messages. Exact-source checks retain historical
pins and reconstruct only the three enumerated changes from commit
`4e7ddeb82c498aab0183a9e500ffa4289091e5aa`.

Production installation must use exact code preimage checks and private backups
for these three files. Repository-wide cPanel deployment would include deferred
Operations changes. Synthetic tests do not establish real staff/device acceptance.
