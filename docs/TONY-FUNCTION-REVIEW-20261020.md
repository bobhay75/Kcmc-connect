# Tony functional corrections — October 20, 2026

Draft review only. No production deployment, live content replacement, real visitor email, or staff account changes have been performed.

The parent is PR #161's reviewed family-branding source (`cac1420a905bba78a4a54651c69a8e77b57b2450`). The October 20 host transcript confirms that its branding and separately reconciled content were installed. Main alone is not an adequate production baseline. Preserve the host's `livecalendar` CSS variant; do not replace the live application or content store from this branch.

## Requested behavior

- Preserve the current navy/gold theme, app icon, fixed church-building background, typography and opening layout. Remove the newly added congregation photo galleries and redundant hidden homepage promotions. The instruction to leave the design in place is interpreted as retaining the building background; no original-design restoration is included.
- Watch Online goes directly to the official KCMC Facebook broadcasts page. The separate Watch Live screen lists 8:00 AM Front Porch Gospel, 9:15 AM Traditional Worship and 10:30 AM Contemporary Worship, with all three filter choices and exactly one authentic image per service.
- Remove the two side-by-side buttons pointing to the same archive. Each service card uses its own staff-published direct Facebook recording URL. Canonicalize video URLs, reject generic pages and unsafe destinations, and refuse the same recording for multiple services. A missing URL produces explanatory text, not a dead or mislabeled button. One shared archive link remains clearly labeled as such.
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
- PHP contract sweep: 42 of 43 suites pass, with 1,260 passing assertions. The remaining `timeclock-own-review-contract.php` failure reproduces unchanged on the parent snapshot. Current owner/manual-clock behavior passes its current contracts and signed-in browser test. No unrelated timeclock change is included.
- Cache privacy: all 28 checks pass. Client resilience: 3 checks pass. Invitation client: 17 checks pass. All 88 PHP files lint successfully; JS parse and whitespace checks pass.

## Release blockers and remaining live acceptance

1. The three actual service-specific Facebook video URLs have not been independently obtained. The official church website publishes a shared Facebook broadcasts link. Staff must supply/verify each distinct recording in the new Publishing Desk fields. Do not substitute three copies of the shared archive.
2. Inspect the host's current welcome-email configuration, authorized sender, SPF/DKIM and transport; obtain an approved test recipient and verify inbox receipt before stating production delivery works. The implementation remains disabled unless existing server-only welcome settings enable it.
3. The historical exact-source reconciliation gate currently rejects the intended `index.php` changes against its previous immutable branding fixture. A new independently reviewed reversible source layer and updated guarded host transaction are still required before release. No historic fixture or security gate has been relaxed, regenerated or bypassed in this draft. Do not reuse PR #161's exact-hash installer for these new bytes.
4. Recheck real external Facebook, giving, directions and youth destinations and the actual signed-in host workflows. Local link-target checks establish internal targets, not successful third-party account access or live delivery.
5. Obtain Robert's production-release approval after the concrete review and host preflight. No apply command is included here.

## Weekly bulletin operation

Each week, use Mary Lou's approved Front Pew News/current church announcements as the source. Confirm the Sunday issue date, all service times, upcoming community event dates/times/location, expired announcements and the author's exact message notes. Review and publish through the guarded Publishing Desk, then check the public bulletin on a phone. Its seven-day freshness rule prevents an old issue being presented as current; it cannot replace the church's weekly editorial review. No recurring task or automatic content publication was enabled.

## Source of the service photograph

The Front Porch Gospel photo comes from the church's existing homepage (`frontporch.jpg`), fetched unchanged from the original Wix image URL recorded in `assets/visuals/SOURCE.md`. Traditional and Contemporary use the supplied October 18 KCMC photos. No generated congregation photos are used.
