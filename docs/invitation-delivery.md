# Invitation delivery repair

This branch repairs the invitation-screen handoff. It does not send mail, create
production invitations, change roles, activate accounts, or change the public app,
service worker, stored church content, or sermon assistant.

## Operator flow

After creating a separate invitation through the existing authorized form:

1. Check the recipient name, email, role and expiration on the delivery card.
2. Check the recipient-confirmation box, then **Copy invitation email**.
3. Select **Open Gmail**, paste into the message body, verify the To address and
   the correct sending Google account, then choose Send in Gmail.

**Copy link only** remains available for a different authorized delivery channel.
**Open another email app** is the optional mailto path, not the only delivery option.
Neither link sends mail, and the card never reports that an email was delivered.

When clipboard access is denied or missing, the relevant field is selected for
manual copying and clear instructions are shown. With JavaScript off, the manual
email, recipient, subject and link remain available. Keep the card open until copied;
the existing one-time session flash behavior is unchanged on refresh/navigation.

## Boundaries

The delivery helper matches the token hash to exactly one unused, unexpired record,
then verifies the stored recipient and creator. Unknown, expired, superseded,
ambiguous or mismatched records are not rendered as usable delivery cards.
The new helper allows the owned bobsome1.com hosts plus explicit localhost test
origins; HTTP production handoff is refused. It does not rewrite stored invites.
A custom staging hostname would require an explicit reviewed allowlist change.

Recipient details come from the matched record, never the form for the next invite.
A checkbox reduces user mix-ups but is not a substitute for server authorization.
Copying uses the original card snapshot. No tokens go into local/session storage,
analytics, logs, Gmail compose URLs, or new mailto URLs. The full private message
is pasted by the authorized sender. No clipboard reads occur in application code.
The CI browser test reads back only the synthetic text it just wrote in its own
headless-browser test session to verify real clipboard behavior.

Gmail web-compose parameters are a convenience, not a supported sending API or
proof of delivery. Account selection, sign-in, browser restrictions and Google UI
changes may prevent a prefilled composer. The always-available manual Gmail route
and copyable fields are the fallback. No Google API credentials are required.

## Verification and release

Run `php tests/invitation-delivery.php` and
`node --test tests/invitation-delivery.cjs` for the focused checks.
The PHP checks also fingerprint the unchanged original POST handlers, invitation
form, role controls and account directory. Existing security workflows remain intact.

Run `python tests/invitation-delivery-browser.py` with PHP and Playwright Chromium
installed for full-app acceptance. It copies the actual app into a temporary
localhost site, creates synthetic accounts/invitations there, disables PHP mail,
blocks production/third-party browser traffic, and intercepts Gmail navigation.
It checks real Chromium clipboard behavior, keyboard flow, fallback states,
recipient binding, no sends/POSTs from delivery controls, private-store preservation,
and the one-time card lifetime. Screenshots/results contain synthetic data only.

`--components` runs only a PHP-rendered card with a minimal test stylesheet and
simulated clipboard. Local environments blocking external popups exercise the
Gmail handler and URL without navigation; full CI still requires an intercepted
Gmail request. Component results do not certify complete app styles or production.

Remaining release acceptance: owner approval, controlled cPanel deployment, then
check the authenticated invitation screen and intended Gmail/account/browser route.
Do not generate duplicate live invitations merely to test the UI; use the next
owner-approved invitation and do not send until its recipient is checked.
This patch does not certify real phone OS behavior or account activation.

## Current transport blocker

The GitHub connector blocked two attempts to upload the full browser runner with
an indeterminate safety-status error. No alternate upload path was used. The full
runner and intended workflow remain in the local review package, not this branch.
The branch workflow deliberately fails its final release gate rather than silently
skipping that check. Existing repository security/description workflows are unchanged.
Local evidence: 44 PHP assertions, 16 Node tests, 22 isolated component-browser
checks passed. Full-app/browser/real Gmail acceptance has NOT been completed for
this revision. This branch is draft-only and must not be merged or deployed yet.
