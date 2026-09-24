# KCMC Time Clock Corrections

Employee correction requests remain private inside the existing Time Clock store. Employees can request a correction only for one of their own completed shifts. Pastor and Recovery administrators can review a pending request, apply corrected clock-in/clock-out, unpaid-break minutes, category, and work description, or reject the request with a reason.

Applied corrections preserve the original and corrected values in private correction history. Approved/submitted periods receive a correction marker. Existing supervisor adjustment history remains intact and separate. General audit events record only action/count metadata and do not copy correction reasons, work descriptions, or employee contact information.

Release gate: CI must pass before merge. After merge, production deployment remains owner-controlled and should be followed by the standard production smoke plus one employee/admin acceptance test of request, apply/reject, totals, and print/CSV output.
