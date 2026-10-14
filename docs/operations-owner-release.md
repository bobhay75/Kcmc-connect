# Scoped Operations guard release

The existing application guard restricts Operations to the configured active administrator owner. This release tool makes that protection independently deployable to an installed copy without replacing its other application code or content.

The fixed scope is the existing `lib/operations-owner.php` helper plus ten Operations entry points: the hub, health, audit and audit export, push, public-content backup and restore, and timecard review/export/print. The guard is inserted immediately after bootstrap and before any operational work. Direct GET and POST requests are covered, including export routes. Missing owner configuration denies access.

Publishing, Publisher, account administration, member pages, prayer roles, Prayer & Care, and employee self-service keep their existing permissions. The tool never reads or writes user or prayer records and never changes the owner setting. No homepage, public content, images or calendar files are released. Existing navigation is unchanged; an unauthorized direct Operations link is rejected by the server.

## Review and release

This PR does not deploy automatically. Run the following only against an explicitly approved application root. Use an absolute private backup directory outside the web application and its document root. Keep this directory and any output private. Verify the owner setting reaches PHP web requests and matches the approved active administrator before release; shell configuration alone is insufficient.

1. Run `python3 tools/release-operations-owner.py APP_ROOT` for a read-only preflight. The script needs the repository's reviewed helper alongside it.
2. After release approval, run `python3 tools/release-operations-owner.py APP_ROOT --prepare NEW_PRIVATE_BACKUP`. This validates every route, backs up exact installed bytes, stages only guard insertions and the helper, and lints all staged PHP. It does not change live files.
3. Review the private manifest and release scope. Run `python3 tools/release-operations-owner.py APP_ROOT --apply PREPARED_BACKUP` only after approving that concrete release. The script refuses changed installed files, modified staging/backups, unexpected helper bytes, ambiguous PHP prologues and reused releases. It installs the helper first, verifies replacements and restores already-touched files if a write fails.
4. Verify owner access and non-owner rejection for Operations, including direct action/export URLs, without displaying operational or prayer records. Verify normal publishing/member/prayer access remains unchanged. Do not create production test users or change anyone's role to test the boundary.

Keep the backup for recovery. Restoration of unguarded routes would reopen Operations to the previous administrator audience, so any later rollback requires an explicit security decision. Do not perform a broad application sync as part of this repair.

## Synthetic acceptance

`tests/operations-owner-release.py` tests unchanged installed customizations, exact file scope, preparation without live mutation, tamper/concurrent-change refusal, rollback on an injected write failure, and repeat-run behavior. `tests/operations-owner-http.py` removes the guards from an isolated fixture, repairs it using the release tool, then tests real PHP login sessions. It verifies owner access, other administrator/member rejection, unset/mismatched configuration, denied POSTs, private headers, and normal access to publishing, account tools, member security/notifications, Time Clock, and Prayer & Care. No production identities or records are used.
