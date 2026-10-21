# Simplify public Events navigation

Remove the Upcoming and Next week filter buttons. Events opens directly to upcoming community gatherings. Keep Church calendar as a distinct wider schedule, with Community events as its return action. Old event_view=next-week bookmarks now show upcoming events, so there is no hidden filtered state without controls.

Preserves the uploaded Trunk or Treat slide, calendar downloads, event questions and all saved records. Exactly index.php and events.php change. The supplied installer requires the verified slide-cache release, checks exact preimages, makes a private backup and supports rollback.

Validation: PHP syntax and rendered pages pass; both old next-week URLs show upcoming events; distinct calendar link preserved; installer apply, repeated apply and rollback pass in an isolated app copy. Live verification follows owner installation.
