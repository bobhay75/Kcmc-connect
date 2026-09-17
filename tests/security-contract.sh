#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
app_dir="$repo_dir/KCMC-Connect-Phase6-Recreated"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

grep -q "3.0.0" "$app_dir/VERSION" || fail "Version 3 marker is missing"
grep -q "data/private/" "$repo_dir/.gitignore" || fail "Private data is not ignored by Git"
grep -q "assets/newsletter/" "$repo_dir/.gitignore" || fail "Newsletter source pages are not blocked by Git"
grep -q -- "--exclude='data/private/'" "$repo_dir/.cpanel.yml" || fail "Deployment does not preserve private data"
grep -Eq "RewriteRule \^\(\?:data\|backups\)" "$app_dir/.htaccess" || fail "Apache does not block data and backups"
grep -Fq '<FilesMatch "(?:\.json(?:\.tmp-[A-Fa-f0-9]+)?|\.ndjson|\.lock)$">' "$app_dir/.htaccess" || fail "Apache file-level private-data fallback is missing"

grep -q "kcmc_require_role(\['member', 'prayer_team', 'pastor_admin'\])" "$app_dir/member/submit-prayer.php" || fail "Prayer submission role gate is missing"
grep -q "kcmc_require_role(\['prayer_team', 'pastor_admin'\])" "$app_dir/member/prayer-team.php" || fail "Prayer-team role gate is missing"
grep -q "kcmc_require_role(\['pastor_admin'\])" "$app_dir/admin/prayers.php" || fail "Pastor approval role gate is missing"
grep -q "Prayer content is intentionally unavailable" "$app_dir/member/index.php" || fail "Recovery privacy boundary is missing"

if grep -Eq "submit-prayer\.php|KCMC_PRAYERS|name=\"share_with_members\"" "$app_dir/care.php" "$app_dir/index.php"; then
  fail "A public page exposes the private prayer workflow"
fi

if find "$app_dir/assets/newsletter" -type f -print -quit 2>/dev/null | grep -q .; then
  fail "A complete newsletter source image remains in the release"
fi
if grep -R -Eq "assets/newsletter|aug-2026-page|newsletter page viewer" "$app_dir" --exclude='RELEASE_NOTES.md' --exclude='README.md' --exclude='DEPLOY.md'; then
  fail "A newsletter page-image reference remains in the app"
fi

grep -Fq 'privateRoute=/\/(?:member|admin)' "$app_dir/sw.js" || fail "Service worker private-route bypass is missing"
grep -q "Cache-Control: no-store" "$app_dir/lib/bootstrap.php" || fail "Private no-store headers are missing"
grep -q "X-Robots-Tag: noindex" "$app_dir/lib/bootstrap.php" || fail "Private noindex headers are missing"
grep -q "kcmc_current_user_if_session" "$app_dir/index.php" || fail "Public homepage still creates anonymous sessions"
grep -q "kcmc_current_user_if_session" "$app_dir/care.php" || fail "Public care page still creates anonymous sessions"

if grep -R -Eq --exclude='RELEASE_NOTES.md' "admin_password_hash|shared_admin_password" "$app_dir"; then
  fail "Legacy shared-password configuration remains"
fi

if grep -R -Fq "KCMC_STAFF_INITIAL_CODE" "$app_dir"; then
  fail "Legacy shared staff onboarding code remains"
fi
grep -q "kcmc_private_headers" "$app_dir/member/first-login.php" || fail "Retired first-login route is missing private no-store headers"
grep -q "http_response_code(410)" "$app_dir/member/first-login.php" || fail "Retired first-login route does not return HTTP 410"
if grep -Eq 'REQUEST_METHOD|\$_POST|<form|password_hash|kcmc_update_json_store|kcmc_login_user|temporary_code|name="staff"' "$app_dir/member/first-login.php"; then
  fail "Retired first-login route still contains account self-claim logic"
fi
if grep -Fq "member/first-login.php" "$app_dir/member/login.php"; then
  fail "Regular sign-in still advertises the retired self-claim route"
