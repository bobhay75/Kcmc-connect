#!/usr/bin/env python3
"""Check scoped-release pins against immutable Git objects; never contact a host."""
from __future__ import print_function

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASELINE = '268bebca444bd4970bb4ecaa0d6eceb6a11988fd'
TARGET = '4225fce8968747ad4f828a9a36087b04fd020484'
PATHS = set(['admin/publication-designer.php',
             'assets/visuals/kcmc-building-retouched-20261009.jpg',
             'index.php', 'public-presentation.css', 'public-presentation.js', 'sw.js',
             'lib/bootstrap.php', 'assets/icons/icon-512.png', 'manifest.webmanifest',
             'assets/visuals/trunk-or-treat-2026.svg'])
GUARD_PATHS = set(['.htaccess', 'admin/audit.php', 'admin/health.php', 'admin/index.php',
                  'admin/timecards.php', 'assets/visuals/kcmc-building-2024.webp',
                  'assets/visuals/kcmc-ministry-group.jpg', 'assets/visuals/kcmc-stage-2014.webp',
                  'assets/visuals/kcmc-worship-2017.webp', 'care.php',
                  'member/login.php', 'member/timeclock.php',
                  'admin/publication-projects.php', 'admin/publication-media.php'])


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=HERE.parents[1])
    args = parser.parse_args()
    repository = args.repository.resolve()
    def git(*values):
        return subprocess.check_output(['git'] + list(values), cwd=str(repository))
    def source(ref, path):
        return git('show', ref + ':' + PREFIX + path)

    spec = importlib.util.spec_from_file_location('reviewed_release', str(HERE / 'installer.py'))
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.inventory()
    approved = json.loads((HERE / 'approved-inventory.json').read_text())
    baselines = json.loads((HERE / 'baseline-inventory.json').read_text())
    assert installer.COMMIT == approved['commit'] == TARGET
    assert approved['baseline_commit'] == BASELINE
    assert str(installer.APP_ROOT) == approved['app'] == baselines['app']
    assert installer.BASELINE_IDS == (BASELINE,)
    assert set(approved['files']) == set(installer.FILES) == installer.ALLOWED == PATHS
    assert set(approved['preserve_guards']) == set(installer.GUARDS) == GUARD_PATHS
    assert installer.BASELINES == baselines['baselines']
    assert set(installer.BASELINES) == set([BASELINE])
    assert installer.SOURCE_ROOT == ('https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' +
                                    TARGET + '/' + PREFIX)

    changed = git('diff', '--name-only', BASELINE, TARGET, '--', PREFIX).decode().splitlines()
    deleted = git('diff', '--name-only', '--diff-filter=D', BASELINE, TARGET, '--', PREFIX).decode().splitlines()
    assert set(changed) == set(PREFIX + path for path in PATHS)
    assert not deleted
    for path, pin in approved['files'].items():
        raw = source(TARGET, path)
        assert len(raw) == pin['bytes'] and sha256(raw) == pin['sha256']
        assert blob_sha(raw) == pin['git_sha'] == installer.GIT_SHAS[path]
        assert installer.FILES[path] == {key: pin[key] for key in ('bytes', 'sha256', 'baseline_sha256')}
        assert pin['url'] == installer.SOURCE_ROOT + path
        listing = git('ls-tree', TARGET, '--', PREFIX + path)
        assert listing.startswith(b'100644 blob ')
        old_pin = installer.BASELINES[BASELINE][path]
        if old_pin is None:
            probe = subprocess.call(['git', 'cat-file', '-e', BASELINE + ':' + PREFIX + path],
                                    cwd=str(repository), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            assert probe != 0 and pin['baseline_sha256'] is None
            assert pin['baseline_bytes'] is None and pin['baseline_mode'] is None
        else:
            old = source(BASELINE, path)
            assert len(old) == old_pin['bytes'] == pin['baseline_bytes']
            assert sha256(old) == old_pin['sha256'] == pin['baseline_sha256']
            assert old_pin['mode'] == pin['baseline_mode'] == 0o644
            assert installer.BASELINE_EXPECTATIONS[path] == {'bytes':len(old), 'mode':0o644}
            assert git('ls-tree', BASELINE, '--', PREFIX + path).startswith(b'100644 blob ')
        assert (repository / PREFIX / path).read_bytes() == raw
    assert set(installer.BASELINE_EXPECTATIONS) == PATHS - set(['assets/visuals/kcmc-building-retouched-20261009.jpg', 'assets/visuals/trunk-or-treat-2026.svg'])
    for path, pin in approved['preserve_guards'].items():
        raw = source(TARGET, path)
        assert source(BASELINE, path) == raw
        assert len(raw) == pin['bytes'] and sha256(raw) == pin['sha256'] == installer.GUARDS[path]
        assert blob_sha(raw) == pin['git_sha']
        assert pin['mode'] == 0o644
        assert (repository / PREFIX / path).read_bytes() == raw
    print('PASS: ten exact release files, one complete baseline, fourteen unchanged guards; no APP deletions.')


if __name__ == '__main__':
    main()
