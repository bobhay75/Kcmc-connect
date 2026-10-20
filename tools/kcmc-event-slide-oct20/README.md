# Tony event slide correction — October 20, 2026

Uses Robert’s uploaded image(3).png as the Trunk or Treat artwork. The original 1200×675 content is retained in a JPEG embedded in the existing SVG asset URL, so saved event records remain compatible. No generated replacement artwork is used.

Removes nonfunctional date/category pills from public event cards. For Trunk or Treat, date and time are shown by the slide; the parking-lot location, description, telephone action and Add to Calendar remain. Other events retain plain-text dates and times. Calendar data attributes are unchanged.

Three runtime targets only: index.php, events.php, assets/visuals/trunk-or-treat-2026.svg. No config, saved content, account or private record edits. Requires the exact installed Tony functional release. The installer checks all preimages and payloads, creates a private backup, replaces files atomically and supports rollback using the returned backup path.

Validation: PHP syntax checks pass. Temporary-app install/check/idempotence/rollback passes. Rendered HTML confirms the slide and working controls, no date/category pills or duplicate time, and unchanged calendar metadata. Embedded bitmap decodes at 1200×675. Production browser review remains required after owner installation.
