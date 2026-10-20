# KCMC branding and current content — October 20, 2026

## Public appearance

Keep the approved `#0d2235` navy, existing gold left-facing fish, full original
church photograph on phones, natural sky, hero actions, service strip, and three
welcome links. Add the requested “Called to love and serve.” beneath those links.
No image pixels, architecture, sky, or people were generated or modified.

The supplied October 18 worship photographs form a “Life at KCMC” section below
that approved opening. Three landscape photographs are featured; seven more open
through a native accessible disclosure. The existing kids/family photographs
remain. Each photograph has descriptive alternative text and no visible caption.
The new section has an explicit CSS display rule because the older fish-only
homepage stylesheet hides other sections by default. Browser acceptance checks
real visibility and expansion, not merely successful image downloads.

Original supplied files are preserved byte-for-byte under these descriptive names:

| Supplied camera file | Public asset |
|---|---|
| IMG_20261018_102336442_HDR.jpg | kcmc-traditional-sanctuary-20261018.jpg |
| IMG_20261018_101931201(1).jpg | kcmc-traditional-worship-20261018.jpg |
| IMG_20261018_102011546(1).jpg | kcmc-traditional-front-20261018.jpg |
| IMG_20261018_102511280(1).jpg | kcmc-traditional-message-20261018.jpg |
| IMG_20261018_113209309(1).jpg | kcmc-contemporary-gathering-20261018.jpg |
| IMG_20261018_113217623(1).jpg | kcmc-contemporary-fellowship-20261018.jpg |
| IMG_20261018_113226222(1).jpg | kcmc-contemporary-music-20261018.jpg |
| IMG_20261018_113220909_HDR(1).jpg | kcmc-contemporary-room-20261018.jpg |
| IMG_20261018_113159790_HDR(1).jpg | kcmc-contemporary-room-portrait-20261018.jpg |
| IMG_20261018_114920982_HDR(1).jpg | kcmc-contemporary-after-service-20261018.jpg |

Exact byte counts and SHA256 values are in the separately pinned
`tests/fixtures/brand-family-20261020-reviewed.json`. The October 19 welcome
fixture and all prior source/security fixtures remain immutable. The current
brand layer projects to those historical bytes only in isolated test copies.

The service worker gets a new cache name and the new welcome stylesheet URL.
The three visible photographs are precached; the other seven are allowed in the
existing public-only cache when viewed. Existing authentication/private-page
cache restrictions are unchanged.

## Current editorial evidence

The original “Front Pew News -- Friday, October 16” email from Kimberling City
Methodist Church was read on October 20. It confirms Way Forward on October 22 at
1:30 PM, Trunk or Treat on October 31 from 4:30–6:30 PM, the October 25 bottle
return, the November 14 dinner, and the October 20–23 calendar. Its 5:17 PM Bible
study/youth/children's times are preserved as written.

`KCMC_Friends_of_Faith_October_18_2026.pptx` explicitly says “Beginning October 18,
2026” and “Sundays at 10:20 AM” in the Pairs & Spares Classroom. Its owner-review
notes reconcile the newsletter's older “Faith & Friends / 10:15 AM” with the
approved Friends of Faith title and 10:20 AM time. The class is therefore weekly,
with no inferred end date. Personal contact numbers and raw newsletter/email
contents are not included in the public package.

The repository content is a reviewed source snapshot. The live site had an
October 14 bulletin and lacked current meeting/class visibility. A release must
not overwrite live `data/content.json` with the source snapshot. The dedicated
`tools/kcmc-content-oct20` package merges only reviewed fields/records, skips
expired items, detects conflicts, and provides a private actual-byte rollback.
The old October 18 “this Sunday” signup wording is changed to office contact.

## Review bundle and deployment boundary

Run `python3 -B tools/prepare-brand-release.py --output <review-zip-path>` to build
the reproducible release ZIP. It contains exactly three public file replacements,
ten authentic added images, independent main/livecalendar preflight guards, and
the separately operated record-level content package. `public-presentation.css`
is a read-only guard: the installed livecalendar customization is retained.

The source anchor is main commit `ca0d6197b4be7339fd5937f216202a7e5fbdd13d` plus the
exact current file hashes. The bundle does not require an unpublished local
commit. No live content, private stores, backups, credentials, or ledgers belong
in this code review or release archive. Building/checking the package makes no
host changes. Production installation and post-install public checks remain a
separate authorized release operation.
