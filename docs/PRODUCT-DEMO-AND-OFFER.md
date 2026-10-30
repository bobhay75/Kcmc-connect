# KCMC Connect — Product Demonstration and Commercial Offer (Draft)

**Status:** Internal draft, not an offer or transfer of ownership.

## Demonstration sequence (10–15 minutes)
1. Open the public homepage on a phone and desktop; show church identity, contact information and service links.
2. Show the bulletin, announcements, upcoming events, and event details.
3. Sign in using a synthetic staging administrator account. Demonstrate updating an announcement and bulletin, creating an event, and signing out.
4. Explain role-restricted editing, CSRF protections, backups, and the separation of private data.
5. Show that Publisher, payroll, time clock, team workspace, member functions, and push notifications are **not** included.
6. Present options for installation, support, and ongoing updates.

## Commercial terms to decide before presenting
- License to use vs. assignment of intellectual property; do not assume ownership is resolved without reviewing agreements.
- One-time license/installation fee, optional monthly maintenance, and any separate hosting fees.
- Number of church sites, permitted administrators, source-code access, modifications, and future upgrades.
- Acceptance criteria, support period, warranty limitations, and payment schedule.
- Data controller, credential custody, backups, restoration responsibilities, and termination/transition procedures.

## Sale-readiness gates
- Final release package passes isolated CI checks on its exact commit.
- Separate Apache staging test verifies data and backup URL denial.
- Administrator authentication, expired sessions, and backup restore are exercised in staging.
- Church approves branding and factual content before any live release.
- Written license and intellectual-property terms are agreed before source-code transfer.

KCMC receives the first opportunity to evaluate the completed application. Development-hour records remain private and are not part of the commercial package.
