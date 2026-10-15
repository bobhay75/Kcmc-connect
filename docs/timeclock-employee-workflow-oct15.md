# Employee time clock and administrator payroll review

Employees clock in and out using KCMC server timestamps. Work notes and categories are optional. Clock Out also ends a running unpaid break at that same timestamp. The screen shows the current-period completed-hour total and the latest 50 shifts, including correction requests with reasons. It has My account and Home links. Employee POSTs cannot submit or approve a pay period.

A current period submitted or approved early no longer disables the clock. A successful new punch reopens that period for administrator review, retains the prior submission/approval attribution in `review_history`, and keeps all original shifts and correction evidence. A duplicate or invalid punch changes no records. Existing completed historical shifts cannot be edited by punch actions.

The configured active administrator identified by the existing `KCMC_OPERATIONS_OWNER_USER_ID` may review their own time card and correction requests. This uses the existing owner helper and real account lookup. A supplied POST `reviewer_id` does not grant authority; routes use the signed-in account. Other reviewers retain the self-review restriction. Reasons and before/after evidence remain required for corrections. Approved entries remain unavailable to the duration-adjustment action; their documented correction workflow remains available.

Administrator Time Cards shows current cards as well as closed periods. Prepare for review, approve, return, adjustment, and correction-review actions live here. Period preparation no longer requires employee work descriptions. An open shift prevents preparation or approval; its clock-out time is never invented. Return means administrator follow-up; employees continue to use the correction-request form rather than submission controls.

## Period-end queue

`kcmc_timeclock_close_due_periods()` groups shifts by their existing America/Chicago work date, using the existing 23rd–22nd pay-period rule. At local midnight after the 22nd, completed periods receive summed minutes, completed-shift counts, and submitted status. A still-open or overnight shift produces `needs_attention`; only completed-shift minutes are included until the employee clocks out. All actual minutes of an overnight shift stay assigned to its original work date, as in the existing model. It does not split shifts, fabricate punches, move dates, or send money.

The function recomputes under the existing private-store lock. Retries do not duplicate periods or replace unchanged records. Corrected and adjusted totals are recomputed under the same lock; applied correction markers and rejected-request states are persisted. Approved historical cards remain approved, and returned cards require explicit administrator preparation rather than automatic resubmission.

Opening administrator Time Cards runs this idempotent queue as a fallback. `admin/timeclock-period-close.php` provides the same operation for a hosting cron task. It refuses HTTP execution before loading the application, and resolves the live application's bootstrap, config, and private store. It prints only a count and success/failure marker, never account names, hours, reasons, or private records.

## Hosting schedule contract

The source and installer do not activate a schedule or send a payroll message. After live installation, a reviewed cPanel cron should run the **live** script (not a repository copy), for example every 15 minutes:

```text
/opt/alt/php82/usr/bin/php -n /home/bobsome1/public_html/kcmc-connect/admin/timeclock-period-close.php
```

The CLI environment must resolve the same `KCMC_PRIVATE_DATA_DIR` as the web SAPI. This is an environment override in bootstrap, so a web-only Apache SetEnv value must be passed explicitly to cron when present. A host acceptance check must verify the mapping before enabling the task. The app computes Chicago cutoff dates itself; the schedule does not need a fixed UTC cutoff hour or a daylight-saving edit. Configure output handling in a private location and verify an actual cron receipt before claiming scheduled execution.

The resulting cards are prepared in the private administrator queue. This is not evidence of delivery to Mike Cahill. His approved recipient/account, delivery channel, and payroll-provider integration remain separate configuration decisions. This change stores no banking details, sends no email, submits no payroll, and implements no advance disbursement.

## Validation

`tests/timeclock-employee-workflow-contract.php` runs 35 real PHP service assertions on temporary synthetic private data. It covers early submitted/approved cards, optional notes, open breaks, duplicate rejection, correction ownership/reasons/persistence, designated-owner self-review, ordinary/inactive/member refusal, no approval of open shifts, added totals, exact Chicago cutoff and daylight-saving transition, overnight completion, corrected-total retry, historical approval/return preservation, and year rollover.

`tests/timeclock-route-workflow-contract.py` executes seven real protected-route scenarios using synthetic credential-bound sessions and isolated private stores. It checks visible controls and actual route mutations, forged actor IDs, forbidden employee submissions, bad CSRF, owner self-approval attribution, unauthorized administrator routes, adjustment eligibility, and shared live-store use by the admin fallback and CLI runner. Existing time-clock service and UI checks remain in place with the employee-certification assertion updated to the user’s new admin-only preparation rule.
