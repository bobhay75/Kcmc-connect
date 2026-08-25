# KCMC Connect — cPanel Deployment

The repository deploys to `/home/bobsome1/public_html/kcmc-connect/` through `.cpanel.yml`.

## What deployment preserves

The deployment intentionally does not overwrite:

- `config.php` — private owner credentials stored only on the server
- `data/content.json` — live Publishing Desk content
- `backups/` — automatic content backups

A seed `data/content.json` is copied only when the live file does not exist. The retired `SETUP-CREDENTIALS.txt` file is removed from production during deployment.

## First-time owner setup

Use one of these private server-side methods; never commit credentials to GitHub:

1. Set a long random `KCMC_SETUP_KEY` environment variable in cPanel, visit `/kcmc-connect/admin/setup.php`, create the owner password, then remove the environment variable.
2. Copy `config.example.php` to live `config.php` and place a PHP `password_hash()` value in `admin_password_hash`.

Without a server-only setup key or password hash, public pages continue to work and owner setup remains safely disabled.

## Live checks

1. Confirm the homepage, `bulletin.php`, and all six in-app navigation views.
2. Confirm Chrome DevTools shows an active service worker and the app is installable on Android.
3. Confirm `/kcmc-connect/admin/setup.php` does not show a setup form unless the private environment key is present.
4. After owner login is configured, publish a small test change and verify it survives the next deployment.
5. Confirm PHP 8.1+, HTTPS, and writable `data/` and `backups/` directories.

No MySQL, Node.js, Wix, WordPress, plugin, or paid CMS is required.
