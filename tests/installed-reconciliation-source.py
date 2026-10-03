#!/usr/bin/env python3
"""Read-only exact-source verification. Never calls an installer or a host."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '2146af219d2fd23136eae1685f91a2a2caec030e'
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

manifest = json.loads((ROOT / 'docs/installed-reconciliation-2026-10-03.json').read_text())
check(set(manifest['runtime_sha256']) == set(expected), 'manifest contains exactly the ten installed runtime files')
for name, content in expected.items():
    check((ROOT / PREFIX / name).read_bytes() == content, name + ': byte-for-byte reviewed runtime match')
    check(hashlib.sha256(content).hexdigest() == manifest['runtime_sha256'][name], name + ': recorded SHA-256 match')

changed = set(git('diff', '--name-only', BASE, '--', PREFIX).decode().splitlines())
check(changed == {PREFIX + p for p in expected}, 'runtime diff is exactly six Tony files plus four readability pages')
for path in ['.cpanel.yml', 'KCMC-Connect-Phase6-Recreated/data/content.json', 'KCMC-Connect-Phase6-Recreated/config.example.php']:
    check((ROOT / path).read_bytes() == source(BASE, path), path + ': unchanged')
login = (ROOT / PREFIX / 'member/login.php').read_bytes()
check(login.split(b'?><!doctype html>', 1)[0] == base['member/login.php'].split(b'?><!doctype html>', 1)[0], 'staff authentication PHP remains byte-for-byte unchanged')
js = (ROOT / PREFIX / 'public-presentation.js').read_text()
css = (ROOT / PREFIX / 'public-presentation.css').read_text()
check('8000' in js and '420000' not in js, 'installed eight-second rotation retained; uninstalled seven-minute patch excluded')
check('KCMC hero caption fix' not in css, 'uninstalled caption CSS absent (exact-byte checks are authoritative)')
print('Installed reconciliation exact-source checks passed.')
