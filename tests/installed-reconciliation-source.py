#!/usr/bin/env python3
"""Verify installed provenance and enumerated approved deltas; never call a host."""
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
# Reviewed PR90 presentation only; no installer or caption patch is executed.
bright_bytes = (ROOT / 'tests/fixtures/contemporary-bright-reviewed.json').read_bytes()
check(hashlib.sha256(bright_bytes).hexdigest() == 'b85e1c0dfbd0f38e877fb2e96f639784b79966b50eccbdbb76b0817997d9183a', 'reviewed bright presentation fixture remains exact')
bright = json.loads(bright_bytes)
for name in bright['replacements']:
    approved.setdefault(name, [])

# PR103 photo placements follow the bright integration; overlapping versions are explicitly enumerated.
image_bytes = (ROOT / 'tests/fixtures/supplied-images-runtime-delta.json').read_bytes()
check(hashlib.sha256(image_bytes).hexdigest() == 'f4b79cacf3985f4f5b5d0605f3308f594b78eff91ac5955f8098c4df8763a322', 'reviewed supplied image delta remains exact')
image_delta = json.loads(image_bytes)
check(set(image_delta) == {'index.php', 'public-presentation.js', 'sw.js'}, 'supplied image runtime delta is limited to public photo surfaces')
offline_bytes = (ROOT / 'tests/fixtures/public-photo-offline-reviewed.json').read_bytes()
check(hashlib.sha256(offline_bytes).hexdigest() == '38eaa8ddcd3022d4e21bf7e46c1586ab2bb258390141ce374de745c4140f7bb4', 'reviewed offline photo delta remains exact')
offline = json.loads(offline_bytes)
check(set(offline) == {'source_commit', 'replacements'} and offline['source_commit'] == '61c70f590735522adbfd6be02dab6888924a54fd', 'offline repair source remains pinned')
check(set(offline['replacements']) == {'index.php', 'public-presentation.js', 'sw.js'}, 'offline repair scope remains public photo/runtime cache surfaces')

# Owner-requested visitor welcome scope. The proposed delta is enumerated byte
# for byte against current main; merge and deployment still require approval.
visitor_bytes = (ROOT / 'tests/fixtures/visitor-welcome-reviewed.json').read_bytes()
check(hashlib.sha256(visitor_bytes).hexdigest() == 'c1063495d8d493eea0fb3561648442f0c9967504193fc27b2e0fcde494c211ab', 'visitor delta fixture remains exact')
visitor = json.loads(visitor_bytes)
check(visitor['source_commit'] == 'b6093050dafe9a8d5b2ad4d958fdae742bc06624', 'visitor baseline remains current reviewed main')
check(set(visitor['replacements']) == {'index.php', 'public-presentation.css', 'sw.js', 'app.js', 'api/connection.php', 'admin/connections.php'}, 'visitor changes are confined to six named existing files')
check(set(visitor['new_files']) == {'lib/visitor-welcome.php'}, 'one independent visitor mail module is introduced')

