# KCMC Connect — Release Candidate Checklist

Status: **review candidate only**. This document does not authorize deployment, transfer, or sale.

## Product scope
Public church information, bulletin, service links, announcements, events, and basic administrator editing. Excluded: Publisher, member workspace, time clock, payroll, team collaboration, and push notifications.

## Build and local acceptance
1. Use the PR branch in an isolated checkout. Do not pull into the live cPanel working tree.
2. Run `python3 tests/basic-handoff-http.py`.
3. Run `bash tests/security-contract.sh`.
4. Build into a new empty destination with `python3 tools/basic-handoff/build.py /tmp/kcmc-release-candidate`.
5. Confirm `config.php`, `data/private/`, private ledgers, and excluded routes are absent.
6. Verify the GitHub Basic church handoff, Security contract, and Hero preview checks on the exact release commit.

## Staging-only host acceptance (requires owner's approval)
Use a separate staging document root and independent synthetic credentials/data. Never point staging at production's private storage.
- Verify HTTPS and all public pages, bulletin, links, event display and mobile layout.
- Verify administrator sign-in, invalid-password denial, CSRF rejection, editing, backup creation, logout and session expiry.
- On **Apache**, GET requests for `/data/content.json`, `/data/private/users.json`, and `/backups/<synthetic-backup-name>.json` must return 403 or 404. PHP's built-in test server does **not** enforce .htaccess.
- Verify the original content snapshot can be restored into an isolated staging copy, then validate the restored content.
- Confirm excluded routes return 404 and no secrets, ledgers, or private data appear in the deliverable.
- Confirm the production cPanel deployment configuration remains disabled and production was not changed.

## Release decision
Do not label production-ready until staging Apache access controls, backup restoration, and administrator session behavior have been observed. Keep PR #169 draft; no merge or deployment without explicit approval.

## Sales preparation
Demonstrate the working product to KCMC first. Define whether the offer is a license or transfer, included support, hosting, maintenance, and price. Review any employment or IP agreements before asserting exclusive ownership. Development hours are private reference only.

## Final acceptance record (fill from observed evidence, not assumptions)
| Gate | Evidence | Result |
| --- | --- | --- |
| Basic church handoff CI | Exact commit GitHub Actions | Verified on e8d805a |
| Security contract CI | Exact commit GitHub Actions | Verified on e8d805a |
| Hero concept preview CI | Exact commit GitHub Actions | Verified on e8d805a |
| Apache denial of data and backups | Separate staging host HTTP 403/404 | Pending |
| Administrator session expiry | Separate staging test | Pending |
| Operational backup restore | Separate staging restore drill | Pending |
| Current event and service facts | Church-approved content review | Pending |
| Final customer demonstration | Owner acceptance | Pending |

**Release decision: NOT YET APPROVED.** The three priority CI workflows are green; staging and customer acceptance are still required. Do not interpret historical-feature workflow failures as automatically relevant or irrelevant without triage.

## Candidate staging evidence — October 30, 2026
Review artifact from commit `9123456157b8d3d907f2eb25a040d99048d94c13`.
- GitHub Basic church handoff, Security contract and Hero preview: passed.
- Review archive integrity: SHA-256 matched after checksum format correction.
- Isolated Apache 2.4 tests reported: administrator sign-in/dashboard, idle-session expiry, protected JSON/backup URL denial, publishing and backup creation, and isolated backup restore.
- **Not verified:** actual cPanel configuration, production data migration, church approval of public content, final device visual acceptance.
- The isolated Apache results are not authorization to install or overwrite production.

Release decision remains **pending owner approval and host-specific acceptance**. Keep automatic deployment disabled and PR #169 in draft.

## Read-only production host inspection — October 30, 2026
Evidence supplied from cPanel terminal at `/home/bobsome1/public_html/kcmc-connect`:
- PHP CLI: 8.2.35.
- The public installation directory is not a Git working tree; `.cpanel.yml` is absent there.
- `.htaccess` exists, contains `Options -Indexes`, file-level JSON denial, and a `data|backups` rewrite deny rule.
- Public HTTP probes returned **403** for `data/content.json`, `data/private/users.json`, and `backups/test-nonexistent.json`.
- These observations verify the tested production URL restrictions, **not** the candidate installation, authentication, or full host security.
- No live files were changed by this inspection.

**Next:** deploy the candidate only to an explicitly authorized, isolated staging document root with separate synthetic storage; verify the exact archive, Apache behavior, session expiry, backup restore, mobile/desktop layout, and church content. Do not overwrite the production directory.
