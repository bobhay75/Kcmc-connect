#!/usr/bin/env bash
set -euo pipefail

script='tools/production-smoke.sh'

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[[ -f "$script" ]] || fail 'production smoke script exists'
bash -n "$script" || fail 'production smoke script parses'
pass 'production smoke script parses'

grep -Fq "BASE_URL=\"\${1:-https://bobsome1.com/kcmc-connect}\"" "$script" || fail 'default production URL is explicit'
pass 'default production URL is explicit'

grep -Fq -- "--proto '=https'" "$script" || fail 'smoke requests are restricted to HTTPS'
grep -Fq -- '--connect-timeout 8' "$script" || fail 'smoke requests have connect timeout'
grep -Fq -- '--max-time 20' "$script" || fail 'smoke requests have total timeout'
pass 'network checks are HTTPS-only and bounded'

if grep -Eq -- '(^|[[:space:]])(-X|--request)[[:space:]]*(POST|PUT|PATCH|DELETE)|--data|--form|-F[[:space:]]' "$script"; then
  fail 'smoke script contains a mutating HTTP request'
fi
pass 'smoke script contains GET-only checks'

grep -Fq "A Pastor administrator approves anything shared with members." "$script" || fail 'role-based public prayer wording is asserted'
grep -Fq "Tony or Barry" "$script" || fail 'stale named-person wording is explicitly rejected'
pass 'public prayer wording regression is covered'

grep -Fq "'/admin/health.php'" "$script" || fail 'release-health protection is checked'
grep -Fq "'/admin/restore.php'" "$script" || fail 'restore protection is checked'
grep -Fq "'/admin/audit.php'" "$script" || fail 'audit protection is checked'
pass 'new administrator routes are checked while signed out'

grep -Fq "'/config.php'" "$script" || fail 'config exposure is checked'
grep -Fq "'/data/content.json'" "$script" || fail 'data exposure is checked'
grep -Fq "'/data/private/users.json'" "$script" || fail 'private store exposure is checked'
grep -Fq "'/backups/'" "$script" || fail 'backup exposure is checked'
pass 'protected storage paths are checked'

grep -Fq 'kcmc-connect-v3.0.2-public-only' "$script" || fail 'service-worker release marker is checked'
grep -Fq 'x-content-type-options' "$script" || fail 'security response headers are checked'
pass 'PWA marker and baseline security headers are checked'

printf 'Production smoke source contract checks passed.\n'
