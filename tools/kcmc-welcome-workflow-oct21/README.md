# KCMC Connections welcome workflow

Adds an authenticated welcome-draft editor to the existing Connections inbox and a public, printable welcome package. Drafts are private, protected by existing Pastor Admin / Recovery Admin authorization and CSRF, and use revision checks to prevent lost edits. Staff open saved drafts in their email app and send there; saving never sends or marks a person contacted.

New visit, volunteer and group-interest requests receive a one-time welcome response when an existing church mail sender is configured. Reuses the existing private delivery claims, recipient suppression window and validated sender configuration; no historical requests are emailed during installation. Inbox status describes mail handoff, not confirmed inbox delivery. No new account roles, payment features or mailing-list subscription are added.

Removes Event RSVP admin navigation/statistics while preserving response records and existing endpoints. Other public content and design remain intact.

Installer supports Python 3.6, validates payload hashes, checks every resulting PHP file and runs isolated fake-mail tests before mutation. It backs up replaced files outside public_html, preserves file modes and rolls back partial writes. Run `python3 -I -B install.py check` for a read-only preflight, or `apply` to install. `--root PATH` is available for disposable fixture validation.

Validation: PHP 8.3 syntax checks, isolated welcome sending/deduplication/draft tests, fixture apply and idempotent preflight, HTTP anonymous GET/POST login redirects and public welcome-package rendering. No real email was sent during tests.
