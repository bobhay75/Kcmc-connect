# Push failure repair — October 15, 2026

The reported production test failed, but the previous result showed only a failed
count. That does not establish whether its cause was server setup, device
registration, an obsolete subscription, provider rejection or connectivity.

This repair addresses three reproducible source defects:

- A newly registered service worker could be passed to PushManager before it had
  activated. The client now waits for activation and reports a bounded setup
  error if installation fails or takes too long.
- Enable reused a browser subscription even when its exposed application-server
  key differed from the configured public VAPID key. After an explicit Enable
  click, the client now revokes that old registration and subscribes with the
  current public key. It never creates or replaces server keys. Browsers that do
  not expose the subscription key retain their existing path.
- An all-failed send displayed a green success notice. Zero accepted requests now
  display an error, partial failures display a warning, and the owner sees fixed
  aggregate failure messages such as HTTP 403, rate limiting or transport failure.
  A provider acceptance is explicitly distinguished from device receipt.

Setup guidance reports missing/invalid components without rendering public or
private keys, key-file paths, contact values, endpoints, JWTs, response bodies or
raw transport errors. The owner-only sender gate, CSRF/confirmation requirements,
30-second guard, five-device self-test bound, 200-device broadcast bound,
payloadless requests and expired-subscription handling are unchanged. No service
worker or homepage files change. Member Notifications retains device preferences;
administrative sending belongs in the separate administration area.

## Validation

`node tests/push-client-runtime.cjs` executes the actual client with synthetic
browser objects. It covers first-visit activation, explicit old-key reconnection,
failed reconnection, matching-key registration, denied permission, server save
failure and disabling notifications.

`python3 tests/push-diagnostics-routes.py` executes the actual PHP route against
temporary synthetic accounts, sessions and stores. Its only runtime substitution
is adding the sender's existing optional transport callback in a temporary copy.
The callback returns fixed provider statuses; it never calls the network. Ten
cases cover zero/partial/successful handoff reporting, safe failure messages,
missing/mismatched keys, no subscriptions, self-account scoping, expired endpoint
cleanup and authorization/CSRF denial. All source and configuration values used
by these tests are synthetic and removed afterwards. Existing push contracts also
pass. The delivery contract now uses a literal public IPv4 fixture with its
synthetic transport, avoiding an unnecessary DNS lookup.

These tests establish code behavior; they do not establish production outbound
HTTPS, actual hosting configuration or notification delivery on a physical device.

## Narrow production diagnosis

After installation, open Push Updates as the existing owner and report only the
setup messages, active/signed-in subscription counts and the safe result text.
Do not paste configuration values or subscription records. Missing setup must be
resolved using the existing matching VAPID pair; do not regenerate keys merely
because a send failed. For an authentication rejection, verify that pair and
explicitly re-enable the affected device. For a transport error, inspect the
hosting PHP cURL, outbound HTTPS and certificate trust configuration.

When setup is ready and the signed-in account has a subscribed device, use
**Test my device** rather than a church-wide broadcast. Production acceptance
still requires observing notification receipt while the app is in the background,
tapping it to open KCMC, and then disabling notifications and confirming removal.
Keep issue #20 open until that sequence succeeds.
