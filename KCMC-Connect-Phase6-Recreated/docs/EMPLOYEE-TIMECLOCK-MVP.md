# KCMC Connect — Employee Time Clock MVP

Status: draft implementation contract; no production deployment

## Goal
Add payroll-ready employee timekeeping to KCMC Connect without turning the application into a payroll processor. KCMC Connect records time, daily work descriptions, approvals, and audit history. The CPA/payroll process remains responsible for rates, withholding, taxes, and pay calculations.

## Pay period
Default KCMC pay period: 23rd through 22nd. This must be configuration, not hard-coded business logic.

## Employee workflow
1. Sign in with the existing KCMC account.
2. Open **Time Clock**.
3. Clock In.
4. Start Break / End Break as needed.
5. Clock Out.
6. Before the day can be completed, provide a daily work description and select one or more work categories.
7. Review the pay-period time card.
8. Submit the completed period for supervisor review.

A running shift always shows the authoritative server timestamp. Client-provided timestamps must not be trusted for punches.

## Initial work categories
- Office / Administration
- Maintenance / Facilities
- Media / Worship
- KCMC Connect / IT
- Events / Outreach
- Other

Administrators may manage categories later; the first release can use a controlled list.

## Time entry model
Each shift needs:
- immutable entry ID
- employee account ID
- work date in church local timezone
- clock-in timestamp
- clock-out timestamp
- zero or more break intervals
- calculated gross minutes
- calculated unpaid-break minutes
- calculated net minutes
- work category
- required daily description
- status: open, completed, submitted, approved, returned
- created/updated timestamps

Store duration in integer minutes. Display decimal hours only as a derived value.

## Audit model
Never silently overwrite payroll evidence. Every correction creates an audit event containing:
- entry ID
- actor account ID
- actor role
- action
- before value
- after value
- reason
- server timestamp

Employee corrections after submission become requests. An authorized reviewer approves or rejects them. Approved periods are locked except for an administrator correction that creates another audit event.

## Roles
**Employee**
- punch own time
- enter own descriptions
- view own history
- submit own pay period
- request corrections

**Supervisor / Administrator**
- view submitted employee periods
- return a period with a reason
- approve a period
- process correction requests
- export approved time cards

An employee must never be able to read another employee's time data through either UI or direct API requests.

## Submission and approval
A pay period cannot be submitted while it contains:
- an open shift
- an open break
- a completed shift without a description
- a correction awaiting employee completion

Submission records employee certification and server timestamp. Approval records reviewer account and server timestamp.

## CPA / monthly turn-in
Generate a professional pay-period package containing:
- church name
- employee name
- period start/end
- each work date
- clock-in / clock-out
- break minutes
- net daily hours
- category
- daily work description
- period category totals
- total net hours
- employee submission timestamp
- reviewer approval timestamp
- correction/audit indicator when applicable

Exports:
1. printable PDF
2. CSV suitable for accounting/payroll import

No wage rate, tax, withholding, or paycheck calculations in MVP.

## Privacy and security requirements
- authenticated access only
- CSRF protection on every state-changing request
- server-side authorization on every read/write
- server-generated punch timestamps
- prepared statements / safe storage operations
- no GPS tracking in MVP
- no public time-card URLs
- no payroll information in PWA caches
- no employee time data in push payloads
- fail closed when identity, authorization, or storage validation fails
- audit events append-only through application code

## Recovery rules
If an employee forgets to clock out, do not invent an end time. Mark the entry incomplete and require a correction request or authorized correction with reason.

If network connectivity is unavailable, the MVP does not fabricate an offline punch time. The UI may record a local intent for display, but the payroll record is created only when the server accepts it and must clearly identify the accepted server time. Offline payroll punching can be designed separately with signed receipts if KCMC later needs it.

## Administrator dashboard
Add a **Time Cards** tile alongside existing administration tools showing:
- periods awaiting review
- open/incomplete entries
- returned periods
- approved periods ready for export

## Acceptance tests
- employee can clock in only once at a time
- employee cannot clock out while a break is open
- description required before completion/submission
- employee cannot read another employee's entries
- non-admin cannot approve a period
- CSRF failure performs no mutation
- duplicate punch request is idempotent or rejected without duplicate time
- net minutes equal gross minutes minus closed breaks
- 23rd–22nd period boundary is correct across month/year boundaries
- incomplete entries block submission
- approved period is locked
- authorized correction preserves before/after audit evidence
- CSV total equals UI total
- PDF total equals UI total
- time data is excluded from public/PWA caches

## Release gate
Do not deploy until automated tests pass and a production-style manual test verifies: employee punch flow, description, submission, admin approval, correction audit, PDF/CSV totals, authorization isolation, and mobile layout.
