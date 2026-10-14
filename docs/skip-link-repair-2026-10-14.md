# Skip-link repair

Activating Skip to content changed `#visit` or `#events` to `#mainContent`.
The route handler interpreted that landmark ID as Home, changed the section,
and left keyboard focus outside the content. The live public script reproduced
the defect in a local Chromium replay of its TLS-verified public HTML.

The repair changes only `app.js`: its skip-link click listener preserves the
route, focuses the existing main landmark and scrolls it below the sticky header.
Keyboard Enter uses the same native click event. Repeated pointer activation and
ordinary route/back/forward behavior remain supported. Current network-first
asset fetching refreshes the saved script after an online load; cache policy,
page markup, accounts, authored content and private records are unchanged.

Browser checks exercise the empty hash, Home, Visit and Events at 320, 390 and
1440 pixels, including focus, next Tab, header visibility and navigation state.
The previous immutable public script is a negative control. Temporary fixtures
block external requests and form submission. The source check permits only the
reviewed insertion against `b18454042ddeb19e069821ea9a238b40335c780b` and retains
all historical, editorial and three-file repair pins.

Source review and CI do not establish hosting installation or physical-device
acceptance. The prior three-file cPanel installer does not install this script.
