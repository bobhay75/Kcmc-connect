# October 18 weekly content update — prepared for review

Source: Robert Hayes supplied the October 16, 2026 Front Pew News and requested both app updates and announcement slides on October 18. His confirmed correction controls the Bible study: Friends of Faith at 10:20 AM, Becoming Like Jesus by Matt Chandler, Pairs & Spares Classroom. This is one class, and the announcement does not say “New.”

## App content

- Add 17 dated events for October 18–23, including the Way Forward meeting October 22 at 1:30 PM. The existing corrected Bible study is retained without duplication.
- Add three expiring announcements: Way Forward, the memorial dinner, and Friends of Faith.
- Refresh the dated bulletin for October 18–24, replacing past October 15–16 reminders.
- Update the existing Trunk or Treat description with the bounce house, hot dogs, hot cider and costume contest. Preserve 4:30–6:30 PM October 31, existing artwork, location, RSVP behavior, and ID. Extend the existing volunteer announcement with this Sunday's signup request while retaining previously supplied guidance.
- Update the existing PLL announcement and event to say change or folding money, with an October 25 date-only return deadline. No return hour is invented.
- Preserve the existing November 14 dinner event at 4:30 PM, Fellowship Hall, $15 each.
- WEB Kids is 9–10 AM October 22. The newsletter does not identify its location; the new record leaves location blank and directs readers to the office rather than assuming church grounds.
- Keep worship definitions, historical events, contact fields, archived September material, metadata, sponsors, and all private records unchanged. No recurrence, additional choir practice, or unlisted preschool dates are inferred. All times use America/Chicago; November expiry uses standard time.

## Content review and privacy

The newsletter's staff contact list and Sherri DeBoom's personal number are not copied into public content. Public questions use the existing church office number. The earlier hold on changing the office email remains open. Prayer language stays generic. No raw email, named prayer request, medical detail, private record, runtime code or security change is included.

## Validation

`python3 tests/editorial-content-source.py` retains the previous historical snapshot and 11 negative controls, then verifies the complete October 18 update against its pinned reviewed fixture. It also checks unique IDs, the single corrected class, date-only bottle deadline, unchanged service definitions and contact fields, and protected historical sections. The installed-reconciliation suite invokes this check.

## Publishing after separate owner approval

This review changes repository content only. The host preserves `data/content.json`, so merging this PR or deploying runtime files alone does not establish publication. Never overwrite live content with the complete repository snapshot.

Before an authorized publication, back up current live content privately. Compare the exact IDs and fields in `tests/fixtures/editorial-content-20261018-reviewed.json` with current live records. Apply missing events and announcements and the four reviewed existing-record changes through the existing publishing workflow. Preserve unrelated edits. Reconcile matching records that differ rather than silently overwriting. Check the current bulletin before replacing its four dated fields.

Skip events and announcements that have expired at publication time. Update “this Sunday” wording if publishing after October 18. Read back and verify public event rendering, calendar times, the date-only bottle deadline, correct class details, expiry and privacy. No merge, deployment, live write, email, or Dropbox upload is included in this preparation.
