# Owner-only Operations

The Operations hub and all ten associated page/action/export entry points require
both an existing administrator role and an exact match with the private
`KCMC_OPERATIONS_OWNER_USER_ID` environment setting. Missing configuration denies
access. The check runs before reading operational records or handling actions.
Publishing, member access, employee self-service and prayer roles remain unchanged.
The four public/member API endpoints are not Operations actions and retain their
existing access checks. Owner timecard self-approval is implemented but remains
disabled by default. It requires the private server setting
`KCMC_TIMECARD_SELF_APPROVAL_ENABLED=1`, which must not be enabled until KCMC has
explicitly approved the payroll self-approval policy. When enabled, only the configured
Operations owner can self-approve; self-return, self-adjustment and self-correction remain
blocked. The period stores `self_approved=true`, the approving actor and timestamp, and an
append-only review-history entry. The private audit log also records the self-approval flag.

## Production prerequisite

Using an authenticated private hosting session, identify the owner account's
existing immutable ID in the configured private user store. Verify the account
with the owner and confirm it has an active administrator role. Set that ID in
the PHP hosting environment, then verify it is available to PHP requests (not
only a terminal shell). Never infer the ID from a display name, commit email or
repository account, and never commit it or print private records in logs.

Before release, back up affected files, deploy the helper and guarded routes
together, and perform owner/non-owner checks. Without a verified configuration,
Operations will be intentionally unavailable. No production identity has been
configured or verified by this change. No merge or deployment is implied.

## Verification

`python3 tests/operations-owner-http.py` runs the real PHP app in a temporary copy,
using synthetic owner, other administrator, recovery administrator and employee
accounts. It covers direct GET and denied POST requests, CSV/print routes,
missing configuration, a configured non-administrator, private cache headers,
and preservation of Publishing Desk, Publisher and employee Time Clock access.
Existing signed-in/readability fixtures explicitly configure their synthetic owner.

The policy acceptance matrix also rejects unset, `0`, `true`, and `01` policy
values; missing/non-administrator owner configuration; valid-session non-owner
approval attempts; invalid CSRF; self-return; self-adjustment; self-correction
application/rejection; and repeat approval. Denied actions preserve the complete
payroll file and emit no successful review audit. Enabled approval must preserve
the prior review history and append a matching actor/timestamp plus one flagged
private audit event. All accounts and payroll records are synthetic.

The historical runtime provenance checks retain every old pin. Exact checks
retain the two-line guard insertion on all ten routes and pin the owner helper.
The self-approval fixture separately pins the complete parent and target bytes
for only `admin/timecards.php`, `lib/timeclock.php`, and `lib/audit-history.php`,
then reconstructs the parent for all historical checks. Removing a guard,
changing an unenumerated runtime file, or changing a pinned policy file fails
verification. These are source checks, not evidence of a production installation.
