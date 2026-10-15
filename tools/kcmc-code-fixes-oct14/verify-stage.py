#!/usr/bin/env python3
"""Real PHP 8.2 syntax-only staged transaction in temporary public-code copies."""
from __future__ import print_function

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
from unittest import mock


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().with_name('installer.py')
    spec = importlib.util.spec_from_file_location('temporary_combined_installer', str(source))
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    engines = runner.load_engines()
    php = shutil.which('php')
    if php is None:
        raise RuntimeError('PHP 8.2 CLI required for the syntax-only fixture')
    with tempfile.TemporaryDirectory(prefix='kcmc-code-real-stage-') as temporary:
        root = Path(temporary)
        app = root / 'app'; app.mkdir(mode=0o700)
        before = {}
        for group in runner.GROUPS:
            engine = engines[group]
            engine.APP, engine.BACKUPS = app, root / ('private-' + group)
            engine.UID, engine.GID = os.getuid(), os.getgid()
            for index, path in enumerate(engine.PATHS):
                item = engine.FILES[path]
                after = (args.runtime_root / path).read_bytes()
                assert sha(after) == item['after_sha256']
                original = after
                for old, new in reversed(item['replacements']):
                    assert original.count(new.encode('utf-8')) == 1
                    original = original.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
                assert sha(original) == item['before_sha256']
                before[path] = original
                target = app / path
                target.parent.mkdir(mode=0o700, exist_ok=True)
                target.write_bytes(original)
                target.chmod(0o664 if index == 1 else 0o644)
        sentinel = app / 'untouched-synthetic-content.json'
        sentinel.write_bytes(b'{"synthetic":"never read by the runner"}\n')
        sentinel.chmod(0o600)
        # Force the ordinary PATH fallback in this temporary fixture only. The
        # released command has no argument or environment path override.
        with mock.patch.object(runner, 'PHP82_LOCATIONS', (str(root / 'absent-cpanel-php82'),
                                                         str(root / 'absent-cloudlinux-php82'))):
            results = runner.preflight(engines)
            assert all(result[0] == 'before' for result in results.values())
            assert engines['php'].PHP == os.path.abspath(php)
            assert all(not engine.BACKUPS.exists() for engine in engines.values())
            assert runner.apply_groups(engines) == 0
        for group in runner.GROUPS:
            engine = engines[group]
            for path in engine.PATHS:
                assert sha((app / path).read_bytes()) == engine.FILES[path]['after_sha256']
        stats = {path: (app / path).stat() for path in before}
        with mock.patch.object(runner, 'choose_php82_cli', side_effect=AssertionError('No runtime needed for no-op')):
            assert runner.apply_groups(engines) == 0
        for path, stat in stats.items():
            current = (app / path).stat()
            assert (current.st_ino,current.st_mtime_ns,current.st_ctime_ns,current.st_mode) == (stat.st_ino,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_mode)
        for group in ('skip','php'):
            engine = engines[group]
            names = runner.session_names(engine)
            assert len(names) == 1
            name = next(iter(names))
            assert engine.load(engine.BACKUPS / name)['phase'] == 'applied'
            engine.rollback(name)
            assert engine.load(engine.BACKUPS / name)['phase'] == 'rolled_back'
            for path in engine.PATHS:
                assert (app / path).read_bytes() == before[path]
        assert sentinel.read_bytes() == b'{"synthetic":"never read by the runner"}\n'
    print('PASS: actual PHP 8.2 PATH fallback and syntax-only staging; four-file apply, runtime-free no-op and independent rollback in temporary copies')


if __name__ == '__main__':
    main()
