# Interactive calendar release plan

## Safety
The protected index.php was restored byte-for-byte. Do not bypass checksum guards or deploy this branch until the calendar has a reviewed integration point.

## Required behavior
- October 31, 2026: Trunk or Treat, 4:30–6:30 PM, church parking lot.
- Render a month grid with visible markers on dates with published events.
- Selecting a date opens the original event slide image and the event title, date, time, location and description.
- Provide previous/next month controls, keyboard-accessible date buttons, and an enlarged slide view.
- Derive all calendar markers and details from the same published event data; do not duplicate event content.
- Retain current branding. Remove redundant public event controls only after integration tests are updated.
- Preserve staff-only operations and private data.
- Confirm that cPanel's preserved data/content.json includes the Trunk or Treat record.
- Test on Android and desktop before merging.

## Current blocker
Existing CI pins the exact bytes of index.php. Integration requires an approved change to that protection contract or a separately approved extension point; neither has been authorized yet.
