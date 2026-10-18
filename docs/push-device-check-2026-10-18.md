# Notification display and delivery — October 18, 2026

The previous report that a broadcast test failed did not identify its cause.
Release health confirms local configuration and a stored subscription count;
neither proves that the current browser is subscribed or that Windows displayed
a notification. A current production self-test result and physical observation
remain necessary.

This change repairs three concrete client behaviors:

- Notification settings explicitly register KCMC's worker and app scope, rather
  than reusing a possibly unrelated parent-site worker. A matching active script
  is required before notification work proceeds. One registration promise is
  shared within the page, with failed setup available for retry.
- Disable reports a retry when the browser refuses to unsubscribe. It no longer
  reports that the device is off after an unsuccessful browser operation.
- Incoming updates keep their existing stable tag and request a fresh alert when
  replacing a previous notification. Repeated tests can alert without stacking
  old KCMC cards. Windows and browser settings still control actual display.

The member Notifications page adds **Test notification display** in a collapsed
help section. This explicit local test uses only an already granted permission,
does not request permission, does not subscribe or post to the subscription API,
and does not send a push request. It requests a generic notification through the
KCMC worker and reports a request, not verified receipt. It uses a separate tag
from real KCMC updates. Notification settings and the administrator guide include
Windows notification/banner and Do not disturb checks. The administrator guide
links directly to the existing device settings.

The service worker cache name and notification-client version change so browsers
can load the repair. Public cache eligibility, private-route exclusions, core
assets, church photos and all other worker behavior are preserved. Server
transport, VAPID key material, roles, confirmation/CSRF checks, send limits,
rate guard and private records are unchanged.

## Validation

`node tests/push-client-runtime.cjs` executes the actual client with synthetic
browser objects. It covers the existing activation and key-reconnection cases,
explicit app scope when a parent worker exists, replacement of a different active
script, unsuccessful browser unsubscribe, default/denied permission, a local
display request without API/permission calls, repeated local display requests,
root and nested hosting, and display rejection. It also executes the actual
worker: two payloadless pushes request fresh alerts with one tag; malformed or
private notification targets fall back to public home; bounded public content
and click focus/open behavior are preserved. These tests make no network sends.

The existing subscription, delivery, route and cache-privacy contracts remain
applicable. Browser acceptance uses synthetic accounts and stores, not production
messages or device endpoints. Source tests do not establish production delivery.

## Production acceptance

1. Open **Notifications** on the intended Windows/Edge device, enable
   notifications, expand **Check notification display**, and choose
   **Test notification display**. Observe the notification. If it does not appear,
   inspect Edge site permission, Windows notification/banner settings and
   Do not disturb before changing server configuration.
2. Open **Broadcast updates** as the owner. Check the count for the signed-in
   account. Put KCMC in the background and send **Test my device** from another
   window or device. Record only the safe aggregate result text.
3. Confirm physical receipt and select the notification to open KCMC. If the
   provider rejects the request, follow the displayed failure category. Do not
   replace keys or broadcast to everyone just to diagnose a self-test.
4. Disable notifications on the device, confirm success, reload the sender and
   verify that its account device count decreases.

Keep device delivery unverified until those physical steps succeed.
