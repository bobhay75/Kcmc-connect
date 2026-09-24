# Time Clock correction acceptance

After an approved deployment:
1. Employee opens Time Clock and submits a correction request on one completed shift.
2. Confirm a second pending request for the same shift is blocked.
3. Administrator opens Time Cards and sees the pending request without employee contact data in general audit context.
4. Apply one correction and verify corrected punches, break minutes, category/description, net total, employee-visible status, and correction marker.
5. Confirm original and corrected values remain in private correction history.
6. Submit a second request and reject it with a reason; confirm employee sees the administrator response.
7. Verify approved CSV/print totals reflect the current corrected values.
8. Run the normal production smoke.
