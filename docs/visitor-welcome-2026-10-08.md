# Brighter welcome, visitor receipt and member invitations

Status: proposed source change. Not deployed; real email disabled pending approval.
Baseline: `b6093050dafe9a8d5b2ad4d958fdae742bc06624`.

## Visitor experience

The hero now uses light cream surfaces, dark readable text and unobscured photography. The empty `kcmc-stage-2014.webp` frame is removed from the hero, contemporary fallback and offline precache; its archived original is not deleted. Eight other hero frames remain, exterior first. Seven-minute rotation, manual controls, reduced-motion behavior and no visible source captions remain. The hero's primary action is Plan your visit.

After a newly saved Plan Your Visit submission, the server attempts a one-time welcome email immediately when explicitly enabled. It confirms the selected service, directions, events, groups, serving and current bulletin links, with Launch Kids at 10:30 and the published office reply address. The confirmation screen also shows next steps when email is unavailable. Staff see delivery status in the existing protected Connections inbox.

Invite someone this Sunday lets the visitor choose a recipient through their device. The invitation points directly to the visit page and excludes query strings and tokens. It does not harvest contacts, send automatically, create an account or enroll anyone in a mailing list.

## Activation and delivery safeguards

Visitor email is independently disabled by default. Existing staff invitation enablement does not activate it. Under a separately approved host change, add these keys to the preserved server-only config.php without replacing other settings:

```php
'visitor_welcome_mail_enabled' => true,
'visitor_welcome_from' => 'AUTHORIZED-LOCAL-SENDER@YOUR-DOMAIN',
'visitor_welcome_from_name' => 'KCMC Connect',
'visitor_welcome_base_url' => 'https://bobsome1.com/kcmc-connect/',
```

Matching environment names are KCMC_VISITOR_WELCOME_MAIL_ENABLED, KCMC_VISITOR_WELCOME_FROM, KCMC_VISITOR_WELCOME_FROM_NAME and KCMC_VISITOR_WELCOME_BASE_URL. Only value 1 activates the environment flag. An existing validated invitation_from can provide the sender fallback, but the separate visitor enable flag is required. Do not spoof a domain as From unless this host is authorized to send for it. Reply-To uses the published church office email.

PHP mail() returning true establishes acceptance for delivery, not inbox receipt. The UI and staff labels make that distinction. Primary documentation: https://www.php.net/manual/en/function.mail.php . Before activation, verify the authorized sender and SPF/DKIM, obtain approval for an exact test recipient and body, and check the received email and Reply-To. Tests send no real email.

Failed or disabled email never discards a saved visit. Duplicate requests return before the mail logic. A private atomic claim and a per-recipient 24-hour attempt limit prevent repeated receipts. Interrupted handoffs require human verification before resending. There is no automatic retry or marketing sequence. Existing validation, rate limit, same-site restrictions and private no-store headers remain intact.

Delivery metadata is stored in KCMC_PRIVATE_DATA/visitor-welcome-delivery.json: submission IDs, timestamps, statuses and recipient hashes, not names, addresses or visitor notes. Entries older than 30 days are pruned when a later welcome claim is processed; there is no scheduled deletion job. The existing visitor record and personal staff follow-up workflow remain separate.

## Verification

Run python3 tests/installed-reconciliation-source.py, php tests/visitor-welcome-contract.php, php tests/connection-intake-contract.php, bash tests/security-contract.sh, node tests/public-photo-offline-source.cjs, python3 tests/visitor-welcome-browser.py, python3 tests/public-photo-offline-browser.py and python3 tests/visible-photos-review.py.

Browser acceptance uses a temporary app copy, synthetic .invalid contacts and a local sendmail capture, exercising actual PHP HTTP submission, accepted handoff, duplicate, transport failure, disabled sending and unchanged public content. It checks desktop, 390px and 320px layouts. Offline regression retains the pinned historical nine-frame failure and checks the new eight-frame gallery, including a missing frame, all controls and private/token cache exclusions.

The exact replacement fixture and new mail module are pinned by SHA-256. Prior runtime provenance and Publisher checks remain. No data/content.json, credentials, authentication, private records, timecards, existing mail transport or .cpanel.yml changes are included. The temporary candidate materializer and its write-enabled workflow have been removed; ongoing review has contents: read only.

## Outreach practice proposed for church approval

Start with one specific invitation: a Sunday service or an already published community event. Encourage members to say, Come sit with me; I will meet you there. Give each new private request a named welcome-team owner and propose personal follow-up within one business day, subject to staffing approval. Ask separately before sending ongoing updates. Review aggregate visit requests, completed follow-ups and voluntarily confirmed attendance; never publish individual visitor information or add tracking by default.

## Release hold and rollback

Merge, deployment, mail activation and a real inbox smoke test each require approval. Do not use production visitor submissions as test fixtures. Deploy only the exact reviewed commit through the existing guarded host process. Roll back source through that same process and disable visitor_welcome_mail_enabled, preserving the delivery ledger and visitor records. The public service-worker cache version changes so installed clients can refresh.
