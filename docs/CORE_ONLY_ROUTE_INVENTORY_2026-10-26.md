# Core-only route inventory — first pass

Source: GitHub directory listings from handoff/core-only-20261026. This is a filename-level inventory, not a dependency audit.

## Public candidates
index.php, events.php, bulletin.php, news.php, connect.php, care.php, backpack-blessing.php; associated assets, styles and JS. Verify whether care.php or connect.php invokes member-only functions.

## Basic admin candidates (retain only after access/dependency review)
admin/login.php, logout.php, index.php, home.php, event-create.php, posts.php, save.php, setup.php. Evaluate whether existing content edits rely on publication infrastructure.

## Excluded from delivery pending dependency isolation
- Publisher: admin/publication-designer.php, publication-media.php, publication-projects.php, publishing-desk.js
- Members: entire member/ directory and related private account functions; admin/users.php, admin/prayers.php, admin/prayer-care.php, admin/prayer-inbox.php, admin/password-resets.php
- Payroll/time clock: admin/payroll-setup.php, admin/timecards.php, admin/timecards-export.php, admin/timecards-print.php, admin/timeclock-period-close.php, member/timeclock.php
- Collaboration: api/team-workspace.php, member/work.php, member/workspace.js, member/workspace.css
- Advanced operations and privacy-sensitive tools: admin/operations.php, admin/audit-export.php, admin/backup.php, admin/restore.php, admin/connections-export.php, admin/rsvps-export.php; disposition requires authorization and security review.

## Blocking checks
- Search all PHP requires/includes, navigation links and JS fetch calls before removing any route.
- Determine whether api/content.php, api/connection.php and api/rsvp.php serve public functions.
- Confirm minimum viable administrator login and safe content editing independent of Publisher.
- Do not ship production private data, credentials or customer/member records.
- Preserve existing production behavior until approved cutover.

No files removed, no host changes, no acceptance claimed.
