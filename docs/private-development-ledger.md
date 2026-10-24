# Private KCMC Connect development ledger — specification

This ledger is separate from the church employee time clock and is never exposed to public app visitors.

## Record structure
- Immutable session ID, actor (owner or AI-assisted action), source, task, started_at, ended_at, created_at.
- Evidence references (GitHub commit, PR, test run, deployment), activity classification and review status.
- Break intervals and explicit nonbillable exclusions.
- Each AI action records a timestamp and deliverable, not fabricated human-equivalent hours.

## Billing rules
- Human work and AI-assisted work are consolidated into one project timeline.
- Calculate billable elapsed time from confirmed active intervals; merge overlapping intervals before summing.
- Do not count unattended AI processing, idle gaps or unverified activity automatically.
- Keep raw event records unchanged; corrections are appended with actor, reason and timestamp.
- Keep gross hours, exclusions, discounts and approved net hours as separate fields.
- Export only owner-reviewed, approved entries to a timecard; never sync automatically to payroll.

## Access and integration
- Private owner-only authenticated area with CSRF protection and server-side authorization.
- Never reuse or mutate the church staff timeclock store.
- Record GitHub webhooks only after signature validation and deduplicate by event ID.
- ChatGPT activity requires an explicit integration; conversation timestamps alone do not constitute a live tracking feed.
- Timezone: America/Chicago; persist UTC instants and render Central local time.
- Audit access, edits and exports; keep backups.

## Acceptance tests
- Overlapping human and AI intervals are counted once.
- Idle intervals excluded; break intervals excluded.
- Duplicate webhook deliveries do not create duplicate records.
- Public visitors and nonowner staff cannot read or modify the ledger.
- No payroll write is possible from the private ledger.
- Corrections preserve original events.
