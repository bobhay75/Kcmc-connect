#!/usr/bin/env bash
set -euo pipefail

base_url=${1:-https://bobsome1.com/kcmc-connect/}
base_url=${base_url%/}/
tmp_dir=$(mktemp -d)
trap 'rm -rf -- "$tmp_dir"' EXIT

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

fetch() {
  local path=$1
  local name=$2
  curl --silent --show-error --location --max-time 25 \
    --dump-header "$tmp_dir/$name.headers" \
    --output "$tmp_dir/$name.body" \
    --write-out '%{http_code}' \
    "${base_url}${path}"
}

status=$(fetch '' home)
[[ $status == 200 ]] || fail "Homepage returned HTTP $status"
grep -Fq '8:00 • 9:15 • 10:30' "$tmp_dir/home.body" || fail 'Current worship times are missing'
grep -Fq 'Trunk or Treat!' "$tmp_dir/home.body" || fail 'Trunk or Treat is missing from the homepage'

status=$(fetch 'api/content.php' api)
[[ $status == 200 ]] || fail "Public content API returned HTTP $status"
jq -e '.events | type == "array"' "$tmp_dir/api.body" >/dev/null || fail 'Public content API did not return event JSON'
if jq -e 'has("prayers") or has("users") or has("invites")' "$tmp_dir/api.body" >/dev/null; then
  fail 'Public content API exposed a private-data key'
fi
if jq -e '.. | objects | keys[] | select(test("sermon|deck|job"; "i"))' "$tmp_dir/api.body" >/dev/null; then
  fail 'Public content API exposed a Sermon Assistant field'
fi

for path in data/content.json data/private/ backups/; do
  name=${path//\//_}
  status=$(fetch "$path" "$name")
  [[ $status == 403 || $status == 404 ]] || fail "$path returned HTTP $status instead of denying access"
done

status=$(fetch 'member/prayer-team.php' private)
[[ $status == 200 ]] || fail "Signed-out private route did not reach the login page (HTTP $status)"
grep -Fqi 'Member Sign In' "$tmp_dir/private.body" || fail 'Signed-out private route did not show the login page'
grep -Eqi '^cache-control:.*no-store' "$tmp_dir/private.headers" || fail 'Private route is missing no-store caching'
grep -Eqi '^x-robots-tag:.*noindex' "$tmp_dir/private.headers" || fail 'Private route is missing noindex protection'

status=$(fetch 'admin/service-decks.php' sermon_private)
[[ $status == 200 ]] || fail "Signed-out Sermon Assistant route did not reach the login page (HTTP $status)"
grep -Fqi 'Member Sign In' "$tmp_dir/sermon_private.body" || fail 'Signed-out Sermon Assistant route did not show the login page'
grep -Eqi '^cache-control:.*no-store' "$tmp_dir/sermon_private.headers" || fail 'Signed-out Sermon Assistant route is missing no-store caching'
grep -Eqi '^x-robots-tag:.*noindex' "$tmp_dir/sermon_private.headers" || fail 'Signed-out Sermon Assistant route is missing noindex protection'

echo "KCMC live smoke checks passed for $base_url"
