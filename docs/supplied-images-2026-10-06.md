# Supplied KCMC images — October 6, 2026

Base: `89f8904e8ce3d7a09782debe770bb45e6f045c7c`. All nine original uploads are preserved byte for byte. The JSON inventory records dimensions, byte counts, SHA-256 hashes and useful alt text.

Tony clarified during implementation that all bridge photos and bridge artwork should participate in the rotation. That supersedes the initial bridge exclusion. The rotation mixes church and family photos with all three supplied bridge artworks; the existing single image plane, seven-minute timer, reduced-motion controls and lack of added visible photo subtitles remain. The inset logo already embedded in the supplied bridge composite is preserved. No second image is added inside the hero service card.

| Original upload | Classification | Contents and placement |
|---|---|---|
| kcmc4.jpg | hero-suitable | Congregation gathering: Hero and Publisher. 2048 × 1105. |
| kcmc6.jpg | hero-suitable | Outdoor family event: Hero, gallery and Publisher. 2048 × 1536. |
| kcmc7.jpg | hero-suitable | Bridge and cross logo: Hero and Publisher (bridge artwork approved by Tony). 1156 × 1156. |
| kcmc8.jpg | kids/family/gallery | Kids safari activity: Gallery and Publisher. 2048 × 1536. |
| kcmc9.jpg | kids/family/gallery | Kids game room: Gallery and Publisher. 2048 × 1289. |
| kcmc kids.jpg | kids/family/gallery | Summer kids and family group: Family welcome and Publisher. 1440 × 1080. |
| kcmc logo3.jpg | publication/branding-only | Church photo wordmark: Publisher only. 1181 × 574. |
| kcmc logo.png | hero-suitable | Bridge photo wordmark: Hero and Publisher (bridge artwork approved by Tony). 2048 × 706. |
| kcmc bridge 2.png | hero-suitable | Bridge photo with inset logo: Hero and Publisher (bridge artwork approved by Tony). 2048 × 1144. |

All nine are built-in Publication Designer assets and are accepted by the shared-project image allowlist. They can be reused across devices without creating private uploaded-media records. Bridge artwork uses `object-fit: contain` in the hero to retain its lettering. The church exterior wordmark remains publication/branding-only because of its embedded lettering.

The family welcome now uses the supplied summer group photograph instead of an external image host. The three-image gallery shows the outdoor event, safari activity and game room with uncropped proportions and no captions. The service-worker cache version is refreshed and the eight public supplied assets are available offline. Original PNG bridge artwork is retained at full quality; the two large PNGs total about 5.5 MB.

Scope excludes private records, credentials, prayers, timecards and `data/content.json`. Production deployment is not part of this PR.
