# KCMC Connect — Core-only handover scope (October 26, 2026)

Status: isolation branch; NOT a production release. Source baseline: main ff948840c7437efc41bc2846774f792ffe6bf654.

## Deliver only
- Approved church homepage/branding, three Sunday services, verified worship links
- Visitor information, contact, and plan-your-visit
- Events and interactive calendar, announcements, current bulletin
- Secure basic admin login and essential edits to events, announcements, bulletin and church details

## Exclude from handover UI and release package
- Publisher / Publishing Desk and advanced publishing workflows
- Member registration, profiles, prayer/member portals, pastoral approval workflows
- Sermon Assistant and other AI assistants
- Smart Clock, employee time clock, payroll and scheduling automation
- Team collaboration and experimental productivity modules
- Private developer ledger, personal billing evidence, development-only utilities

## Implementation constraints
1. This document is a scope lock, not proof of removal. Audit route references, includes, links, assets, background jobs, admin permissions and stored data before modifying files.
2. Never delete or alter existing church records, payroll, prayers, accounts or editorial content; exclude unnecessary private stores from distribution and preserve authorized backups.
3. Basic admin must edit content without exposing Publisher or member workflows; replace dependencies only after tests demonstrate equivalent core functionality.
4. No changes to live cPanel hosting, credentials, production data, church accounts or DNS without explicit owner authorization.
5. Preserve complete historical source and contribution evidence in the original repository. Keep reusable modules separate only where ownership/licensing permits.
6. Do not add post-termination development hours to the KCMC invoice without confirming authorization.

## Release gates
- [ ] Inventory production entry points, dependency graph and private stores
- [ ] Isolate excluded modules and navigation on this branch
- [ ] Implement minimal secure admin content edits
- [ ] Reconcile current calendar, bulletin, service links and event images
- [ ] Run PHP lint, integration/security tests and mobile/desktop acceptance
- [ ] Run read-only host preflight and confirm mail delivery with approved recipient
- [ ] Produce checksum manifest, rollback package, basic admin guide and limitations
- [ ] Obtain explicit authorization before production deployment and transfer

Estimated 14–26 focused hours is provisional, not verified work time.