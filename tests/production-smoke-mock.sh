#!/usr/bin/env bash
set -euo pipefail

root="$(pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"

cat > "$tmp/bin/curl" <<'MOCK'
#!/usr/bin/env bash
set -u
headers=''
body=''
url=''
while (($#)); do
  case "$1" in
    -D|-o|-w|--connect-timeout|--max-time|--proto)
      key="$1"; value="${2:-}"
      case "$key" in
        -D) headers="$value" ;;
        -o) body="$value" ;;
      esac
      shift 2
      ;;
    -sS|--tlsv1.2)
      shift
      ;;
    https://*)
      url="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

[[ -n "$headers" && -n "$body" && -n "$url" ]] || exit 3
status=200
response_headers=$'HTTP/1.1 200 OK\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: SAMEORIGIN\r\nReferrer-Policy: strict-origin-when-cross-origin\r\n'
response_body=''

case "$url" in
  */kcmc-connect/)
    if [[ "${MOCK_STALE_WORDING:-0}" == '1' ]]; then
      response_body='KCMC CONNECT Prayer names stay private. Tony or Barry approves anything shared with members.'
    else
      response_body='KCMC CONNECT Prayer names stay private. A Pastor administrator approves anything shared with members.'
    fi
    ;;
  */manifest.webmanifest*)
    response_body='{"name":"KCMC Connect"}'
    ;;
  */sw.js)
    response_body="const CACHE='kcmc-connect-v3.0.2-public-only';"
    ;;
  */member/|*/member/timeclock.php*|*/admin/|*/admin/health.php|*/admin/restore.php|*/admin/audit.php|*/admin/operations.php|*/admin/push.php|*/admin/timecards.php*|*/admin/timecards-export.php*|*/admin/timecards-print.php*|*/admin/rsvps.php|*/admin/connections.php|*/admin/rsvps-export.php*|*/admin/connections-export.php*)
    status=302
    response_headers=$'HTTP/1.1 302 Found\r\nLocation: /kcmc-connect/member/login.php?next=test\r\nX-Content-Type-Options: nosniff\r\n'
    response_body='Redirecting'
    ;;
  */config.php|*/data/content.json|*/data/private/users.json|*/backups/)
    status=403
    response_headers=$'HTTP/1.1 403 Forbidden\r\nX-Content-Type-Options: nosniff\r\n'
    response_body='Forbidden'
    ;;
  *)
    status=404
    response_headers=$'HTTP/1.1 404 Not Found\r\n'
    response_body='Not found'
    ;;
esac

printf '%s' "$response_headers" > "$headers"
printf '%s' "$response_body" > "$body"
printf '%s' "$status"
MOCK
chmod +x "$tmp/bin/curl"

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

healthy_output="$(PATH="$tmp/bin:$PATH" bash "$root/tools/production-smoke.sh" 'https://example.test/kcmc-connect' 2>&1)" || {
  printf '%s\n' "$healthy_output" >&2
  fail 'healthy mocked deployment should pass'
}
grep -Fq 'Result: 24 passed, 0 failed.' <<<"$healthy_output" || {
  printf '%s\n' "$healthy_output" >&2
  fail 'healthy mocked deployment should pass all 24 checks'
}
pass 'healthy mocked deployment passes all smoke checks'

set +e
stale_output="$(MOCK_STALE_WORDING=1 PATH="$tmp/bin:$PATH" bash "$root/tools/production-smoke.sh" 'https://example.test/kcmc-connect' 2>&1)"
stale_status=$?
set -e
[[ $stale_status -eq 1 ]] || {
  printf '%s\n' "$stale_output" >&2
  fail 'stale public wording should fail smoke check'
}
grep -Fq 'FAIL: public prayer approval wording is current and role-based' <<<"$stale_output" || fail 'stale wording failure is reported clearly'
pass 'stale named-person wording is detected'

set +e
http_output="$(PATH="$tmp/bin:$PATH" bash "$root/tools/production-smoke.sh" 'http://example.test/kcmc-connect' 2>&1)"
http_status=$?
set -e
[[ $http_status -eq 2 ]] || {
  printf '%s\n' "$http_output" >&2
  fail 'non-HTTPS base URL should be rejected'
}
pass 'non-HTTPS smoke target is rejected before requests run'

printf 'Production smoke mocked end-to-end checks passed.\n'
