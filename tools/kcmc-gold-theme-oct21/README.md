# Approved gold-fish public theme

Owner requested rich blue/gold homepage and matching interior styling with no extra controls and one authentic photo per worship service. Scoped installer preserves current host PHP/data/bulletin functions, patches existing index.php/index.html hero and brand, routes existing Watch Online link to existing watch view, and adds a public-shell-only stylesheet and hero asset. Existing service photo/data pairings remain unchanged. No private/configuration files change.

Package SHA256: 00a1e295692821487a1eb71b4996a9679f0b28a160d11ed11c76c826e0347f6f

Run `python3 -I -B install.py` to check and `python3 -I -B install.py apply` to install. Uses Python 3.6 compatible APIs. Backs up existing modified files outside the webroot and restores on write failure. Tested against October 20 bulletin PHP and current rendered HTML, repeat install and missing-photo refusal. Browser rendering could not be run because the browser download failed; responsive visual acceptance remains outstanding. Existing recording links are preserved, not independently playback verified.

Generated hero source: owner-approved KCMC gold fish graphic, no invented church photography. Service photos were inspected: front porch music group, traditional sanctuary choir/congregation, contemporary gathering around tables.
