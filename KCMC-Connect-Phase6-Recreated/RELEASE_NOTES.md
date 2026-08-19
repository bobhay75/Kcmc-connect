# KCMC Connect v1.2.0 — Publishing Pass

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
