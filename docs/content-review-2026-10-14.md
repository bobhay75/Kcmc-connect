# October 14 editorial update — draft, not released

Sources: owner-supplied October 9 Front Pew News and Trunk or Treat volunteer note.
Prepared against main 6ed4a87bd1e0a410bcf89c93357727ee59ec3e81. Source attachments are deliberately not committed: the newsletter contains private prayer details.

## Proposed app changes
- Append 13 dated October 14–16 and November 14 events; no inferred recurrence or end times.
- Add two expiring announcements: Trunk volunteer guidance and the October 25 PLL bottle deadline.
- Update office opening time to 8 AM, Tuesday–Thursday.
- Replace the stale bulletin notes with a clearly dated community update. Keep all three service times unchanged.
- Keep all prior events and announcements as history. October 11–13 items are not resurrected.
- Use existing KCMC imagery; no image or security changes.

## Holds requiring confirmation
- Existing Trunk event remains byte-for-byte equivalent as parsed JSON, including 4:30 PM start / 6:30 PM end. Newsletter says 6–8 PM; volunteer note says 4:30–6:30 PM but also says 6 PM in one closing reminder. No time or calendar-field change is proposed. Volunteer reminder uses “until the event is over and families have cleared the area,” without choosing an end time.
- Existing office email remains unchanged. Newsletter names another address; do not replace or supplement it until confirmed.
- 3:30 PM volunteer arrival comes directly from the new note, is distinct from the public event start, and should be checked when leadership resolves the schedule.
- Attendance of 200 is a planning estimate, not guaranteed or historical attendance.

## Privacy and release boundary
No named prayer concerns, medical details, raw source emails, personal contact list, authentication, Operations configuration, or private records are included. Prayer remains generic; no private prayer-store write is proposed.
Do not merge or deploy without separate approval.

## Production application after approval
The host preserves data/content.json; merging or deploying runtime files alone will not necessarily apply these editorial changes. Do not overwrite the production content file with this repository snapshot.
Read the current production content privately; compare IDs and existing fields; apply only the 13 absent/new event IDs, two announcements, office-hours field and reviewed bulletin fields through the existing publishing workflow. Preserve all unrelated live edits, Trunk fields, office email and private data. If a matching ID or bulletin has changed, reconcile before writing.
Skip already-expired dates when applying later. Recheck the bulletin at publication time so this dated October 14 update is not presented as a newer Sunday sermon.
Back up and read back any future content update, then verify public rendering, expiry, calendar behavior and privacy.

## Validation
JSON parsing, unique event/announcement IDs, all 13 event dates and expiry ordering, preserved historical records, unchanged full Trunk event, unchanged email, unchanged services and unrelated top-level sections, and exact allowed field scope are checked during preparation.
No live application, browser, PHP or production test is claimed by these static content checks.
