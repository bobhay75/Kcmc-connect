#!/usr/bin/env python3
"""Create a review-only, clean-directory basic KCMC handoff candidate.

Never reads or writes the live host; not an installer or a migration tool.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

source = Path(__file__).resolve().parents[2] / 'KCMC-Connect-Phase6-Recreated'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', type=Path, help='A new, empty local directory')
args = parser.parse_args()
dest = args.destination.absolute()
if dest.exists() or dest == source or source in dest.parents or dest in source.parents:
    parser.error('destination must not exist or contain the source tree')
if any(p.is_symlink() for p in source.rglob('*')):
    parser.error('source contains symlinks; inspect before building')

# Keep full-product regression source intact. The basic profile is applied only
# to the new output tree, after validating both sides of each replacement.
profile_root = Path(__file__).with_name('profile')
profile = json.loads(Path(__file__).with_name('profile.json').read_text())
replacements = {}
if profile_root.is_symlink() or any(p.is_symlink() for p in profile_root.rglob('*')):
    parser.error('profile contains symlinks; inspect before building')
actual_files = {p.relative_to(profile_root).as_posix() for p in profile_root.rglob('*') if p.is_file()}
if actual_files != set(profile['files']):
    parser.error('profile file list differs from its manifest')
for name, record in profile['files'].items():
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name:
        parser.error('invalid profile path')
    original = (source / relative).read_bytes()
    replacement = (profile_root / relative).read_bytes()
    if hashlib.sha256(original).hexdigest() != record['source_sha256']:
        parser.error('shared source changed; reconcile profile before building: ' + name)
    if hashlib.sha256(replacement).hexdigest() != record['candidate_sha256']:
        parser.error('profile bytes differ from the manifest: ' + name)
    replacements[name] = replacement

def ignore(directory, names):
    relative = Path(directory).relative_to(source)
    excluded = set()
    if relative == Path('.'):
        excluded.update({'config.php', 'backups', 'SETUP-CREDENTIALS.txt', 'DEPLOY.md', 'ICON-REPAIR.md', 'PHASE6-COMMIT.txt', 'RELEASE-MANIFEST.txt', 'RELEASE_NOTES.md', 'README.md'})
    if relative == Path('data'):
        excluded.add('private')
    return excluded.intersection(names)

shutil.copytree(source, dest, ignore=ignore)
for name, content in replacements.items():
    (dest / name).write_bytes(content)
allow = {
    'admin': {'index.php','home.php','upgrades.php','login.php','setup.php','save.php','posts.php','event-create.php','connections.php','connections-export.php','rsvps.php','rsvps-export.php','event-descriptions.js','publishing-desk.js'},
    'member': {'login.php','logout.php'},
    'api': {'content.php','connection.php','rsvp.php'},
}
for folder, keep in allow.items():
    for item in (dest / folder).iterdir():
        if item.name not in keep:
            if item.is_dir(): shutil.rmtree(item)
            else: item.unlink()
for name in ['payroll.php','timeclock.php','team-workspace.php','publication-drafts.php','prayer-care.php','push-subscriptions.php','invitation-delivery.php','invitation-mailer.php','password-lifecycle.php']:
    (dest / 'lib' / name).unlink(missing_ok=True)
# Add a protected, informational upgrade catalog only to the Core output.
# The full-product source remains unchanged and premium modules stay absent.
catalog = Path(__file__).with_name('upgrade-catalog.php')
if catalog.is_symlink() or not catalog.is_file():
    parser.error('upgrade catalog source missing or linked')
catalog_text = catalog.read_text(encoding='utf-8')
if 'kcmc_require_role' not in catalog_text or 'kcmc_private_headers()' not in catalog_text:
    parser.error('upgrade catalog must enforce administrator authentication and private headers')
(dest / 'admin' / 'upgrades.php').write_text(catalog_text, encoding='utf-8')
# The new page is not part of the pinned historical profile: restrict it
# explicitly in the generated Core bootstrap and link only from basic admin.
bootstrap = dest / 'lib' / 'bootstrap.php'
bootstrap_text = bootstrap.read_text(encoding='utf-8')
old_allow = "'admin' => ['index.php', 'home.php', 'login.php'"
new_allow = "'admin' => ['index.php', 'home.php', 'upgrades.php', 'login.php'"
if bootstrap_text.count(old_allow) == 1:
    bootstrap_text = bootstrap_text.replace(old_allow, new_allow, 1)
elif bootstrap_text.count(new_allow) != 1:
    parser.error('basic administrator route allowlist missing or ambiguous')
bootstrap.write_text(bootstrap_text, encoding='utf-8')
admin_home = dest / 'admin' / 'index.php'
admin_text = admin_home.read_text(encoding='utf-8')
original = '<h1>Church content</h1>'
updated = '<h1>Church content</h1><p><a href="<?=kcmc_h(kcmc_url(\'admin/upgrades.php\'))?>">Available upgrades</a></p>'
if admin_text.count(updated) == 1:
    pass  # The hash-validated profile already contains the catalog link.
elif admin_text.count(original) == 1:
    admin_text = admin_text.replace(original, updated, 1)
else:
    parser.error('administrator heading anchor missing or ambiguous')
admin_home.write_text(admin_text, encoding='utf-8')
# Fail closed if any excluded private or development material is present.
for forbidden in ('config.php', 'SETUP-CREDENTIALS.txt', 'data/private', 'admin/publication-designer.php',
                  'member/timeclock.php', 'admin/timecards.php', 'api/team-workspace.php'):
    if (dest / forbidden).exists():
        parser.error(f'forbidden release material present: {forbidden}')
if not (dest / '.htaccess').is_file():
    parser.error('Apache access-control rules missing from release candidate')
rules = (dest / '.htaccess').read_text()
if 'RewriteRule ^(?:data|backups)(?:/|$) - [F,L,NC]' not in rules:
    parser.error('Apache private-data and backup deny rule missing')
if not (dest / 'admin/index.php').is_file() or not (dest / 'member/login.php').is_file():
    parser.error('administrator entry points missing')

# Give Core the bridge-forward visual identity, overriding inherited blue-gold
# homepage rules without modifying the full-product regression source.
bridge_css = Path(__file__).with_name('bridge-theme.css')
if bridge_css.is_symlink() or not bridge_css.is_file():
    parser.error('bridge theme asset missing or linked')
bridge_theme = bridge_css.read_text(encoding='utf-8')
if 'body.kcmc-welcome-design' not in bridge_theme:
    parser.error('bridge theme is missing scoped homepage styles')
(dest / 'bridge-theme.css').write_text(bridge_theme, encoding='utf-8')
homepage = dest / 'index.php'
homepage_text = homepage.read_text(encoding='utf-8')
old_style = '<link rel="stylesheet" href="home-welcome.css?v=20261023-bridge-gradient">'
new_style = old_style + '\n<link rel="stylesheet" href="bridge-theme.css?v=core-bridge-20261106">'
if homepage_text.count(old_style) != 1:
    parser.error('expected one homepage bridge stylesheet anchor')
homepage.write_text(homepage_text.replace(old_style, new_style, 1), encoding='utf-8')
service_worker = dest / 'sw.js'
worker_text = service_worker.read_text(encoding='utf-8')
old_cache = "'./home-welcome.css?v=20261023-bridge-gradient'"
new_cache = old_cache + ",'./bridge-theme.css?v=core-bridge-20261106'"
if worker_text.count(old_cache) != 1:
    parser.error('expected one service worker CSS cache anchor')
service_worker.write_text(worker_text.replace(old_cache, new_cache, 1), encoding='utf-8')

(dest / 'HANDOFF-STATUS.txt').write_text('REVIEW CANDIDATE ONLY. Not production-ready. Do not deploy or overwrite live data.\n')
print(f'Created review candidate: {dest}')
