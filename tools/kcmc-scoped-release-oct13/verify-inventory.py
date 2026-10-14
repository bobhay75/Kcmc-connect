#!/usr/bin/env python3
"""Verify public pins and deferred owner boundaries from immutable Git only."""
from __future__ import print_function
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASELINE_IDS = ('268bebca444bd4970bb4ecaa0d6eceb6a11988fd', '4225fce8968747ad4f828a9a36087b04fd020484')
TARGET = '154b779a0ea3d27a11300bfe0454f8a7c4aca355'
PUBLIC = set(['admin/publication-designer.php', 'assets/icons/icon-512.png',
              'assets/visuals/kcmc-building-retouched-20261009.jpg', 'assets/visuals/trunk-or-treat-2026.svg',
              'index.php', 'lib/bootstrap.php', 'manifest.webmanifest', 'public-presentation.css',
              'public-presentation.js', 'sw.js'])
OWNER = set('admin/' + name for name in ['audit-export.php', 'audit.php', 'backup.php', 'health.php',
             'operations.php', 'push.php', 'restore.php', 'timecards-export.php', 'timecards-print.php', 'timecards.php'])
ABSENT = set(['lib/operations-owner.php'])
GUARD_PATHS = OWNER | set(['.htaccess', 'admin/index.php', 'admin/publication-projects.php',
              'admin/publication-media.php', 'assets/visuals/kcmc-building-2024.webp',
              'assets/visuals/kcmc-ministry-group.jpg', 'assets/visuals/kcmc-stage-2014.webp',
              'assets/visuals/kcmc-worship-2017.webp', 'care.php', 'member/login.php', 'member/timeclock.php'])


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=HERE.parents[1])
    repository = parser.parse_args().repository.resolve()
    def git(*values):
        return subprocess.check_output(['git'] + list(values), cwd=str(repository))
    def source(ref, path):
        return git('show', ref + ':' + PREFIX + path)
    def missing(ref, path):
        return subprocess.call(['git', 'cat-file', '-e', ref + ':' + PREFIX + path],
                               cwd=str(repository), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0

    spec = importlib.util.spec_from_file_location('reviewed_public_release', str(HERE / 'installer.py'))
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.inventory()
    alignment_spec = importlib.util.spec_from_file_location('reviewed_checkout_alignment',
                                                          str(HERE / 'align-repository.py'))
    alignment = importlib.util.module_from_spec(alignment_spec)
    alignment_spec.loader.exec_module(alignment)
    assert alignment.BASELINE_IDS == BASELINE_IDS
    assert alignment.TARGET == TARGET
    assert str(alignment.REPO) == '/home/bobsome1/repositories/Kcmc-connect-live'
    approved = json.loads((HERE / 'approved-inventory.json').read_text())
    baseline_inventory = json.loads((HERE / 'baseline-inventory.json').read_text())
    assert installer.COMMIT == approved['commit'] == TARGET
    assert approved['baseline_commit'] == BASELINE_IDS[0]
    assert tuple(approved['baseline_commits']) == installer.BASELINE_IDS == BASELINE_IDS
    assert installer.BASELINES == baseline_inventory['baselines']
    assert set(installer.BASELINES) == set(BASELINE_IDS)
    assert str(installer.APP_ROOT) == approved['app'] == baseline_inventory['app']
    assert set(installer.FILES) == installer.ALLOWED == set(approved['files']) == PUBLIC
    assert set(installer.GUARDS) == set(approved['preserve_guards']) == GUARD_PATHS
    assert installer.OWNER_GUARD_PATHS == OWNER
    assert installer.ABSENT_GUARDS == set(approved['preserve_absent_guards']) == ABSENT
    assert set(approved['excluded_owner_paths']) == OWNER | ABSENT
    assert not PUBLIC.intersection(OWNER | ABSENT | GUARD_PATHS)
    assert installer.SOURCE_ROOT == 'https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' + TARGET + '/' + PREFIX
    changed = git('diff', '--name-only', BASELINE_IDS[0], TARGET, '--', PREFIX).decode().splitlines()
    deleted = git('diff', '--name-only', '--diff-filter=D', BASELINE_IDS[0], TARGET, '--', PREFIX).decode().splitlines()
    assert set(changed) == set(PREFIX + path for path in PUBLIC | OWNER | ABSENT)
    assert not deleted
    for path, pin in approved['files'].items():
        raw = source(TARGET, path)
        assert len(raw) == pin['bytes'] and sha256(raw) == pin['sha256']
        assert blob_sha(raw) == pin['git_sha'] == installer.GIT_SHAS[path]
        assert installer.FILES[path] == {key:pin[key] for key in ('bytes', 'sha256', 'baseline_sha256')}
        assert pin['url'] == installer.SOURCE_ROOT + path
        assert git('ls-tree', TARGET, '--', PREFIX + path).startswith(b'100644 blob ')
        assert (repository / PREFIX / path).read_bytes() == raw
    for ref, bundle in installer.BASELINES.items():
        assert set(bundle) == PUBLIC
        for path, pin in bundle.items():
            if pin is None:
                assert missing(ref, path)
            else:
                raw = source(ref, path)
                assert len(raw) == pin['bytes'] and sha256(raw) == pin['sha256'] and pin['mode'] == 0o644
                assert git('ls-tree', ref, '--', PREFIX + path).startswith(b'100644 blob ')
        assert sum(pin is None for pin in bundle.values()) == (2 if ref == BASELINE_IDS[0] else 0)
    for path, pin in approved['files'].items():
        old = installer.BASELINES[BASELINE_IDS[0]][path]
        if old is None:
            assert pin['baseline_sha256'] is None and pin['baseline_bytes'] is None and pin['baseline_mode'] is None
        else:
            assert pin['baseline_sha256'] == old['sha256'] and pin['baseline_bytes'] == old['bytes']
            assert pin['baseline_mode'] == old['mode']
            assert installer.BASELINE_EXPECTATIONS[path] == {'bytes':old['bytes'], 'mode':old['mode']}
    assert set(installer.BASELINE_EXPECTATIONS) == set(p for p,v in installer.BASELINES[BASELINE_IDS[0]].items() if v is not None)
    # Guards deliberately preserve old host bytes, independently of newer checkout owner files.
    for path, pin in approved['preserve_guards'].items():
        assert pin['source_commit'] == BASELINE_IDS[0]
        for ref in BASELINE_IDS:
            raw = source(ref, path)
            assert len(raw) == pin['bytes'] and sha256(raw) == pin['sha256'] == installer.GUARDS[path]
            assert blob_sha(raw) == pin['git_sha'] and pin['mode'] == 0o644
            assert git('ls-tree', ref, '--', PREFIX + path).startswith(b'100644 blob ')
    for path in ABSENT:
        assert all(missing(ref, path) for ref in BASELINE_IDS)
        assert not missing(TARGET, path)
    for path in OWNER:
        assert source(BASELINE_IDS[0], path) != source(TARGET, path)
    print('PASS: public10 pins, two complete baselines, old21 guards/helper absence, excluded owner11 and no APP deletions.')


if __name__ == '__main__':
    main()
