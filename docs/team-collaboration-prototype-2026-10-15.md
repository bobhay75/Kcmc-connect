# Team work and publication collaboration prototype

This isolated, unpublished increment builds on the clock, account-navigation and
push repairs from PR #144. It does not alter their frozen source or hosting
package. There are no production records, external messages or configuration
changes in the prototype or its tests.

## What it adds

One Work hub provides list, board and schedule views of actual assignments.
Publishers create tasks, choose an existing active account, set start/due dates,
priority and whether the work is blocked. Employees can update the status of
their assigned tasks and discuss those tasks. Contextual replies stay with their
task or publication. Saved personal choices cover view, status filter and sorting.

Smart order puts unfinished work first, then blocked work, overdue/today/future
or undated work, priority and stable date/ID tie breakers. Due-date and priority
orders are available. This is deterministic sorting; it does not infer private
facts or claim AI prioritization. Schedule is a date/list view, not a recurring
shift planner or payroll system.

Publication saves compare the loaded project revision while holding the actual
private-store write lock. The first save wins; stale editors receive HTTP 409
without replacing it. Their unsaved canvas remains visible, with explicit Save a
copy and Load latest choices. Existing drafts begin at revision zero without a
migration write. The normal Publishing Desk also requires the exact loaded public
content hash, checked inside its existing content lock. Publishing conflicts keep
the form input visible; the latest version can be opened separately for comparison.

Visible pages poll saved state about every ten seconds, with one request at a time,
failure backoff and a pause when hidden. Polling never overwrites a dirty editor.
This provides timely awareness of saved work; it does not merge simultaneous
character edits or require WebSockets or a new hosting service.

## Boundaries

| Person | Team tasks | Conversations | Publication designs |
| --- | --- | --- | --- |
| Existing active publisher or designated owner | Create, assign and edit | Task and publication contexts | Existing publishing access |
| Other active signed-in account | Only tasks currently assigned to that account; status updates only | Only those assigned task contexts | No access granted |
| Anonymous, inactive or expired session | None | None | Existing denial remains |

Every operation checks the server-side assignment or existing publishing
capability. Ordinary responses omit the account picker and publication IDs/names.
Reassigning a task removes the previous assignee's access. Publication conversation
access is separate from an employee task linked to that publication. No private
prayer, timecard, banking or account-role data is imported into collaboration.

Task and preference revisions are checked inside the write lock. Plain-text
comments have actor-bound request nonces to prevent retry duplicates, and reply
parents must belong to the same authorized context. Preferences are keyed by the
authenticated user, never a submitted user ID. The API uses same-origin session
cookies, CSRF validation, bounded requests and private no-store responses. Passive
reads do not extend idle lifetime and release the PHP session lock before I/O.
Audit entries contain mutation IDs and counts rather than message text.

The private team JSON store fails closed on corruption or unsafe file metadata;
there is no empty-board fallback or silent eviction. The first bounded store
supports 500 tasks, 5,000 comments and 8 MiB. These are explicit prototype limits;
retention and a larger-workspace database transition are later decisions. Existing
publication records are retained, including more than 50 projects. Draft stores
fail closed on corruption. Normal Publishing Desk saves reject damaged current
public data; the explicit backup-restore path keeps its existing behavior.

## Navigation and current limitations

Account home shows My work only when the user has an assignment. Publishers reach
the same Work hub from Administration. Administration uses compact grouped links
instead of a wall of cards. The account has one Prayer & Care entry; the untouched
legacy prayer history route is available contextually inside Prayer & Care.
Denied HTML pages keep HTTP 403 and their existing denial message, with fixed
same-app Home and My account links. Authentication, credential revocation, the
owner identity rule and prayer permissions remain unchanged.

There are no emails, pushes, external chat integrations, payroll actions, new
roles or automatic publishing. The separate payroll-recipient proposal has not
been composed into this prototype. Private backup/recovery and real multi-user
hosting acceptance remain separate deployment gates.

Local PHP 8.2 and Node fixtures cover simultaneous-process revision conflicts,
authorization, exact-byte preservation, retry deduplication, date/sorting rules,
per-user preferences, stale editor races and retained drafts. Real browser tests
are prepared for isolated CI; local Chromium startup is blocked by the execution
sandbox's socket permissions. Responsive layout and keyboard acceptance therefore
remain unverified until that browser job runs and its screenshots are inspected.