fi
grep -Fq "random_bytes(32)" "$app_dir/admin/users.php" || fail "Individual invitation token generation is missing"
grep -Fq "'token_hash' => hash('sha256', \$token)" "$app_dir/admin/users.php" || fail "Individual invitations are not stored by token hash"
grep -Fq "'email' => \$email" "$app_dir/admin/users.php" || fail "Individual invitations are not bound to a verified email"
grep -Fq "'role' => \$role" "$app_dir/admin/users.php" || fail "Individual invitations are not bound to an assigned role"
grep -Fq "KCMC_INVITES" "$app_dir/member/activate.php" || fail "Invitation activation store is missing"
grep -Fq "hash_equals(\$candidateHash, \$tokenHash)" "$app_dir/member/activate.php" || fail "Invitation activation does not verify the identity-bound token"
grep -Fq '<option value="pastor_admin">Pastor administrator</option>' "$app_dir/admin/users.php" || fail "Pastor administrator invitations are unavailable"
grep -Fq "separate one-time invitation" "$app_dir/member/login.php" || fail "Pastor sign-in does not direct Tony and Barry to individual invitations"

sermon_page="$app_dir/admin/service-decks.php"
sermon_action="$app_dir/admin/service-deck-action.php"
sermon_download="$app_dir/admin/service-deck-download.php"
sermon_library="$app_dir/lib/service-decks.php"
for file in "$sermon_page" "$sermon_action" "$sermon_download" "$sermon_library"; do
  test -f "$file" || fail "Authenticated Sermon Assistant component is missing: ${file#$app_dir/}"
done
for route in "$sermon_page" "$sermon_action" "$sermon_download"; do
  grep -Fq "kcmc_require_role(['pastor_admin', 'recovery_admin'])" "$route" || fail "Sermon Assistant route is missing its administrator role gate: ${route#$app_dir/}"
  grep -Fq 'kcmc_private_headers()' "$route" || fail "Sermon Assistant route is missing private response headers: ${route#$app_dir/}"
done
grep -Fq 'kcmc_csrf()' "$sermon_page" || fail "Sermon Assistant forms are missing CSRF tokens"
grep -q 'REQUEST_METHOD.*POST' "$sermon_action" || fail "Sermon Assistant mutations are not restricted to POST"
grep -Fq 'kcmc_verify_csrf' "$sermon_action" || fail "Sermon Assistant mutations are missing CSRF verification"
grep -Fq 'kcmc_can_approve_service_decks' "$sermon_action" || fail "Sermon Assistant decisions are missing the pastor-only authorization gate"
grep -Fq 'password_verify' "$sermon_action" || fail "Sermon Assistant decisions are missing password reauthentication"
grep -Fq "getenv('KCMC_PRIVATE_DATA_DIR')" "$app_dir/lib/bootstrap.php" || fail "External private-data directory configuration is missing"
grep -Fq "\$_SERVER['DOCUMENT_ROOT']" "$app_dir/lib/bootstrap.php" || fail "External private-data validation ignores the server document root"
grep -Fq 'must resolve outside every public web directory' "$app_dir/lib/bootstrap.php" || fail "External private-data overrides are not rejected inside the web root"
grep -Fq '!is_dir($privateDataDir) || is_link($privateDataDir)' "$app_dir/lib/bootstrap.php" || fail "External private-data overrides do not require an existing non-symlink directory"
grep -Fq "getenv('KCMC_SERMON_IMPORT_KEY')" "$sermon_library" || fail "Sermon Assistant import-key configuration is missing"
grep -Fq "hash_hmac('sha256'" "$sermon_library" || fail "Sermon Assistant signed imports do not use HMAC-SHA256"
grep -Fq 'hash_equals' "$sermon_library" || fail "Sermon Assistant signed imports do not use constant-time comparison"
grep -Fq "define('KCMC_SERVICE_DECKS_DIR', KCMC_PRIVATE_DATA" "$sermon_library" || fail "Sermon Assistant artifacts are not rooted in private storage"
if grep -Eiq '\b(shell_exec|exec|system|passthru|proc_open|popen|pcntl_exec)[[:space:]]*\(' "$sermon_page" "$sermon_action" "$sermon_download" "$sermon_library"; then
  fail "A Sermon Assistant web component can execute a shell or process"
fi

