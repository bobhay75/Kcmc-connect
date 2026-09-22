# Publishing review guard acceptance notes

This change keeps the existing Publishing Desk workflow but adds two independent release gates before a content write:

1. Browser-side changed-field counting and explicit administrator review confirmation.
2. Server-side enforcement of `confirm_publish=1` after CSRF validation and before `kcmc_write_content()`.

The existing event/date/time validation, automatic content backup, backup retention, and content-published audit path remain unchanged.

The review guard also listens for programmatic event-description recovery edits because that helper dispatches normal `input` and `change` events after filling a description.
