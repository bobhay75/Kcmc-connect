# Tony functional corrections — October 20, 2026

Draft review only. No production deployment, live content replacement, real visitor email, or staff account changes have been performed.

The parent is PR #161's reviewed family-branding source (`cac1420a905bba78a4a54651c69a8e77b57b2450`). The October 20 host transcript confirms that its branding and separately reconciled content were installed. Main alone is not an adequate production baseline. Preserve the host's `livecalendar` CSS variant; do not replace the live application or content store from this branch.

## Requested behavior

- Preserve the current navy/gold theme, app icon, fixed church-building background, typography and opening layout. Remove the newly added congregation photo galleries and redundant hidden homepage promotions. The instruction to leave the design in place is interpreted as retaining the building background; no original-design restoration is included.
- Watch Online goes directly to the official KCMC Facebook broadcasts page. The separate Watch Live screen lists 8:00 AM Front Porch Gospel, 9:15 AM Traditional Worship and 10:30 AM Contemporary Worship, with all three filter choices and exactly one authentic image per service.
- Remove the two side-by-side buttons pointing to the same archive. Each service card uses its own direct Facebook recording URL: the verified October 18 recording by default, with staff-published replacements supported. Canonicalize video URLs, reject generic pages and unsafe destinations, and refuse the same recording for multiple services. A missing URL produces explanatory text, not a dead or mislabeled button. One shared archive link remains clearly labeled as such.
- Change the Partner Hub heading to Church Family. Add Back under church updates and under the bulletin's Stay Connected section.
- Upcoming Events highlights community events instead of routine classes and internal meetings. Trunk or Treat (October 31, 4:30–6:30 PM) precedes the November 14 Lasagna Dinner. The wider church calendar remains accessible; staff meetings and preschool are excluded from public event lists. Staff can explicitly select future event highlights in the Publishing Desk. Publication, embargo, deletion, recurrence, expiration and chronological ordering remain enforced.
- Visit, connection/group, and serving requests receive the appropriate one-time welcome after the request is saved, when the existing authorized mail configuration is enabled. Deduplicate across forms and preserve requests when mail is disabled or rejected. No recurring subscription is created and no staff-invitation permission is granted.
- Mark an old/undated weekly bulletin as awaiting an update, suppress its obsolete title/notes, show its actual issue date when current, and prevent its caching. Do not fabricate new weekly announcements or silently advance dates. Keep approved literal message notes and fill-in-the-blank spaces intact.

## Verification

Focused local tests use the real PHP app and isolated synthetic private stores. Email is captured locally; stream URLs in tests are synthetic. Browser traffic for public acceptance is restricted to the local fixture. A separate authenticated fixture exercises the Publishing Desk's service-link save and duplicate refusal.

- Public acceptance: 200 checks pass; phone widths 320 and 390; desktop 1440; routes, filters, image loading, search empty state, Back, preferences, event calendar download, local link targets, three public forms, actual captured PHP mail, bulletin current/stale behavior, and content write boundaries.
- Existing visitor browser/API acceptance: welcome delivery, disabled mail, transport failure, duplicate handling, cross-site and method rejection, next steps, and unchanged public editorial data.
- Existing signed-in browser acceptance: account, Publishing Desk, manual Clock In/Out, owner corrections, CSV/print, RSVP/follow-up inboxes, Operations, Release Health and notification controls.
- Existing Publisher control audit: templates, text/photo/shape controls, page operations, arrange/undo/redo, drag/resize/keyboard controls, shared save/reopen, duplicate and print preparation. This audit uses synthetic endpoints; actual host media/storage and projection acceptance remain separate.
- PHP contract sweep: All current PHP contract suites pass. The one legacy self-review contract runs through its historical service reconstruction and passes there, as required by the existing CI workflow. The legacy `timeclock-own-review-contract.php` is correctly run through `historical-timeclock-review.py` against its pinned historical service; that complete historical test now passes. Current owner/manual-clock behavior passes its current contracts and signed-in browser test. No unrelated timeclock change is included.
- Exact-source and release acceptance: installed reconciliation, all seven historical negative-control suites, current functional tamper controls, deployment divergence, historical branding package reproducibility, and the 14-target functional transaction all pass. The transaction tests interrupt after every live replacement and verify exact automatic recovery.
- Cache privacy: all 28 checks pass. Client resilience: 3 checks pass. Invitation client: 17 checks pass. All 88 PHP files lint successfully; JS parse and whitespace checks pass.

## Release status and remaining live acceptance

1. Verified October 18 recordings now provide three distinct, dated defaults. The titles and dates were checked on the public KCMC Facebook video pages. Staff can replace each link in the Publishing Desk when a new service is broadcast; a past recording is not labeled currently live. The verified URLs are recorded in tools/kcmc-tony-functions-oct20/README.md.
2. Inspect the host's current welcome-email configuration, authorized sender, SPF/DKIM and transport; obtain an approved test recipient and verify inbox receipt before stating production delivery works. The implementation remains disabled unless existing server-only welcome settings enable it.
3. Exact-source reconciliation now passes using a separately pinned, reversible functional layer. All earlier fixtures remain unchanged. A new 14-target host transaction is built and tested for main/livecalendar, including fault injection after every replacement, all-PHP lint before writes, actual-byte backups, and refusal after unknown/concurrent edits. Do not reuse PR #161’s installer for these new bytes. Actual host preflight and production approval remain outstanding.
4. Recheck real external Facebook, giving, directions and youth destinations and the actual signed-in host workflows. Local link-target checks establish internal targets, not successful third-party account access or live delivery.
5. Obtain Robert's production-release approval after the concrete review and host preflight. No apply command is included here.

## Weekly bulletin operation

Each week, use Mary Lou's approved Front Pew News/current church announcements as the source. Confirm the Sunday issue date, all service times, upcoming community event dates/times/location, expired announcements and the author's exact message notes. Review and publish through the guarded Publishing Desk, then check the public bulletin on a phone. Its seven-day freshness rule prevents an old issue being presented as current; it cannot replace the church's weekly editorial review. No recurring task or automatic content publication was enabled.

## Source of the service photograph

The Front Porch Gospel photo comes from the church's existing homepage (`frontporch.jpg`), fetched unchanged from the original Wix image URL recorded in `assets/visuals/SOURCE.md`. Traditional and Contemporary use the supplied October 18 KCMC photos. No generated congregation photos are used.
