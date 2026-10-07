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
print('PASS: 16 release files, six host preimages, 13 preserved guards, and the read-only event candidate match reviewed source pins.')
