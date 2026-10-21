# Digital church bulletin and working information headings

The first repository bulletin (d560fd8, August 19) used a single reading sheet, service rows and weekly notes. This change restores that structural approach, with a paper-style church masthead, actual issue date, expandable service and weekly-information headings, and a print control that opens all sections then restores reading state.

Current saved weekly content is retained; no worship order, hymns, sermon titles or dates are fabricated. This is not claimed to be a facsimile of an unprovided printed bulletin. The existing freshness gate and no-store header remain.

Visit information, service choices, announcements, event details, serving and Church Family information open from native details/summary headings. Existing forms and watch links remain. The Stay Connected KCMC on Facebook button is removed. The misleading Event questions label becomes Call church office with its number. Prior requested removal of the calendar-download and Upcoming/Next week buttons is included.

Exactly four runtime files: index.php, events.php, bulletin.php, home-welcome.css. The approved Trunk or Treat slide is preserved. No config, private records or saved editorial content changes. CSS uses a fresh asset version. Installer accepts three whole reviewed predecessor states, refuses mixed or unknown files, lints staged PHP, creates private backups and supports rollback.

Validation: PHP syntax, rendered disclosure structure and preserved forms/artwork, stale-issue gate, and print expansion/state-restoration logic. Installer validation runs against all three predecessor states. Production browser acceptance is required after owner installation. The HTML preview is self-contained for the bulletin layout and native heading interactions.

Python 3.6 hosting compatibility: staged PHP lint captures stdout/stderr with PIPE and universal_newlines, avoiding capture_output/text keywords introduced in Python 3.7. Runtime payloads and manifests are unchanged.
