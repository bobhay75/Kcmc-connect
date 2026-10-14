#!/usr/bin/env python3
"""Scoped, offline Operations guard repair. Check is read-only; release is explicit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROUTES = ['operations.php', 'health.php', 'audit.php', 'audit-export.php',
          'push.php', 'backup.php', 'restore.php', 'timecards.php',
          'timecards-export.php', 'timecards-print.php']
HELPER = 'lib/operations-owner.php'
FILES = [HELPER] + ['admin/' + name for name in ROUTES]
ANCHOR = b"require_once __DIR__ . '/../lib/bootstrap.php';\n"
GUARD = b"require_once __DIR__ . '/../lib/operations-owner.php';\nkcmc_require_operations_owner();\n"
HELPER_SHA = '03989956a73a0f5d995e6eb24fe64d722ed7b47558f94103d7cf79778ac2c2ef'

def check(ok, message):
    if not ok:
        raise RuntimeError(message)

def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None

def safe_file(root, name):
    p = root / name
    check(p.resolve() == p and not p.is_symlink(), 'Symlink/noncanonical target refused: ' + name)
    return p

def guard_route(data):
    prefixes = [b'<?php\n', b'<?php\ndeclare(strict_types=1);\n']
    check(any(data.startswith(p + ANCHOR) for p in prefixes), 'Unexpected PHP entry prologue')
    check(data.count(ANCHOR) == 1, 'Ambiguous bootstrap anchor')
    if GUARD in data:
        check(data.count(GUARD) == 1 and ANCHOR + GUARD in data, 'Misplaced owner guard')
        return data
    check(b'operations-owner.php' not in data and b'kcmc_require_operations_owner' not in data,
          'Partial or unexpected owner guard')
    result = data.replace(ANCHOR, ANCHOR + GUARD, 1)
    check(result.replace(GUARD, b'', 1) == data, 'Unrelated route bytes changed')
    return result

def helper_bytes():
    data = (Path(__file__).resolve().parents[1] / 'KCMC-Connect-Phase6-Recreated' / HELPER).read_bytes()
    check(digest(data) == HELPER_SHA, 'Reviewed helper hash mismatch')
    return data

def plan(root):
    check(root.is_dir(), 'Application root missing')
    ht = safe_file(root, '.htaccess').read_bytes()
    configured = bool(os.environ.get('KCMC_OPERATIONS_OWNER_USER_ID', '').strip()) or bool(
        re.search(rb'^\s*SetEnv\s+KCMC_OPERATIONS_OWNER_USER_ID\s+[^\s#]+\s*$', ht, re.M))
    check(configured, 'Owner setting missing; verify PHP web-request identity before release')
    helper = helper_bytes()
    result = {}
    for name in FILES:
        p = safe_file(root, name)
        before = p.read_bytes() if p.exists() else None
        if name == HELPER:
            check(before is None or before == helper, 'Existing owner helper differs; review required')
            after = helper
        else:
            check(before is not None, 'Missing Operations route: ' + name)
            after = guard_route(before)
        result[name] = (before, after, stat.S_IMODE(p.stat().st_mode) if p.exists() else 0o644)
    return result

def lint(path):
    result = subprocess.run([os.environ.get('PHP_BIN', 'php'), '-l', str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    check(result.returncode == 0, 'PHP lint failed: ' + path.name)

def outside(root, backup):
    check(backup != root and root not in backup.parents, 'Backup must be outside application root')
    check(not backup.is_symlink() and backup.resolve() == backup, 'Invalid backup path')

def prepare(root, backup):
    outside(root, backup)
    changes = plan(root)  # Validate every route before creating anything.
    backup.mkdir(mode=0o700, parents=False, exist_ok=False)
    m = {'root': str(root), 'status': 'prepared', 'files': {}}
    for name, (before, after, mode) in changes.items():
        for folder, data in [('before', before), ('stage', after)]:
            if data is None:
                continue
            p = backup / folder / name
            p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            p.write_bytes(data)
            os.chmod(str(p), 0o600)
            check(p.read_bytes() == data, 'Backup/stage readback failed')
        lint(backup / 'stage' / name)
        m['files'][name] = {'before': digest(before), 'after': digest(after), 'mode': mode}
    (backup / 'manifest.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
    print('Prepared Operations-only backup and stage; live files unchanged.')

def atomic_write(path, data, mode):
    fd, temp = tempfile.mkstemp(prefix='.owner-release-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def apply(root, backup):
    outside(root, backup)
    m = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    check(m['root'] == str(root) and m['status'] == 'prepared', 'Wrong or already-used release')
    check(set(m['files']) == set(FILES), 'Unexpected file scope')
    current = plan(root)
    for name, (before, after, mode) in current.items():
        record = m['files'][name]
        check(digest(before) == record['before'] and mode == record['mode'], 'Installed file changed: ' + name)
        check(digest(after) == record['after'], 'Unexpected target: ' + name)
        check(safe_file(backup, 'stage/' + name).read_bytes() == after, 'Staged file changed: ' + name)
        if before is not None:
            check(safe_file(backup, 'before/' + name).read_bytes() == before, 'Backup changed: ' + name)
        lint(backup / 'stage' / name)
    touched = []
    try:
        for name in FILES:  # Helper first; each route then begins denying non-owners.
            before, after, mode = current[name]
            p = safe_file(root, name)
            check((p.read_bytes() if p.exists() else None) == before, 'Concurrent file change: ' + name)
            if before != after:
                atomic_write(p, after, mode)
                touched.append(name)
            check(p.read_bytes() == after, 'Installed readback failed: ' + name)
    except BaseException:
        for name in reversed(touched):
            before, after, mode = current[name]
            if before is None:
                (root / name).unlink()
            else:
                atomic_write(root / name, before, mode)
        m['status'] = 'rolled_back'
        (backup / 'manifest.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
        raise
    m['status'] = 'applied'
    (backup / 'manifest.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
    print('Applied exact Operations guard scope; backup retained. Verify authenticated owner/non-owner HTTP access.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--prepare', type=Path, metavar='NEW_PRIVATE_BACKUP')
    action.add_argument('--apply', type=Path, metavar='PREPARED_BACKUP')
    args = parser.parse_args()
    os.umask(0o077)
    root = args.root.absolute()
    check(root.resolve() == root, 'Noncanonical application root')
    if args.prepare:
        prepare(root, args.prepare.absolute())
    elif args.apply:
        apply(root, args.apply.absolute())
    else:
        result = plan(root)
        print('CHECK ONLY:', sum(before != after for before, after, mode in result.values()), 'files need guard repair; no writes.')

if __name__ == '__main__':
    main()
