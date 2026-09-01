# KCMC Connect Release Notes

## 3.0.0 — Private member prayer and individual access

- Moved prayer submission, prayer details and the approved prayer wall behind verified member sign-in.
- Added separate email/password accounts with seven-day, one-time invitation links.
- Added member, prayer-team, pastor-administrator and recovery-administrator roles with explicit privacy boundaries.
- Added pastor approval before any request can appear on the members-only prayer wall.
- Added confidential prayer-team inbox, account enable/disable controls and individual sign-out.
- Added CSRF protection, secure session settings, login throttling, atomic private JSON storage and privacy-safe auditing.
- Prevented the recovery-administrator role from reading, submitting or moderating prayer requests.
- Changed private pages to `no-store`/`noindex` and excluded them from the service worker cache.
- Replaced the stale static sermon bulletin with live Publishing Desk content.
- Replaced the August newsletter page gallery with September Issue #16 app-native text, current events and ministry highlights.
- Removed all complete newsletter page photographs from the release and added a permanent content policy: page scans are prohibited; separately approved individual ministry photos remain allowed.
- Updated navigation, care messaging, current-content labels and Version 3 portal styling.
- Preserved private production data during cPanel deployments.

## 2.1.4 — Verified Kimberling City Bridge photography
- Replaced every site use of the inaccurate or ambiguous scenic bridge/lake artwork with the verified 1920 × 1280 Wikimedia Commons photograph of the Kimberling City Bridge carrying Highway 13 across Table Rock Lake.
- Uses the original 2024 photograph by Avalon1101, released under the CC0 1.0 Universal Public Domain Dedication.
- Corrected image descriptions, social sharing artwork and Watch-page scenery while preserving real KCMC ministry photography.
- Removed the suspect generated/lookalike scenic assets from the release.
- Versioned page assets and bumped the service-worker cache to force installed PWAs to refresh.

## 2.1.2 — Sharper, richer Table Rock hero
- Replaced the low-resolution hero with a sharper 1774 × 887 WebP scene of Table Rock Lake and the Kimberling City Bridge.
- Restored natural lake blues, forest greens and golden-hour color by removing the faded image opacity and reducing the overly heavy navy overlay.
- Added a responsive mobile crop and contrast treatment that keeps both the bridge and white interface text clear.
- Preloads the hero and bumps the service-worker cache so the new background arrives immediately after deployment.
- Retired the completed Backpack Blessing announcement and removed its promotional home-page feature while preserving the story page as an archive.

## 2.1.1 — KCMC Ichthys app icon
- Replaced the installed-app artwork with a bold KCMC wordmark and Christian Ichthys symbol.
- Added versioned manifest and Apple touch-icon URLs so Android, iPhone, iPad and desktop browsers discover the new artwork.
- Bumped the service-worker cache while retaining the existing PWA caching strategy.

## 2.1.0 — One-touch PWA installation
- Added a prominent Save to Home Screen call-to-action on the home view and a compact header action.
- Connected Android Chrome and installable desktop browsers directly to the native PWA install prompt.
- Added concise, platform-aware iPhone and iPad Safari instructions for Add to Home Screen.
- Hides install controls when KCMC Connect is already running as an installed app.
- Bumped the service-worker cache so the new interface is delivered immediately after deployment.

## 1.2.0 — Publishing Pass

## Visitor-first experience
- Added a complete in-app **I’m New / Plan a Visit** journey.
- Added verified service descriptions, directions, office contact, Launch Kids context, and accessibility contact guidance.
- Added an **I’m Coming This Sunday** form with required-field validation and church-office email handoff.

## Connection features
- Added event RSVP and downloadable `.ics` calendar actions.
- Added volunteer-interest form.
- Added private prayer/care form.
- Added Find Your People / group-interest form.
- Added optional device-local preferred service setting.

## Watch & content
- Added sermon-library structure with search/filter controls and current verified featured video.
- Preserved August 2026 newsletter pages and current dated events.

## Technical polish
- Improved meta/OG tags and Church schema.
- Added skip link, focus states, reduced-motion support and better form labeling.
- Added offline status messaging and retained installable PWA support.
- Updated cache version to v1.2.0.

## Production integration note
The current host is static. Forms validate in-app and open a fully composed message to `secretary@umckc.org`, which works without storing visitor data in an unapproved third-party service. A future approved ChMS/serverless endpoint can replace the mail handoff to add staff dashboard notifications and automatic confirmation emails.


## 1.2.1 — August Church News Data Integration
- Integrated the five newly supplied August 2026 Issue #15 newsletter photos as the source pages.
- Added the KCMC Church News visual summary and current baptism, attendance, youth, facilities, Quest Preschool, staffing and connection updates.
- Corrected office hours to Tuesday–Thursday, 8:00 AM–4:00 PM based on the supplied newsletter.
- Bumped the PWA cache to v1.2.1.
