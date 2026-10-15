# Narrow owner UI and account guards

This separate source-only follow-up contains two independently pinned repairs
over canonical source commit `93c72f4fc430d311e01108d3a30d0561bb701c9d`. It is based
on the completed session-binding and deployment-preflight source work and is
intended for a reviewable follow-up PR after that work reaches main. The owner
authorized continued audit repairs and remains the sole designated master
administrator until handoff. No hosting, GitHub, owner configuration, credentials,
user records, roles, schema or private records were changed.

These are not host-ready packages. They depend on the existing owner identity
helper in the reviewed 93 source. The older live154 bootstrap lacks that helper;
its owner route guard installation alone does not make these calls compatible.
Resolve the exact host/bootstrap lineage before preparing any scoped installer.

A7 changes one condition in `member/notifications.php`: Send update now uses the
existing `kcmc_is_designated_owner()` helper. Device subscription controls remain
available to members. The actual owner-only `admin/push.php` gate and sender are
byte-identical to the reviewed source.

A5 adds an exact designated-owner target guard to the existing password-reset
capability and administrator account-status action. Other administrators cannot
mint an owner reset link or disable the active configured owner, even with a
crafted valid-CSRF POST. Owner rows explain this restriction instead of offering
misleading controls. The role-based staff reset/status rules, active-account
checks, self-disable restriction and administrator self-reset policy remain
unchanged. The owner changes their own password through Account Security.

These guards reuse the current `KCMC_OPERATIONS_OWNER_USER_ID` setting and the
existing active administrator identity helper. They do not infer a new owner
when that setting is absent or alter role-based prayer privacy. This narrow
patch does not revoke or reinterpret reset tokens issued before the guard;
existing bearer-reset handling is outside its scope.

## Validation

`tests/owner-ui-narrow-routes.py` executes the real PHP routes in fresh PHP CLI
processes with temporary synthetic users, sessions and stores. It opens no
socket, sends no email/push and calls no production site. Nine cases cover both
owner administrator roles, the link/destination authorization matrix, crafted
status/reset POSTs, active actors, bad CSRF, self-policy and ordinary staff
workflows. The tests prove route authorization, rendered controls and store
effects; they do not claim HTTP transport or browser verification.

`tests/owner-ui-narrow-negative.py` verifies three separate exact unchanged-source
negative controls fail for the old Send update link,
owner-disable POST and owner-reset POST. The existing password lifecycle and 22
owner capability/privacy contract checks pass without changes.

`tests/owner-ui-narrow-source.py` proves each modified file is exactly the listed
reversible replacements over the canonical commit, pins each fixture and target
hash, and proves the owner-only push implementation remains unchanged.

## Integration and CI

The follow-up changes four existing runtime paths. A7 and A5 remain independently
pinned by `push-owner-link-reviewed.json` and `owner-account-guard-reviewed.json`.
The full installed provenance proof first reverses these exact fixture deltas,
then executes every prior session, owner/privacy, fish, calendar and deployment
assertion. Only the four verified paths extend the two final runtime scope sets.
No older fixture or assertion is discarded or weakened.

The focused `owner-ui-narrow.yml` workflow uses the existing pinned checkout
action, full source history and the supported PHP 8.3 runtime on Ubuntu 24.04. It
runs syntax, full provenance, isolated route cases, exact prior-source negative
controls and the unchanged password/owner privacy contracts. Locally the same
contracts and syntax were validated with PHP 8.2.34. The workflow performs no
publishing, deployment or external delivery.
