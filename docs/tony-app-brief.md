# KCMC Connect — Tony briefing

Reviewed October 7, 2026. Implemented source, public observations, and production acceptance are separate statuses.

## Implemented in source
- Public PWA, Publishing Desk review-before-publish, individual authentication and invitation lifecycle.
- Private RSVP/visit/serve/groups intake, staff follow-up, CSV exports, Release Health, Operations, audit history and backup/restore tooling.
- Employee Time Clock, pay-period submission and supervisor approval, print/CSV output, auditable adjustments, and employee-requested corrections with administrator review.
- Web Push subscription and signed-in-device self-test implementation; physical-device acceptance remains open in issue #20.
- Staff Sign In wording, private-page readability repair, seven-minute carousel with no visible photo captions, single hero image plane, and multi-page Publication Designer with shared projects, media and preserved paragraphs.
- The reviewed bright Contemporary Worship panel is integrated by this repair. Its existing church photograph, visitor route and official Facebook message destination are retained.

## Observed publicly on October 7
- Sunday services show 8:00 AM Front Porch Gospel, 9:15 AM Traditional and 10:30 AM Contemporary.
- The login page says Staff Sign In and explains that the public app is free without an account. This does not establish that a staff credential works.
- Public JavaScript specifies a 420000 ms rotation and contains the family welcome code. Text extraction alone does not prove those photos render on a device.
- The public content API has no bulletin date, retains July statistics, and returns only Trunk or Treat. It is a filtered public feed, not an unfiltered host backup.

## Remaining work before church use
1. Compare fresh deployed code against the reviewed release, privately back up affected files and preserve host-only edits before applying repairs. Source tests do not establish host-byte equality.
2. Reconcile current approved bulletin and events with the unfiltered host content. Code deployment preserves existing data/content.json and therefore does not publish repository content updates. PR #89 is an October 2 source proposal; do not present October 4 as the upcoming Sunday after that date.
3. Verify real staff sign-in, Publishing Desk review/publish, private readability and installed-app refresh with authorized accounts/devices.
4. Complete physical-device push background receipt, tap navigation and opt-out/removal acceptance before closing issue #20.
5. Run read-only production smoke and public desktop/mobile checks after deployment. Facebook link availability is not playback acceptance.

## Tony's scope and newer directions
- Keep service times correct, welcome visitors without an account, use Message terminology, preserve author-supplied note text/blanks, and keep private prayer information protected.
- The earlier monthly-news source exclusion does not exclude Mary Lou's Friday updates.
- PR #103 records Tony's later instruction to rotate all supplied bridge photos/artwork, superseding the September 29 bridge exclusion. That separate image proposal remains under review; this repair does not remove or replace its supplied assets.
- Church name, hosting migration, member-directory publication and church-wide rollout remain separate leadership decisions. Tony controls Services/Announcements/Dropbox archive cleanup.

## Decisions for Tony
1. Which visitor actions should be most prominent?
2. Who owns weekly content approval and RSVP/connection follow-up?
3. Which staff/ministry roles need private access?
4. Should the Time Clock start with a staff pilot?
5. Which approved public updates warrant optional notifications?

Sources: docs/tony-launch-cleanup-2026-09-29.md; docs/installed-reconciliation-2026-10-03.md; PRs #90, #99, #102 and #103; issue #20; read-only public page/API observations. No production deployment or private workflow acceptance is claimed by this briefing.
