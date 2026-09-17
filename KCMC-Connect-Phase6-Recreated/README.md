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
- Authenticated Sermon Assistant request, signed-import and pastor-review workflow
- JSON-backed private storage, audit events, CSRF protection and login throttling

## Newsletter publishing rule

Never publish or commit photographs/scans of complete newsletter pages. Rebuild newsletter information as accessible app text and event records. KCMC-approved individual ministry photos from inside a newsletter may be published separately under `assets/visuals/`; the printed page itself may not be.

## Roles

| Role | Prayer access | Public publishing | Sermon Assistant | Member access |
|---|---|---|---|---|
| Member | Submit; view pastor-approved member wall | No | No | No |
| Prayer team | Member access plus confidential inbox | No | No | No |
| Pastor administrator | All prayer access and approvals | Yes | Prepare, import and decide | Yes |
| Recovery administrator | None | Yes | Prepare and import; cannot decide | Yes |

Tony Blevins and Barry Smith must each receive a separate one-time invitation, issued from **Member access** by the recovery administrator, and be assigned **Pastor administrator**. Each invitation is bound to that pastor's verified email address; do not share invitation links or passwords. The retired `/member/first-login.php` route cannot create or claim an account.

## Sermon Assistant trust boundary

KCMC Connect is the authenticated control plane; it does not run Python or any shell command from a web request. The private builder runs separately with the approved archive and Front Porch template. Production must set `KCMC_PRIVATE_DATA_DIR` to a directory outside `public_html`, such as `/home/bobsome1/kcmc-private`, so request records, decks, manifests, signatures and decision history are never web-addressable.

Set `KCMC_SERMON_IMPORT_KEY` to a high-entropy secret of at least 32 characters on KCMC Connect and provide the exact same secret only to the trusted private builder. Never put that key in Git, request JSON, an uploaded file, email or a browser. If the key is absent or too short, signed-package import stays unavailable.

The workflow is deliberately manual:

1. A pastor or recovery administrator creates an ordered Front Porch request and downloads its exact JSON.
2. The trusted private builder reads that request and produces the editable deck, `approval.json` and HMAC-signed `kcmc-import.json`.
3. A pastor or recovery administrator uploads all three files. KCMC Connect verifies the job binding, hashes, signature, readiness and QA before storing the files privately.
4. A pastor administrator downloads and visually reviews the exact stored deck, confirms its displayed SHA-256, and re-enters their current password to approve it or request changes.

Only a signed-in `pastor_admin` can make the authoritative decision. A recovery administrator can prepare requests and import signed results, but cannot approve or request changes. Approval records the authenticated pastor, server time and exact deck hash; it never publishes or distributes the deck automatically. The builder's offline `approval.html`, when present, is not an authenticated approval and is not imported.

## Runtime

- Apache with PHP 8.1 or newer
- HTTPS
- Writable `data/` and `backups/`, plus a private `KCMC_PRIVATE_DATA_DIR` outside `public_html`
- A separately operated private Python builder for Sermon Assistant builds
- No database, Node server or paid plugin is required

See `DEPLOY.md` for the production setup and rollout checklist.
