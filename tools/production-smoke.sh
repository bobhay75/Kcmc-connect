#!/usr/bin/env bash
set -u

BASE_URL="${1:-https://bobsome1.com/kcmc-connect}"
BASE_URL="${BASE_URL%/}"

if [[ "$BASE_URL" != https://* ]]; then
  printf 'FAIL: base URL must use HTTPS: %s\n' "$BASE_URL" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  printf 'FAIL: curl is required.\n' >&2
  exit 2
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
passes=0
fails=0

pass() {
  passes=$((passes + 1))
  printf 'PASS: %s\n' "$1"
}

fail() {
  fails=$((fails + 1))
  printf 'FAIL: %s\n' "$1" >&2
}

fetch() {
  local name="$1"
  local path="$2"
  local code
  if ! code="$(curl -sS --connect-timeout 8 --max-time 20 --proto '=https' --tlsv1.2 \
      -D "$workdir/$name.headers" -o "$workdir/$name.body" -w '%{http_code}' \
      "$BASE_URL$path")"; then
    printf '000'
    return
  fi
  printf '%s' "$code"
}

assert_200_contains() {
  local name="$1"
  local path="$2"
  local needle="$3"
  local label="$4"
  local code
  code="$(fetch "$name" "$path")"
  if [[ "$code" == "200" ]] && grep -Fq -- "$needle" "$workdir/$name.body"; then
    pass "$label"
  else
    fail "$label (HTTP $code)"
  fi
}

assert_redirect_to_login() {
  local name="$1"
  local path="$2"
  local label="$3"
  local code
  code="$(fetch "$name" "$path")"
  if [[ "$code" =~ ^30[12378]$ ]] && grep -Eiq '^location: .*member/login\.php' "$workdir/$name.headers"; then
    pass "$label"
  else
    fail "$label (HTTP $code)"
  fi
}

assert_not_public() {
  local name="$1"
  local path="$2"
  local label="$3"
  local code
  code="$(fetch "$name" "$path")"
  if [[ "$code" =~ ^(403|404)$ ]]; then
    pass "$label"
  else
    fail "$label (HTTP $code)"
  fi
}

printf 'KCMC production smoke check\nBase: %s\n\n' "$BASE_URL"

home_code="$(fetch home '/')"
if [[ "$home_code" == "200" ]] && grep -Fq 'KCMC CONNECT' "$workdir/home.body"; then
  pass 'public homepage responds with KCMC Connect shell'
else
  fail "public homepage shell (HTTP $home_code)"
fi

if [[ "$home_code" == "200" ]] && grep -Fq 'A Pastor administrator approves anything shared with members.' "$workdir/home.body" && ! grep -Fq 'Tony or Barry' "$workdir/home.body"; then
  pass 'public prayer approval wording is role-based'
else
  fail 'public prayer approval wording is current and role-based'
fi

if grep -Eiq '^x-content-type-options:[[:space:]]*nosniff' "$workdir/home.headers" && \
   grep -Eiq '^x-frame-options:[[:space:]]*SAMEORIGIN' "$workdir/home.headers" && \
   grep -Eiq '^referrer-policy:' "$workdir/home.headers"; then
  pass 'public response includes baseline security headers'
else
  fail 'public response baseline security headers'
fi

assert_200_contains manifest '/manifest.webmanifest?v=3.0.1' 'KCMC Connect' 'web-app manifest is live'
assert_200_contains worker '/sw.js' 'kcmc-connect-v3.0.2-public-only' 'service worker release marker is live'

assert_redirect_to_login member '/member/' 'signed-out member route redirects to login'
assert_redirect_to_login admin '/admin/' 'signed-out administrator route redirects to login'
assert_redirect_to_login health '/admin/health.php' 'signed-out release-health route redirects to login'
assert_redirect_to_login restore '/admin/restore.php' 'signed-out restore route redirects to login'
assert_redirect_to_login audit '/admin/audit.php' 'signed-out audit-history route redirects to login'

assert_not_public config '/config.php' 'server configuration is not publicly readable'
assert_not_public content '/data/content.json' 'public-content JSON file is blocked from direct access'
assert_not_public private '/data/private/users.json' 'private account store is blocked from direct access'
assert_not_public backups '/backups/' 'backup directory is blocked from public access'

printf '\nResult: %d passed, %d failed.\n' "$passes" "$fails"
if (( fails > 0 )); then
  exit 1
fi
