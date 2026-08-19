# KCMC Connect — Final Launch Package

This package is a self-contained, installable Progressive Web App for Kimberling City Methodist Church.

## Included
- Mobile-first KCMC Connect home experience
- Watch / live-video pathway
- August 2026 Church News highlights plus all five original newsletter pages
- Current August events from the newsletter
- Serve / community-support pathways
- Partner Hub announcements
- Official online giving link
- Plan-a-Visit and directions links
- Installable PWA manifest + offline service worker
- No analytics or advertising trackers by default

## Deploy on cPanel / Namecheap
1. Create a subdomain or folder, such as `connect.yourchurchdomain.org`.
2. Upload **the contents of this folder** to that document root.
3. Make sure HTTPS is enabled.
4. Open the site once online; supported browsers can then install it as an app.

No build command, Node server, database, or paid plugin is required for this release.

## Content source policy
Public worship times, address, office hours, giving, visit and livestream paths should follow the church's current public website. Newsletter-specific news comes from the August 2026 Issue 15 pages supplied for this build.

## Before broad public rollout
- Leadership approves the wording and featured Facebook service.
- Replace dated August events after they pass.
- Pilot with 15–25 real members and collect concrete navigation/content feedback.
- If KCMC wants staff publishing from multiple devices, add real authenticated CMS storage rather than relying on browser-local editing.


### Visual assets
The v1.1.1 build includes KCMC/Ozarks visual assets under `assets/visuals/`, including the approved vision/lake graphic and ministry imagery derived from the August newsletter.

## v1.2.0 publishing architecture
The visitor, RSVP, serve, prayer and group forms are deliberately implemented without an unapproved third-party data processor. On the static build they validate and compose an email to the KCMC office. The `sendFormByEmail()` function in `app.js` is the single integration point to replace when KCMC approves a church-management-system or serverless form endpoint.
