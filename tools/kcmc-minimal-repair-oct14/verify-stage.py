#!/usr/bin/env python3
"""Actual PHP 8.2 lint plus transaction on synthetic temporary copies only."""
from __future__ import print_function

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().with_name('installer.py')
    spec = importlib.util.spec_from_file_location('synthetic_staged_installer', str(source))
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.inventory()
    php = shutil.which('php')
    if php is None:
        raise RuntimeError('PHP 8.2 CLI is required for synthetic staging proof')
    with tempfile.TemporaryDirectory(prefix='kcmc-minimal-actual-php-') as temporary:
        root = Path(temporary)
        app = root / 'app'
        app.mkdir(mode=0o700)
        installer.APP, installer.BACKUPS = app, root / 'private-repairs'
        installer.UID, installer.GID = os.getuid(), os.getgid()
        installer.PHP = php
        before = {}
        for index, path in enumerate(installer.PATHS):
            after = (args.runtime_root / path).read_bytes()
            reviewed = installer.FILES[path]
            assert installer.digest(after) == reviewed['after_sha256']
            data = after
            for old, new in reversed(reviewed['replacements']):
                assert data.count(new.encode('utf-8')) == 1
                data = data.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
            assert installer.digest(data) == reviewed['before_sha256']
            before[path] = data
            target = app / path
            target.parent.mkdir(mode=0o700, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o664 if index == 1 else 0o644)
        sentinel = app / 'untouched-private-synthetic.json'
        sentinel.write_bytes(b'{"synthetic":"never read by installer"}\n')
        sentinel.chmod(0o600)
        session = installer.apply()
        assert session is not None
        assert installer.load(session)['phase'] == 'applied'
        for path in installer.PATHS:
            assert installer.digest((app / path).read_bytes()) == installer.FILES[path]['after_sha256']
        assert installer.apply() is None
        installer.rollback(session.name)
        for path in installer.PATHS:
            assert (app / path).read_bytes() == before[path]
        assert sentinel.read_bytes() == b'{"synthetic":"never read by installer"}\n'
        assert installer.load(session)['phase'] == 'rolled_back'
    print('PASS: actual PHP 8.2 -n syntax-only staging, transaction, no-op and rollback; temporary copies only')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
