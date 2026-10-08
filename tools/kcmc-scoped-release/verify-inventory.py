#!/usr/bin/env python3
"""Verify the deployed helper pins against the independently reviewed inventory."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location('scoped_release', str(HERE / 'installer.py'))
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)
INV = json.loads((HERE / 'approved-inventory.json').read_text())
assert INSTALLER.COMMIT == INV['commit']
assert str(INSTALLER.APP_ROOT) == INV['app']
assert set(INSTALLER.FILES) == set(item['path'] for item in INV['files'])
assert len(INSTALLER.FILES) == 16
assert INSTALLER.GUARDS == {item['path']: item['sha256'] for item in INV['preserve_guards']}
BASELINES = json.loads((HERE / 'baseline-inventory.json').read_text())
assert set(BASELINES) == set(['ae004a659a7c2fb334296fa41f54dd5263f4d5c0',
                              '61c70f590735522adbfd6be02dab6888924a54fd'])
assert set(INSTALLER.BASELINE_IDS) == set(BASELINES)
assert INSTALLER.BASELINES == BASELINES
assert INSTALLER.SOURCE_ROOT == ('https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' +
                                 INV['commit'] + '/KCMC-Connect-Phase6-Recreated/')
for commit, bundle in BASELINES.items():
    assert set(bundle) == set(INSTALLER.FILES)
    assert subprocess.check_output(['git', 'cat-file', '-t', commit], cwd=str(ROOT)).strip() == b'commit'
    for name, preimage in bundle.items():
        source = commit + ':KCMC-Connect-Phase6-Recreated/' + name
        if preimage is None:
            probe = subprocess.run(['git', 'cat-file', '-e', source], cwd=str(ROOT),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert probe.returncode != 0
        else:
            raw = subprocess.check_output(['git', 'show', source], cwd=str(ROOT))
            assert hashlib.sha256(raw).hexdigest() == preimage['sha256']
            assert len(raw) == preimage['bytes']
            assert preimage['mode'] == 0o644
            listing = subprocess.check_output(['git', 'ls-tree', commit, '--',
                                              'KCMC-Connect-Phase6-Recreated/' + name], cwd=str(ROOT))
            assert listing.startswith(b'100644 blob ')
for item in INV['files']:
    name = item['path']
    assert INSTALLER.FILES[name] == {key:item[key] for key in ('sha256','bytes','baseline_sha256')}
    assert INSTALLER.GIT_SHAS[name] == item['git_sha']
    raw = (ROOT / 'KCMC-Connect-Phase6-Recreated' / name).read_bytes()
    assert len(raw) == item['bytes']
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    assert hashlib.sha1(('blob ' + str(len(raw)) + '\0').encode() + raw).hexdigest() == item['git_sha']
    if item['baseline_sha256'] is not None:
        assert INSTALLER.BASELINE_EXPECTATIONS[name] == {'bytes':item['baseline_bytes'], 'mode':int(item['baseline_mode'], 8)}
        old = subprocess.check_output(['git','show','ae004a659a7c2fb334296fa41f54dd5263f4d5c0:KCMC-Connect-Phase6-Recreated/' + name], cwd=str(ROOT))
        assert hashlib.sha256(old).hexdigest() == item['baseline_sha256']
        assert len(old) == item['baseline_bytes']
for item in INV['preserve_guards']:
    raw = (ROOT / 'KCMC-Connect-Phase6-Recreated' / item['path']).read_bytes()
    assert len(raw) == item['bytes']
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
SPEC = importlib.util.spec_from_file_location('content_review', str(HERE / 'content-review.py'))
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
assert REVIEW.SOURCE_COMMIT == INV['commit']
raw = (ROOT / REVIEW.SOURCE_PATH).read_bytes()
assert hashlib.sha1(('blob ' + str(len(raw)) + '\0').encode() + raw).hexdigest() == REVIEW.SOURCE_BLOB_SHA1
assert [event for event in json.loads(raw.decode('utf-8'))['events'] if event['id'] == REVIEW.CANDIDATE['id']] == [REVIEW.CANDIDATE]
SPEC = importlib.util.spec_from_file_location('content_insert', str(HERE / 'insert-hope-keepers.py'))
INSERT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSERT)
assert INSERT.CANDIDATE == REVIEW.CANDIDATE
assert INSERT.SOURCE_BLOB_SHA1 == REVIEW.SOURCE_BLOB_SHA1
assert INSERT.EXPECTED_HOST_SHA256 == 'dc3e671177f2d92096da7c0f5e174883492513261649508921a5ce9875ebe5a6'
assert INSERT.HOST_FILE == '/home/bobsome1/public_html/kcmc-connect/data/content.json'
assert INSERT.verify_source(str(ROOT / INSERT.SOURCE_PATH))['verified']
print('PASS: 16 release files, two complete baseline bundles, 13 preserved guards, and the read-only event candidate match reviewed source pins.')
