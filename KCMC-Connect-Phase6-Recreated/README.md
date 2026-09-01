# KCMC Connect 3.0

KCMC Connect is the mobile-first web app for Kimberling City Methodist Church. Version 3 keeps the public church experience open while moving every prayer request and prayer detail behind verified member sign-in.

## What is included

- Public home, worship, watch, visit, events, news, serve and giving pathways
- Installable Progressive Web App with a network-first public cache
- Individual email/password member accounts created by one-time invitation
- Members-only prayer submission and pastor-approved member prayer wall
- Confidential prayer-team inbox
- Pastor prayer moderation and church-content publishing
- Separate recovery-administrator access that cannot read or submit prayer requests
- JSON-backed private storage, audit events, CSRF protection and login throttling

## Newsletter publishing rule

Never publish or commit photographs/scans of complete newsletter pages. Rebuild newsletter information as accessible app text and event records. KCMC-approved individual ministry photos from inside a newsletter may be published separately under `assets/visuals/`; the printed page itself may not be.

## Roles

| Role | Prayer access | Publishing | Member access |
|---|---|---|---|
| Member | Submit; view pastor-approved member wall | No | No |
| Prayer team | Member access plus confidential inbox | No | No |
| Pastor administrator | All prayer access and approvals | Yes | Yes |
| Recovery administrator | None | Yes | Yes |

Tony Blevins and Barry Smith should each receive their own invitation and be assigned **Pastor administrator**. Do not share passwords.

## Runtime

- Apache with PHP 8.1 or newer
- HTTPS
- Writable `data/`, `data/private/` and `backups/` directories
- No database, Node server or paid plugin is required

See `DEPLOY.md` for the production setup and rollout checklist.