jq empty "$app_dir/data/content.json" "$app_dir/manifest.webmanifest"
jq empty "$app_dir/data/releases/3.0.0.json"
jq -e '[.events[] | select(.id == "trunk-or-treat-2026" and .date == "2026-10-31" and .time == "4:30 PM" and .end_time == "6:30 PM" and .status == "published")] | length == 1' "$app_dir/data/content.json" >/dev/null || fail "Trunk or Treat event is missing or incomplete"
jq -e '[.events[] | select(.id == "trunk-or-treat-2026")] | length == 1' "$app_dir/data/releases/3.0.0.json" >/dev/null || fail "Trunk or Treat release seed is missing"
test -s "$app_dir/assets/visuals/trunk-or-treat-2026.webp" || fail "Trunk or Treat flyer asset is missing"
grep -q "kcmc_apply_required_public_content" "$app_dir/lib/bootstrap.php" || fail "Preserved production content migration is missing"
grep -q "kcmc_featured_announcement_index" "$app_dir/admin/index.php" || fail "Publishing Desk does not select the current announcement"
grep -q 'name="announcement_id"' "$app_dir/admin/index.php" || fail "Publishing Desk announcement identity is missing"
grep -Fq "date('l, F j, Y'" "$app_dir/bulletin.php" || fail "Bulletin date format is invalid"
if grep -Fq "date('Sunday, F j, Y'" "$app_dir/bulletin.php"; then
  fail "Broken literal Sunday date format remains"
fi
grep -Fq 'document.body.dataset.officeEmail' "$app_dir/app.js" || fail "Public forms ignore the published church email"
grep -q "REQUEST_METHOD.*POST" "$app_dir/member/logout.php" || fail "Sign-out is not restricted to POST"
grep -q "kcmc_verify_csrf" "$app_dir/member/logout.php" || fail "Sign-out CSRF protection is missing"
grep -q "data-end-time" "$app_dir/index.php" || fail "Event end time is not exposed to calendar export"
grep -q "DTEND" "$app_dir/app.js" || fail "Calendar export does not include event end time"
grep -q "BEGIN:VTIMEZONE" "$app_dir/app.js" || fail "Calendar export does not define its America/Chicago timezone"
grep -q "KCMC_LOCAL_TIMEZONE = 'America/Chicago'" "$app_dir/lib/bootstrap.php" || fail "Publishing Desk timezone is not explicit"
grep -Fq 'kcmc_local_datetime_iso($ex,true)' "$app_dir/admin/save.php" || fail "Event expiry is not saved in KCMC local time"
if grep -q "Version 3 content migration" "$app_dir/lib/bootstrap.php"; then
  fail "Public content reads can still trigger a release migration write"
fi
grep -q "ignoreSearch:true" "$app_dir/sw.js" || fail "Offline cache does not normalize versioned asset requests"
grep -q "key.startsWith('kcmc-connect-')" "$app_dir/sw.js" || fail "Service worker cache cleanup is not isolated to KCMC Connect"
node --check "$app_dir/app.js"
node --check "$app_dir/sw.js"
bash -n "$repo_dir/tests/live-smoke.sh"
command -v php >/dev/null || fail "PHP is required for syntax verification"
find "$app_dir" -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
if KCMC_PRIVATE_DATA_DIR=/ php -r "require '$app_dir/lib/bootstrap.php';" >/dev/null 2>&1; then
  fail "Filesystem root is accepted as the external private-data directory"
fi
if KCMC_PRIVATE_DATA_DIR=relative-private php -r "require '$app_dir/lib/bootstrap.php';" >/dev/null 2>&1; then
  fail "A relative external private-data directory is accepted"
fi
if KCMC_PRIVATE_DATA_DIR="$app_dir/data" php -r "require '$app_dir/lib/bootstrap.php';" >/dev/null 2>&1; then
  fail "A web-root-contained external private-data directory is accepted"
fi
if KCMC_TEST_DOCUMENT_ROOT="$repo_dir" KCMC_PRIVATE_DATA_DIR="$repo_dir/contest-service-agent" php -r '$_SERVER["DOCUMENT_ROOT"] = getenv("KCMC_TEST_DOCUMENT_ROOT"); require $argv[1];' "$app_dir/lib/bootstrap.php" >/dev/null 2>&1; then
  fail "An external private-data directory beside the app but inside the server document root is accepted"
fi
php "$repo_dir/tests/php-behavior.php"

echo "KCMC Version 3 security contract passed."
