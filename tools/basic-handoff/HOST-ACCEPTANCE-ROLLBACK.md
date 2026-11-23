# Basic KCMC handoff — host acceptance and rollback gates

Status: **review only**. This checklist does not authorize installation, merging, production changes, or contact with the church.

## Read-only inventory (authorized hosting administrator only)

Before collecting evidence, confirm access authorization. Record the document root, PHP runtime and handler, Apache configuration and inherited .htaccess rules, aliases/rewrite rules, all PHP entry points including host-only files, symlinks, service-worker scope, writable directories, and scheduled tasks across relevant hosting accounts. Record **paths and hashes only** for private/configuration files; never commit secrets, personal records, backup contents, or the developer's private ledger.

Compare production files with the pinned recovered snapshot and candidate using `preflight.py`. Investigate every mismatch. Do not assume that repository main matches production.

## Release-blocking assertions

- Direct GET/POST to each excluded legacy endpoint returns 404 (or another explicitly approved denial) both anonymously and as an administrator, including endpoints that do **not** load bootstrap.php. Verify Apache aliases, rewrites and alternate PHP routes.
- Anonymous users cannot reach administration, connection submissions, RSVPs or backups; administrators cannot access excluded payroll, time clock, Publisher, member or team functions.
- Administrator sign-in, session expiration, CSRF, sign-out, authorized account recovery, event creation, edits, conflict rejection, private inboxes and backups pass on the exact staged host configuration.
- Current bulletin, announcements, service links, events, artwork, and church-approved content remain intact. Repository fixture content must not overwrite live data.
- Visitor mail is verified using a specifically authorized test recipient; no unsolicited messages.
- Phone and desktop browser checks include navigation, cache/service-worker upgrade, previously installed push subscriptions, and logout behavior.

Legacy workflows for excluded functions may be marked *not applicable* only after reviewing the failing assertion. Security, session, privacy and deployment-divergence failures remain unresolved until reproduced or explained against this reduced contract.

## HTTPS origin precondition

The Core `.htaccess` redirects HTTP requests for `bobsome1.com` and `www.bobsome1.com` to the same path and query at `https://bobsome1.com`. Localhost and other development hosts are outside that rule. The redirect uses Apache's native `HTTPS` connection state and never trusts a client-supplied `X-Forwarded-Proto` header.

**Before installing this override, verify that the origin handles TLS for HTTPS requests.** Direct TLS and a proxy that connects to the origin over TLS satisfy this precondition. A proxy that terminates TLS and sends HTTP to the origin does not: the native check would cause a redirect loop. For an HTTP backend, configure the redirect at the trusted ingress or review an origin rule against verified proxy addresses and headers that the proxy always overwrites. Do not add a blanket forwarded-header bypass.

The local Apache regression tests the built rules with real HTTP/TLS and fixture files. Acceptance on the actual Namecheap Apache/LiteSpeed configuration is still pending and must establish all of the following:

- HTTP home, administrator sign-in and public routes redirect to HTTPS before serving their page; the same HTTPS requests complete without a loop.
- Both the production and isolated staging directory prefixes, encoded paths and query strings survive the redirect. Spoofed forwarded headers cannot bypass it.
- Inherited rules, aliases, certificate validation and any trusted proxy configuration are compatible with the Core override.
- Private files, data and backup paths remain denied; the two legacy Wikimedia image redirects retain the intended filename and resolve successfully.

References: [Apache HTTPS and trusted proxy guidance](https://httpd.apache.org/docs/2.4/rewrite/remapping.html#https), [Namecheap cPanel HTTPS redirects](https://www.namecheap.com/support/knowledgebase/article.aspx/9770/38/how-to-use-htaccess-to-redirect-to-https-in-cpanel/).

## Backup prerequisite

With hosting authorization, create a timestamped, access-restricted, **actual-byte** backup outside public_html of the current application code, .htaccess and inherited server rules, configuration, editorial JSON, and private stores. Record hashes, permissions, ownership, PHP/runtime versions and an inventory manifest in a protected location. Keep the developer's private work ledger separate and out of the church handoff. Do not upload secrets or personal records to GitHub. Validate backup integrity and rehearse restore in a separate staging tree.

## Installation design (not an executable installer)

Stage candidate code into a new, isolated directory. Compare against current production, prepare a per-file allowlist of intended changes, and explicitly preserve live configuration, content, user accounts, private stores and backups. Do **not** use broad rsync --delete, replace the whole document root, or remove old files without a separately reviewed server-side deny rule and verified inventory. Document writable paths and permissions. Require explicit approval before changing production.

## Rollback rehearsal

1. Stop staged testing and record the failing check and any content edits since backup.
2. Restore the original code and web-server rules from the verified backup in staging; restore configuration and permissions.
3. Reconcile any newer content/private submissions before restoring data to avoid destroying post-backup changes.
4. Clear or version affected caches and service workers; verify public pages, login, submissions, and protected-route behavior.
5. Record restoration hashes and a signed acceptance checklist. Production rollback requires separate authorization.

## Sign-off

- [ ] Full host inventory and extra routes reviewed
- [ ] Server-level exclusions validated
- [ ] Origin TLS/proxy topology verified; HTTPS redirects and Apache/LiteSpeed rules accepted on staging
- [ ] Account recovery and authorized mail tested
- [ ] Exact staged PHP/HTTP/device tests passed
- [ ] Actual-byte backup and isolated restore rehearsal passed
- [ ] Church content and private developer ledger protected
- [ ] Authorized deployment and rollback owner identified
- [ ] User approved deployment explicitly

PR #169 was merged on November 16, 2026 (UTC). Its merge does not establish host
acceptance. Record current results for the exact candidate before installation;
older completed checks are historical evidence, not evidence of current host state.
Keep deployment blocked until these gates pass and the authorized deployment owner
approves the verified release.
