# Next-week public calendar

The Events view and standalone events.php page offer Upcoming and Next week links.
Upcoming retains the existing next-occurrence listing. Next week shows Sunday through
Saturday of the following calendar week in America/Chicago, with the date range visible.
The choice is shareable using ?event_view=next-week#events and works without JavaScript
on the standalone page. Malformed or unknown query values fall back to Upcoming.

Weekly series are projected into that week without writing to storage. One-time events
appear only when their existing date falls within the selected week; they are never
rescheduled or made recurring. Hidden, deleted, retired, expired and embargoed entries
remain excluded. Calendar downloads use the occurrence date displayed on the card.
Existing RSVP behavior is unchanged and still refers to the series, not separate attendance
for each weekly occurrence.

Only public events are read. No prayer records, roles, Operations guards, contact information,
or imagery are changed. No production content or code is deployed by preparing this PR.

Validation: tests/event-calendar-contract.php covers week boundaries, DST, year rollover,
visibility restrictions, recurrence end dates, unchanged one-time records and malformed
queries. tests/event-calendar-browser.py covers desktop/mobile keyboard navigation,
occurrence-specific ICS downloads, private/hidden exclusion, standalone rendering and
unchanged storage in a temporary local fixture.
