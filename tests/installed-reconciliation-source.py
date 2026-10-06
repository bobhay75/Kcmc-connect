#!/usr/bin/env python3
"""Verify PR91 provenance plus only PR92's approved deltas; never call a host."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '2146af219d2fd23136eae1685f91a2a2caec030e'
RECONCILED = 'b1fe32017781be8a570ae114148d66fca82bc867'
TONY = '2c767fd66299524a126f39c5350de8dac1ce1f85'
PHOTOS = '225c564138242f699a1bd31c75b5c78e65268ca7'
INSTALLER_SHA256 = '0220e1a40b3b17f64988dccb3af48dad4fc87e49bb2947a4d7507de812b71bea'
READABILITY_FILES = ['admin/health.php', 'admin/audit.php', 'admin/timecards.php', 'member/timeclock.php']


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source(ref, path):
    return git('show', ref + ':' + path)


def check(ok, message):
    if not ok:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


installer = source(TONY, 'tools/tony_delivery.py')
check(hashlib.sha256(installer).hexdigest() == INSTALLER_SHA256, 'reviewed Tony installer SHA-256 matches PR88 evidence')
# Loading the pinned module only defines its functions; __main__ and install()
# are never invoked. transform() is the original deterministic byte generator.
namespace = {'__name__': 'reviewed_source_only'}
exec(compile(installer, 'reviewed-tony-delivery.py', 'exec'), namespace)
check(namespace['BASE'] == BASE and namespace['PHOTOS'] == PHOTOS, 'installer dependencies remain pinned')
base = {p: source(BASE, PREFIX + p) for p in namespace['TARGETS']}
photos = {p: source(PHOTOS, PREFIX + p) for p in namespace['PHOTO_FILES']}
expected = namespace['transform'](base, photos)
# Inspect the saved shell installer's Python assignments without executing its
# filesystem, subprocess, backup or deployment operations.
readability = (ROOT / 'tests/fixtures/installed-readability-fix-20261001.sh.txt').read_bytes()
check(hashlib.sha256(readability).hexdigest() == 'f0957ebc4c6a512e4a82a9583f9d227d69aaebd2a058a189c97ab3dec6837c0b', 'saved readability installer reference is unchanged')
embedded = readability.decode().split("python3 <<'PY'\n", 1)[1].rsplit('\nPY\n)', 1)[0]
assignments = [n for n in ast.parse(embedded).body if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in {'items', 'scope', 'marker', 'css'}]
check(len(assignments) == 4, 'readability installer has four expected source assignments')
values = {}
exec(compile(ast.Module(body=assignments, type_ignores=[]), 'readability-source-assignments', 'exec'), {'__builtins__': {}}, values)
check(set(values['items']) == set(READABILITY_FILES), 'saved installer scope is exactly four pages')
css = values['css'].encode()
check(hashlib.sha256(css).hexdigest() == 'd0aa33606a160919369ecc8a6459211028ffc36592937e422cd9a5e9c8841c43', 'installed readability CSS SHA-256 matches saved source')
for name in READABILITY_FILES:
    original = source(BASE, PREFIX + name)
    check(original.count(b'</style>') == 1, name + ': unique insertion anchor')
    content = original.replace(b'</style>', css + b'</style>', 1)
    check(content.replace(css, b'', 1) == original, name + ': only installed inline CSS changes')
    expected[name] = content

manifest_path = 'docs/installed-reconciliation-2026-10-03.json'
check((ROOT / manifest_path).read_bytes() == source(RECONCILED, manifest_path), 'PR91 provenance manifest remains byte-for-byte unchanged')
manifest = json.loads((ROOT / manifest_path).read_text())
check(set(manifest['runtime_sha256']) == set(expected), 'manifest contains exactly the ten installed runtime files')
for name, content in expected.items():
    check(source(RECONCILED, PREFIX + name) == content, name + ': PR91 byte-for-byte reviewed runtime match')
    check(hashlib.sha256(content).hexdigest() == manifest['runtime_sha256'][name], name + ': recorded SHA-256 match')

# Exact, single-occurrence replacements enumerate the approved PR92 changes.
# Do not normalize whole files, skip changed files, or accept arbitrary hashes:
# every other byte (including PHP, CSS, alt text and fallback code) must survive.
approved = {
    'index.php': [
        ('<p class="hero-photo-caption" data-hero-caption>', '<p class="hero-photo-caption" data-hero-caption hidden>'),
        (' data-caption="Church exterior • photo archive, May 2024"', ''),
        (' data-caption="Worship gathering • photo archive, June 2017"', ''),
        (' data-caption="Worship space • photo archive, October 2014"', ''),
        ('\n        <p class="hero-photo-caption" data-hero-caption hidden>Church exterior • photo archive, May 2024</p>', ''),
    ],
    'public-presentation.js': [
        ('}, 8000);', '}, 420000);'),
        ("firstPhoto.dataset.caption = 'Church exterior • from KCMC’s published Visit page';", "firstPhoto.dataset.caption = '';"),
        ('if (!firstPhoto.hidden && caption) caption.textContent = firstPhoto.dataset.caption;', 'if (caption) caption.hidden = true;'),
        ("      const source = make('figcaption', 'photo-source');\n      source.append(link('Church photo · KCMC Visit page', visitPage, ''));\n      figure.append(image, source);", '      figure.append(image);'),
        ("  const source = make('figcaption', 'photo-source');\n  source.append(link('Photo · KCMC Youth page', youthPage, ''));", '  const source = null;'),
        ('  figure.append(image, source);', '  figure.append(image);'),
        ("  const caption = gallery.querySelector('[data-hero-caption]');\n", ''),
        ('  if (photos.length < 2 || !controls || !caption || !toggle) return;', '  if (photos.length < 2 || !controls || !toggle) return;'),
        ("    caption.textContent = photos[current].dataset.caption || '';\n    if (announce && status) status.textContent = `Photo ${current + 1} of ${photos.length}. ${caption.textContent}`;", "    if (announce && status) status.textContent = `Photo ${current + 1} of ${photos.length}. ${photos[current].alt || ''}`;"),
    ],
    'member/timeclock.php': [
        ('<p class="eyebrow">EMPLOYEE TIME</p><h1>Time Clock</h1>', '<p class="eyebrow">STAFF TIME CLOCK</p><h1>Clock In / Clock Out</h1>'),
        ('<h2>You are clocked out.</h2><form', '<h2>You are clocked out.</h2><p class="tc-note">Start your shift here. Your clock-in time is recorded by the KCMC server.</p><form'),
        ('type="submit">Clock Out</button>', 'type="submit">Clock Out &amp; Save Shift</button>'),
    ],
}
for name, content in expected.items():
    for old, new in approved.get(name, []):
        old, new = old.encode(), new.encode()
        check(content.count(old) == 1, name + ': approved replacement has exactly one source anchor')
        content = content.replace(old, new, 1)
    check((ROOT / PREFIX / name).read_bytes() == content, name + ': exact PR91 bytes plus approved PR92 differences only')

# PR93 adds only an admin navigation link and a new protected publication
# designer. Pin their Git blob identities so the older PR91/PR92 byte-level
# preservation proof remains authoritative rather than being weakened.
pr93 = {
    'admin/index.php': 'c130b7523b8a59fdde1101fee61a065402108674',
    'admin/publication-designer.php': 'c5dc2a942cc5a8ccc68fc48a24b06aa5dcd03577',
    'admin/publication-projects.php': 'c3e88927599e32d31d69503db536eff9882ab79f',
}
for name, blob in pr93.items():
    actual = git('hash-object', PREFIX + name).decode().strip()
    check(actual == blob, name + ': exact PR93 reviewed blob retained')

changed = set(git('diff', '--name-only', BASE, '--', PREFIX).decode().splitlines())
check(changed == ({PREFIX + p for p in expected} | {PREFIX + p for p in pr93}), 'runtime diff is PR91/PR92 reviewed runtime plus exactly three PR93 admin files')
changed_since_reconciled = set(git('diff', '--name-only', RECONCILED, '--', PREFIX).decode().splitlines())
check(changed_since_reconciled == ({PREFIX + p for p in approved} | {PREFIX + p for p in pr93}), 'post-reconciliation diff is exactly PR92 approved deltas plus PR93 admin additions')
for path in ['.cpanel.yml', 'KCMC-Connect-Phase6-Recreated/data/content.json', 'KCMC-Connect-Phase6-Recreated/config.example.php']:
    check((ROOT / path).read_bytes() == source(BASE, path), path + ': unchanged')
login = (ROOT / PREFIX / 'member/login.php').read_bytes()
check(login.split(b'?><!doctype html>', 1)[0] == base['member/login.php'].split(b'?><!doctype html>', 1)[0], 'staff authentication PHP remains byte-for-byte unchanged')
js = (ROOT / PREFIX / 'public-presentation.js').read_text()
css = (ROOT / PREFIX / 'public-presentation.css').read_text()
check('}, 420000);' in js and '}, 8000);' not in js, 'approved seven-minute rotation retained')
check("data-hero-caption" not in js and "photos[current].alt || ''" in js, 'hero rotation no longer depends on removed caption element')
check('KCMC hero caption fix' not in css, 'no additional caption CSS introduced (exact-byte checks are authoritative)')
index = (ROOT / PREFIX / 'index.php').read_text()
check('data-caption=' not in index and 'data-hero-caption' not in index and 'photo archive,' not in index, 'public homepage carries no obsolete hero caption payload')
print('Installed reconciliation provenance and approved PR92 exact-source checks passed.')
