#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
app_dir="$repo_dir/KCMC-Connect-Phase6-Recreated"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

grep -q "3.0.1" "$app_dir/VERSION" || fail "Version 3.0.1 marker is missing"
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

jq empty "$app_dir/data/content.json" "$app_dir/manifest.webmanifest"
jq -e '.contact.office_hours == "Tue–Thu • 9:00 AM–4:00 PM"' "$app_dir/data/content.json" >/dev/null || fail "Published office hours are stale"
jq -e '.contact.office_hours == "Tue–Thu • 9:00 AM–4:00 PM"' "$app_dir/data/releases/3.0.0.json" >/dev/null || fail "Release seed office hours are stale"
jq empty "$app_dir/data/releases/3.0.0.json"
jq -e '[.events[] | select(.id == "trunk-or-treat-2026" and .date == "2026-10-31" and .time == "4:30 PM" and .end_time == "6:30 PM" and .status == "published")] | length == 1' "$app_dir/data/content.json" >/dev/null || fail "Trunk or Treat event is missing or incomplete"
jq -e '[.events[] | select(.id == "trunk-or-treat-2026")] | length == 1' "$app_dir/data/releases/3.0.0.json" >/dev/null || fail "Trunk or Treat release seed is missing"
test -s "$app_dir/assets/visuals/trunk-or-treat-2026.webp" || fail "Trunk or Treat flyer asset is missing"
grep -q "kcmc_apply_required_public_content" "$app_dir/lib/bootstrap.php" || fail "Preserved production content migration is missing"
grep -Fq "Tue–Thu • 9:00 AM–4:00 PM" "$app_dir/lib/bootstrap.php" || fail "Preserved production office-hours migration is missing"
grep -q "kcmc_featured_announcement_index" "$app_dir/admin/index.php" || fail "Publishing Desk does not select the current announcement"
grep -q 'name="announcement_id"' "$app_dir/admin/index.php" || fail "Publishing Desk announcement identity is missing"
grep -Fq "date('l, F j, Y'" "$app_dir/bulletin.php" || fail "Bulletin date format is invalid"
if grep -Fq "date('Sunday, F j, Y'" "$app_dir/bulletin.php"; then
  fail "Broken literal Sunday date format remains"
fi
grep -Fq 'document.body.dataset.officeEmail' "$app_dir/app.js" || fail "Public forms ignore the published church email"
grep -Fq 'data-share-app' "$app_dir/index.php" || fail "KCMC Connect share control is missing"
grep -Fq "typeof navigator.share==='function'" "$app_dir/app.js" || fail "Native Web Share support is missing"
grep -Fq 'navigator.clipboard?.writeText' "$app_dir/app.js" || fail "Share copy fallback is missing"
grep -Fq "new URL('./',window.location.href).href" "$app_dir/app.js" || fail "Share target is not normalized to the KCMC app root"
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
grep -q "kcmc-connect-v3.0.1" "$app_dir/sw.js" || fail "Service worker cache was not bumped for 3.0.1"
grep -q "app.js?v=3.0.1" "$app_dir/index.php" || fail "Homepage still references stale app.js version"
grep -q "key.startsWith('kcmc-connect-')" "$app_dir/sw.js" || fail "Service worker cache cleanup is not isolated to KCMC Connect"
node --check "$app_dir/app.js"
node --check "$app_dir/sw.js"
bash -n "$repo_dir/tests/live-smoke.sh"
command -v php >/dev/null || fail "PHP is required for syntax verification"
find "$app_dir" -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php "$repo_dir/tests/php-behavior.php"

echo "KCMC Version 3 security contract passed."
