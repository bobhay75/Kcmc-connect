# KCMC Connect installed-icon repair gate

The deployed PWA manifest now exposes separate `any` and `maskable` declarations and bumps the icon cache key to `v=3.0.2`.

## Required visual verification before release

The repository's current binary `assets/icons/icon-192.png` and `icon-512.png` files must be visually verified to contain the approved KCMC fish artwork with safe padding. Do not claim the fish artwork is fixed solely from the manifest change.

If either PNG does not contain the approved fish artwork, replace both source PNGs with approved 192x192 and 512x512 exports before release.

## Phone verification

1. Deploy only after review/tests pass.
2. On the authorized Android test phone, remove the existing installed KCMC Connect PWA if the launcher retains the cached old icon.
3. Open the production KCMC Connect URL in Chrome and reinstall/add to Home screen.
4. Confirm the launcher icon visibly contains the approved fish and is not cropped by Samsung's icon mask.
5. Open the installed app and confirm standalone launch still works.

No invitation should be sent merely to test the icon.
