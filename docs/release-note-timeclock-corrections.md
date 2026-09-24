# Release note — employee time correction requests

This draft adds an employee-owned correction request path to the existing KCMC Time Clock. Employees can request correction of their own completed shifts and see request status. Pastor/Recovery administrators can apply corrected punch times, unpaid break minutes, category, and work description, or reject the request with a reason.

Applied corrections preserve before/after evidence privately and visibly mark corrected shifts/periods. Existing supervisor adjustment history, employee adjustment markers, approved-period exports, print output, and privacy-safe audit boundaries remain in place.

No deployment is authorized by this branch. Merge only after CI is green and the branch is reviewed against current main. After an approved deployment, run production smoke and one controlled employee/admin correction acceptance test.
