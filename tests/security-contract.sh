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

if grep -R -Eq --exclude='RELEASE_NOTES.md' "admin_password_hash|shared_admin_password" "$app_dir"; then
  fail "Legacy shared-password configuration remains"
fi

jq empty "$app_dir/data/content.json" "$app_dir/manifest.webmanifest"
jq empty "$app_dir/data/releases/3.0.0.json"
node --check "$app_dir/app.js"
node --check "$app_dir/sw.js"
command -v php >/dev/null || fail "PHP is required for syntax verification"
find "$app_dir" -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null

echo "KCMC Version 3 security contract passed."
