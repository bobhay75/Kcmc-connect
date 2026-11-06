# Optional upgrade delivery — KCMC Connect

**Status:** Architecture and administrator catalog implemented; purchasing and automatic installation are deliberately disabled pending verified payment/entitlement infrastructure and host acceptance.

## Core contract
Core runs on its own. The administrator-only catalog lists Publication Designer, Member Portal, Timeclock & Payroll, Push Notifications, Team Workspace, and AI Assistants. Their implementation, configuration, secrets, private data, and direct routes are not shipped in the Core build. Catalog descriptions are informational and are not assertions of availability or fitness for a particular buyer.

## Upgrade transaction design
1. The authorized owner controls module offerings and commercial terms outside the app. The installed customer may request an upgrade; no checkout, invoice, or payment is created merely by viewing the catalog.
2. When a supported payment processor is chosen, validate a **server-to-server signed webhook** (not a browser redirect or screenshots), verify merchant/account, amount/currency, product/module, customer installation ID, payment finality, and replay protection. Record a nonsecret idempotency key in private storage.
3. The publisher issues a short-lived, signed entitlement bound to the recipient installation, module ID, version and expiry. Never place entitlement signing keys or full premium source in Core.
4. Installer authenticates the local administrator, checks license and package signature/checksum, Core/API compatibility and available disk/runtime, and verifies a fresh protected backup before downloading the module from the owner-controlled release channel over HTTPS.
5. Install into a versioned nonpublic staging directory, run syntax/config/privacy/auth tests and any data migration on a copy. Explicit confirmation is required before activating a new module. Server must reject public access to unauthorized routes regardless of menu visibility.
6. Promote through a reversible file-level plan, run health checks and rollback on failure. Keep audit metadata (not payment card details) privately. Support revocation, renewal, refunds, and reinstall without double-installing.

## Required additional engineering
- Separate signed distributable for **each** upgrade, with pinned hashes, dependencies, migrations and rollback hooks.
- Owner-controlled release service and entitlement authority; payment processor and signed-webhook adapter.
- Secure authenticated installer and backup/rollback verification on the supported hosting environment.
- Privacy, consent and regulatory review for member data and payroll where applicable.
- End-to-end purchase, replay, invalid-signature, upgrade, rollback, recovery and revoked-entitlement tests.

## Release rule
Do not copy all optional modules onto the customer's server, disable only menu links, or auto-install after an unverified payment notification. Never bundle payment credentials or private developer records in distributed archives. Until the above gates pass, the catalog must remain informational and no module is installed automatically.

## Separate decisions
Installation and technical completeness do not depend on pricing or a particular customer. Licensing/ownership rights, payment terms and support are determined separately by the owner.