def apply_visitor(name, content):
    if name not in visitor['replacements']:
        return content
    check(hashlib.sha256(content).hexdigest() == visitor['baseline_sha256'][name], name + ': visitor baseline bytes match')
    for old, new in visitor['replacements'][name]:
        check(content.count(old.encode()) == 1, name + ': visitor replacement anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    return content

# Owner-requested blue theme, fish navigation and photographic cleanup.
# Every runtime delta is enumerated against the already reconstructed PR110 bytes.
appearance_bytes = (ROOT / 'tests/fixtures/public-appearance-reviewed.json').read_bytes()
def git_blob(content):
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
check(git_blob(appearance_bytes) == 'b55e7fe921bc8e5040f20cdae612eb78a759e537', 'public appearance delta fixture remains exact')
appearance = json.loads(appearance_bytes)
check(set(appearance) == {'source_commit', 'baseline_git_blob', 'replacements', 'new_assets', 'preserved_assets'}, 'appearance fixture has only the reviewed fields')
check(appearance['source_commit'] == '268bebca444bd4970bb4ecaa0d6eceb6a11988fd', 'appearance baseline is deployed PR110')
check(set(appearance['replacements']) == {'index.php', 'public-presentation.css', 'public-presentation.js', 'sw.js'}, 'appearance scope is exactly four public runtime files')
check(set(appearance['baseline_git_blob']) == set(appearance['replacements']), 'every appearance source has an exact baseline blob')
check(set(appearance['replacements']) <= set(expected) | set(visitor['replacements']), 'appearance sources remain covered by historical reconstruction')
check(set(appearance['new_assets']) == {'assets/visuals/kcmc-building-retouched-20261009.jpg'}, 'one separate retouched exterior asset is permitted')
check(set(appearance['preserved_assets']) == {'assets/visuals/kcmc-building-2024.webp', 'assets/visuals/kcmc-ministry-group.jpg', 'assets/visuals/kcmc-bridge-logo.jpg', 'assets/visuals/kcmc-bridge-wordmark.png', 'assets/visuals/kcmc-bridge-logo-composite.png'}, 'original and removed public artwork remain archived intact')

def apply_appearance(name, content):
    if name not in appearance['replacements']:
        return content
    check(git_blob(content) == appearance['baseline_git_blob'][name], name + ': PR110 reconstruction matches the appearance baseline')
    for old, new in appearance['replacements'][name]:
        check(content.count(old.encode()) == 1, name + ': appearance replacement anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    return content

for name, info in appearance['new_assets'].items():
    content = (ROOT / PREFIX / name).read_bytes()
    check(git_blob(content) == info['git_blob'] and len(content) == info['bytes'], name + ': exact retouched web image bytes')
    check(len(content) <= 600_000, name + ': mobile image budget')
for name, blob in appearance['preserved_assets'].items():
    check(git_blob((ROOT / PREFIX / name).read_bytes()) == blob, name + ': original archive bytes are unchanged')
appearance_paths = {PREFIX + p for p in appearance['replacements']} | {PREFIX + p for p in appearance['new_assets']}

for name, content in expected.items():
    for old, new in approved.get(name, []):
        old, new = old.encode(), new.encode()
        check(content.count(old) == 1, name + ': approved replacement has exactly one source anchor')
        content = content.replace(old, new, 1)
    actual = (ROOT / PREFIX / name).read_bytes()
    if name == 'public-presentation.js':
        # PR99 intentionally removes only the obsolete nested hero-card photo injection.
        marker = b"  // Keep the hero as a single rotating image plane; do not inject a second photo into the service card."
        source_start = content.find(b"  // Keep the existing local hero photo unless the church's published image loads.\n")
        source_end = content.find(b"  const section = make('section', 'section family-welcome');", source_start)
        if source_start >= 0 and source_end > source_start:
            content = content[:source_start] + marker + b"\n\n" + content[source_end:]
    if name == 'index.php':
        # PR99 intentionally adds the approved church-family photo as one additional hero frame.
        anchor = b'    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-stage-2014.webp" alt="KCMC worship stage, photographed in 2014" loading="lazy" decoding="async" width="640" height="480" hidden>\n'
        addition = b'    <img class="hero-photo" data-hero-photo src="./assets/visuals/kcmc-ministry-group.jpg" alt="KCMC church family and ministry group" loading="lazy" decoding="async" width="640" height="480" hidden>\n'
        check(content.count(anchor) == 1, 'index.php: approved hero insertion anchor is unique')
        content = content.replace(anchor, anchor + addition, 1)
    for old, new in bright['replacements'].get(name, []):
        check(content.count(old.encode()) == 1, name + ': bright presentation anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    if name == 'public-presentation.css':
        content += bright['css_append'].encode()
    for old, new in image_delta.get(name, []):
        check(content.count(old.encode()) == 1, name + ': supplied image replacement anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    for old, new in offline['replacements'].get(name, []):
        check(content.count(old.encode()) == 1, name + ': offline repair anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    content = apply_appearance(name, apply_visitor(name, content))
    check(actual == content, name + ': exact reviewed runtime plus enumerated visitor and appearance differences only')

for name in set(visitor['replacements']) - set(expected):
    content = apply_appearance(name, apply_visitor(name, source(visitor['source_commit'], PREFIX + name)))
    check((ROOT / PREFIX / name).read_bytes() == content, name + ': only exact visitor delta permitted')
for name, sha in visitor['new_files'].items():
    check(hashlib.sha256((ROOT / PREFIX / name).read_bytes()).hexdigest() == sha, name + ': exact separately tested visitor module')
visitor_paths = {PREFIX + p for p in visitor['replacements']} | {PREFIX + p for p in visitor['new_files']}

# Publication Designer changes remain constrained to the same three reviewed
# admin files. Pin their exact Git blobs so older runtime provenance checks stay
# byte-for-byte authoritative while allowing the approved multi-page upgrade.
publication = {
    'admin/index.php': 'c130b7523b8a59fdde1101fee61a065402108674',
    'admin/publication-designer.php': '8efd67d5870c2cbfa43f64b044d78499cb2cbed6',
    'admin/publication-projects.php': '5aa61e6e23da4ec7a327d8345f8f0067c1c5140b',
    'admin/publication-media.php': '8610de8eef17ee596150e5ae81b06fb52a864ba5',
}
# Save responses may update only the editor project that initiated them.
publisher_bytes = (ROOT / 'tests/fixtures/publication-save-reviewed.json').read_bytes()
check(hashlib.sha256(publisher_bytes).hexdigest() == '102b657b0d2bcb233f26c0987027930aaacd0976e9d0e41bb7716168f3c952e3', 'reviewed publication save delta remains exact')
publisher = json.loads(publisher_bytes)
check(set(publisher) == {'source_commit', 'replacements'} and publisher['source_commit'] == 'c19214a0078ae8a4d306954a76ca4a8f96dadcb2', 'publication repair source remains pinned')
editor_bytes = (ROOT / 'tests/fixtures/publication-editor-reviewed.json').read_bytes()
check(hashlib.sha256(editor_bytes).hexdigest() == 'd927f303e159be1a97eece7d2ea7f624f4d950156e825e03ccf6cbfdef05a6db', 'reviewed publication fidelity delta remains exact')
editor = json.loads(editor_bytes)
check(set(editor) == {'source_commit', 'replacements'} and editor['source_commit'] == '61c70f590735522adbfd6be02dab6888924a54fd', 'publication fidelity source remains pinned')
check(set(editor['replacements']) == {'admin/publication-designer.php', 'admin/publication-projects.php'}, 'publication fidelity scope remains exactly editor and project endpoint')
for name, blob in publication.items():
    if name == 'admin/publication-designer.php':
        content = source(publisher['source_commit'], PREFIX + name)
        header = b'blob ' + str(len(content)).encode() + b'\0'
        check(hashlib.sha1(header + content).hexdigest() == blob, name + ': approved repair baseline blob retained')
        for old, new in publisher['replacements']:
            check(content.count(old.encode()) == 1, name + ': publication repair anchor is unique')
            content = content.replace(old.encode(), new.encode(), 1)
        check(content == source(editor['source_commit'], PREFIX + name), name + ': save repair exactly reaches the fidelity baseline')
    else:
        content = source(editor['source_commit'], PREFIX + name)
        header = b'blob ' + str(len(content)).encode() + b'\0'
        check(hashlib.sha1(header + content).hexdigest() == blob, name + ': approved Publication Designer baseline blob retained')
    for old, new in editor['replacements'].get(name, []):
        check(content.count(old.encode()) == 1, name + ': publication fidelity anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    if name == 'admin/publication-designer.php':
        interaction_bytes = (ROOT / 'tests/fixtures/publication-interaction-reviewed.json').read_bytes()
        check(hashlib.sha256(interaction_bytes).hexdigest() == '979e63e56690eeba8e088b0e26743699a90b7f037877e462e877b661cc162bed', 'reviewed Publisher interaction delta remains exact')
        interaction = json.loads(interaction_bytes)
        check(set(interaction) == {'source_commit', 'baseline_sha256', 'replacements'} and interaction['source_commit'] == 'b6093050dafe9a8d5b2ad4d958fdae742bc06624', 'interaction source remains pinned to reviewed main')
        check(hashlib.sha256(content).hexdigest() == interaction['baseline_sha256'], 'prior Publisher proofs exactly reconstruct interaction baseline')
        check(len(interaction['replacements']) == 7, 'interaction upgrade permits exactly seven named replacements')
        for old, new in interaction['replacements']:
            check(content.count(old.encode()) == 1, 'Publisher interaction replacement anchor is unique')
            content = content.replace(old.encode(), new.encode(), 1)
        arrange_bytes = (ROOT / 'tests/fixtures/publication-arrange-reviewed.json').read_bytes()
        check(hashlib.sha256(arrange_bytes).hexdigest() == 'f65d80794ebc496050523b306b01732b536ba530d17e151561720e1a583005de', 'reviewed Publisher arrange/history fixture remains exact')
        arrange = json.loads(arrange_bytes)
        check(set(arrange) == {'source_commit', 'source_git_blob', 'target_git_blob', 'scope', 'features'}, 'arrange/history fixture has only reviewed fields')
        check(arrange['source_commit'] == '87e2936559e79a860f2d07f6012c2a8cbb26cb59', 'arrange/history baseline remains audited main')
        check(arrange['scope'] == ['admin/publication-designer.php'], 'arrange/history runtime scope is exactly the Publication Designer')
        check(set(arrange['features']) == {'undo-redo','duplicate-object','bring-to-front','bring-forward','send-backward','send-to-back','keyboard-shortcuts'}, 'arrange/history feature scope remains exact')
        check(git_blob(content) == arrange['source_git_blob'], 'prior Publisher proofs exactly reconstruct arrange/history baseline')
        actual_arrange = (ROOT / PREFIX / name).read_bytes()
        check(git_blob(actual_arrange) == arrange['target_git_blob'], 'Publisher arrange/history target blob matches reviewed build')
        content = actual_arrange
    check((ROOT / PREFIX / name).read_bytes() == content, name + ': exact reviewed save/fidelity/interaction/arrange deltas only')

image_inventory = json.loads((ROOT / 'docs/supplied-images-2026-10-06.json').read_text())
check(len(image_inventory) == 9, 'exactly nine supplied assets inventoried')
image_paths = {PREFIX + 'assets/visuals/' + a['file'] for a in image_inventory}
for asset in image_inventory:
    check(hashlib.sha256((ROOT / PREFIX / 'assets/visuals' / asset['file']).read_bytes()).hexdigest() == asset['sha256'], asset['file'] + ': supplied bytes preserved')

# The deployment guide is documentation only, with its complete approved delta
# pinned independently. This permits one named document without exempting any
# application path from the exact runtime checks above.
guide_bytes = (ROOT / 'tests/fixtures/deployment-guide-reviewed.json').read_bytes()
check(hashlib.sha256(guide_bytes).hexdigest() == '4bb31d71293977e1d05cb9e3a2f935d87150c92a897ec9a14330b6de93d9e94b', 'reviewed deployment guide delta remains exact')
guide = json.loads(guide_bytes)
check(set(guide) == {'source_commit', 'replacements'} and guide['source_commit'] == 'f4442fc4cce2121828544b79b8ba3591c5fe0dab', 'deployment guide source remains pinned')
guide_path = PREFIX + 'DEPLOY.md'
check(set(guide['replacements']) == {guide_path}, 'documentation scope is exactly the deployment guide')
guide_content = source(guide['source_commit'], guide_path)
for old, new in guide['replacements'][guide_path]:
    check(guide_content.count(old.encode()) == 1, 'deployment guide replacement anchor is unique')
    guide_content = guide_content.replace(old.encode(), new.encode(), 1)
check((ROOT / guide_path).read_bytes() == guide_content, 'deployment guide matches the exact reviewed documentation delta')
documentation_paths = {guide_path}
changed = set(git('diff', '--name-only', BASE, '--', PREFIX).decode().splitlines())
check(changed == ({PREFIX + p for p in expected} | {PREFIX + p for p in publication} | image_paths | documentation_paths | visitor_paths | appearance_paths), 'application diff is exact runtime, Publisher, documentation and enumerated visitor/appearance scope')
changed_since_reconciled = set(git('diff', '--name-only', RECONCILED, '--', PREFIX).decode().splitlines())
check(changed_since_reconciled == ({PREFIX + p for p in approved} | {PREFIX + 'sw.js'} | {PREFIX + p for p in publication} | image_paths | documentation_paths | visitor_paths | appearance_paths), 'post-reconciliation diff is exact reviewed source plus enumerated visitor/appearance scope')
for path in ['.cpanel.yml', 'KCMC-Connect-Phase6-Recreated/data/content.json', 'KCMC-Connect-Phase6-Recreated/config.example.php']:
    check((ROOT / path).read_bytes() == source(BASE, path), path + ': unchanged')
login = (ROOT / PREFIX / 'member/login.php').read_bytes()
check(login.split(b'?><!doctype html>', 1)[0] == base['member/login.php'].split(b'?><!doctype html>', 1)[0], 'staff authentication PHP remains byte-for-byte unchanged')
js = (ROOT / PREFIX / 'public-presentation.js').read_text()
css = (ROOT / PREFIX / 'public-presentation.css').read_text()
check('}, 420000);' in js and '}, 8000);' not in js, 'approved seven-minute rotation retained')
check("const caption = gallery.querySelector('[data-hero-caption]');" not in js and "!controls || !caption || !toggle" not in js and "photos[current].alt || ''" in js, 'primary hero rotation no longer depends on removed caption element')
check('KCMC hero caption fix' not in css, 'no additional caption CSS introduced (exact-byte checks are authoritative)')
index = (ROOT / PREFIX / 'index.php').read_text()
check('data-caption=' not in index and 'data-hero-caption' not in index and 'photo archive,' not in index, 'public homepage carries no obsolete hero caption payload')
check('kcmc-ministry-group.jpg' not in index, 'owner-rejected photograph of the kids poster is absent from public output')
check('hero-card-with-photo' not in js and 'hero-church-window' not in js, 'hero service card no longer injects a second building photo')
print('Installed reconciliation provenance and approved runtime exact-source checks passed.')
