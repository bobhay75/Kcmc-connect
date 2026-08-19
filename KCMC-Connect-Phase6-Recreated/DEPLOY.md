# KCMC Connect Phase 6 — cPanel Deployment

1. Back up the current KCMC production document root before replacing anything.
2. Upload the **contents** of this folder to the KCMC subdomain/document root.
3. In cPanel, select PHP 8.1+ for the site.
4. Confirm HTTPS/SSL is active.
5. Visit `/admin/setup.php` and use the private setup key from `SETUP-CREDENTIALS.txt` to create the owner password.
6. Delete your local copy of `SETUP-CREDENTIALS.txt` after setup if you do not need it; the web server blocks direct access to it.
7. Visit `/admin/`, publish a small test announcement, and confirm it appears on the homepage.
8. Check `/bulletin`, `/church-news`, `/events`, `/care`, and `/connect` on phone and desktop.
9. Keep the ZIP and Git bundle as recovery masters.

## Server requirements
- Apache/cPanel with `.htaccess` support
- PHP 8.1 or newer
- Writable `data/` and `backups/` directories for the PHP process (normally 755/775 depending on host)

No MySQL, Node.js, Wix, WordPress, plugin, or paid CMS is required.
