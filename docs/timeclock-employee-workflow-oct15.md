# Manual employee time clock

Employees clock in and out using KCMC server timestamps. Work notes and categories are optional. Clock Out ends a running unpaid break at the same timestamp. The employee screen shows completed hours for the current pay period, recent shifts, and correction requests with reasons. Back, Home, My account, and Time clock links remain available.

Time cards do not require submission, certification, approval, or return. Recorded shifts supply the totals directly. Old submission and approval requests are rejected before any record is written. Historical submission, approval, return, and correction evidence remains in the private store; its former status does not restrict current punching or reporting.

## Totals and corrections

Authorized payroll staff can view current and closed periods, download CSV, and print time cards from recorded entries, including periods that have no stored summary. Report bounds must match a valid America/Chicago pay period. Completed shifts contribute their recorded net minutes. An unfinished shift is identified and contributes no unfinished time; the app does not invent its clock-out time.

Employees can request a correction with a reason. Authorized administrators can apply a correction or adjust recorded duration with a reason and before/after history. The existing designated-owner exception permits the owner to correct their own entries. Other administrators retain the existing restriction on changing their own time. A historical approval does not lock an otherwise valid correction or adjustment.

## Period-end totals

The existing pay-period rule runs from the 23rd through the 22nd in America/Chicago. After a period closes, `kcmc_timeclock_close_due_periods()` prepares a neutral recorded summary, or an unfinished-shift warning when needed. It recomputes totals under the private-store lock and avoids duplicate or unchanged writes. It preserves historical approval attribution and does not change completed shifts into submitted records.

Opening administrator Time Cards runs this operation as a fallback. The existing CLI runner uses the same live store. A hosting schedule remains a separate configuration step; a runner receipt alone does not establish an active cPanel cron task.

## Payroll handoff

The configured payroll handoff already uses completed recorded hours without requiring approval. Its selected recipient, delivery channel, revision deduplication, transport claims, and live-store fingerprint checks are unchanged. Delivery to Mike Cahill requires his configured account and the chosen enabled channel. This clock does not transfer money, store bank details, or issue advances.

Smart-clock scheduling, location tracking, device-idle monitoring, and automatic punches were cancelled by the owner. Clock In and Clock Out remain manual.

## Validation

Current service, protected-route, and real-browser checks cover manual punches; periods with no stored summary and with historical submission/approval/return metadata; completed versus unfinished totals; CSV and print access without approval; rejected legacy actions without writes; authorized correction and adjustment history; private headers, CSRF and role boundaries; and the existing period-end payroll handoff.
