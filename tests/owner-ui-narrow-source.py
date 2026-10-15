#!/usr/bin/env python3
"""Exact reversible A7/A5 deltas against reviewed source; no host calls."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '93c72f4fc430d311e01108d3a30d0561bb701c9d'
FIXTURES = {
    'push-owner-link-reviewed.json': ('b6ca2c3e1e218627643aa9d5962ccc11b535242bb7e4e5c25303afd776f32042', {'member/notifications.php'}),
    'owner-account-guard-reviewed.json': ('d872e4deb60baca4cade936412c9706294a3e8a5a2e671acddc59493ca52e527', {'lib/password-lifecycle.php', 'admin/users.php', 'admin/password-resets.php'}),
}

def check(ok, message):
    if not ok: raise AssertionError(message)
    print('PASS:', message)

def run(git_source):
    all_paths = set()
    for name, (sha, expected_paths) in FIXTURES.items():
        raw = (ROOT / 'tests/fixtures' / name).read_bytes()
        check(hashlib.sha256(raw).hexdigest() == sha, name + ': exact fixture bytes')
        fixture = json.loads(raw)
        check(set(fixture) == {'source_commit', 'files'} and fixture['source_commit'] == BASE, name + ': pinned source and schema')
        check(set(fixture['files']) == expected_paths, name + ': exact runtime scope')
        check(not (all_paths & expected_paths), name + ': independent repair scope')
        all_paths.update(expected_paths)
        for path, entry in fixture['files'].items():
            check(set(entry) == {'before_sha256', 'after_sha256', 'replacements'}, path + ': explicit byte pins')
            before = subprocess.check_output(['git', '-C', str(git_source), 'show', BASE + ':' + PREFIX + path])
            check(hashlib.sha256(before).hexdigest() == entry['before_sha256'], path + ': canonical exact source')
            expected = before
            for old, new in entry['replacements']:
                check(expected.count(old.encode()) == 1, path + ': one forward anchor')
                expected = expected.replace(old.encode(), new.encode(), 1)
            actual = (ROOT / PREFIX / path).read_bytes()
            check(actual == expected and hashlib.sha256(actual).hexdigest() == entry['after_sha256'], path + ': only enumerated target bytes')
            for old, new in reversed(entry['replacements']):
                check(actual.count(new.encode()) == 1, path + ': one reverse anchor')
                actual = actual.replace(new.encode(), old.encode(), 1)
            check(actual == before, path + ': exact reversible preimage')
    check(len(all_paths) == 4, 'A7 and A5 together touch exactly four existing runtime files')
    # Existing authorization identity and role policy remain authoritative. This
    # helper is deliberately reused rather than replaced by a second owner ID rule.
    owner_helper = (ROOT / PREFIX / 'lib/operations-owner.php').read_bytes()
    check(hashlib.sha256(owner_helper).hexdigest() == '03989956a73a0f5d995e6eb24fe64d722ed7b47558f94103d7cf79778ac2c2ef', 'operations owner guard remains exact')
    sender = (ROOT / PREFIX / 'admin/push.php').read_bytes()
    canonical_sender = subprocess.check_output(['git', '-C', str(git_source), 'show', BASE + ':' + PREFIX + 'admin/push.php'])
    check(sender == canonical_sender, 'push destination authorization and sender remain byte-identical')
    print('Narrow owner UI/account source proofs passed.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--git-source', type=Path, default=ROOT)
    run(parser.parse_args().git_source)
