#!/usr/bin/env python3
"""Real PHP8.2 syntax/transaction fixture; temporary source and synthetic stores only."""
from __future__ import print_function
import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def sha(data): return hashlib.sha256(data).hexdigest()


def identity(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextlib.contextmanager
def fixture(php):
    with tempfile.TemporaryDirectory(prefix='kcmc-owner-real-php82-') as directory:
        root = Path(directory); app = root / 'app'; app.mkdir()
        spec = importlib.util.spec_from_file_location('real_owner_wrapper', str(HERE / 'installer.py'))
        wrapper = importlib.util.module_from_spec(spec); spec.loader.exec_module(wrapper)
        engines = wrapper.load_engines(); module = engines['main93']
        module.APP = app; module.BACKUPS = root / 'private'; module.UID = os.getuid(); module.GID = os.getgid()
        wrapper.load_engines = lambda: engines
        wrapper.php82_candidates = lambda: [php]
        originals = {}
        for path in module.PATHS:
            target = app / path; target.parent.mkdir(parents=True, exist_ok=True)
            content = (HERE / 'evidence/main93' / path).read_bytes(); originals[path] = content
            target.write_bytes(content); target.chmod(0o664 if path == 'admin/users.php' else 0o644)
        bootstrap = app / 'lib/bootstrap.php'
        bootstrap.write_bytes((HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()); bootstrap.chmod(0o644)
        sentinels = {'lib/bootstrap.php': (bootstrap.read_bytes(), identity(bootstrap))}
        for path in ['config.php', 'data/content.json', 'data/private/users.json', 'data/private/prayers.json',
                'lib/session-lifetime.php', 'member/login.php', 'member/password.php', 'member/reset-password.php',
                'index.php', 'public-presentation.css', 'sw.js', '.git/HEAD']:
            target = app / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'synthetic owner bytes retained\n'); target.chmod(0o600)
            sentinels[path] = (target.read_bytes(), identity(target))
        yield root, app, wrapper, module, originals, sentinels


def cli(wrapper, *args):
    previous = sys.argv; output = io.StringIO()
    try:
        sys.argv = ['installer.py'] + list(args)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output): result = wrapper.main()
    finally: sys.argv = previous
    return result, output.getvalue()


def preserve(app, sentinels, allow_bootstrap=False):
    for path, (content, old) in sentinels.items():
        if allow_bootstrap and path == 'lib/bootstrap.php': continue
        assert (app / path).read_bytes() == content and identity(app / path) == old, path


def changed_bootstrap(root, app):
    replacement = root / 'concurrent-bootstrap.php'
    replacement.write_bytes(b'<?php // synthetic external bootstrap edit retained\n'); replacement.chmod(0o644)
    os.replace(str(replacement), str(app / 'lib/bootstrap.php'))


def no_success(text):
    for marker in ['REPAIRED ', 'ALREADY_REPAIRED;', 'ROLLED_BACK ', 'CHECK READY', 'CHECK ALREADY_REPAIRED']:
        assert marker not in text, text


def basic(php):
    with fixture(php) as (root, app, wrapper, module, originals, sentinels):
        selected, version = wrapper.choose_php82_cli(); assert selected == php
        result, output = cli(wrapper, 'check'); assert result == 0 and 'CHECK READY' in output, output
        result, output = cli(wrapper, 'apply'); assert result == 0 and 'REPAIRED ' in output, output
        session = next(module.BACKUPS.glob('repair-*'))
        for path in module.PATHS: assert sha((app / path).read_bytes()) == module.FILES[path]['after_sha256']
        installed = {path: identity(app / path) for path in module.PATHS}
        result, output = cli(wrapper, 'apply'); assert result == 0 and 'ALREADY_REPAIRED;' in output, output
        for path, old in installed.items(): assert identity(app / path) == old
        result, output = cli(wrapper, 'rollback', '--variant', 'main93', '--session', session.name)
        assert result == 0 and 'ROLLED_BACK ' in output, output
        for path, content in originals.items(): assert (app / path).read_bytes() == content
        assert (app / 'admin/users.php').stat().st_mode & 0o777 == 0o664
        preserve(app, sentinels)
        print('REAL_PHP_82 selection/stage/four-file apply/no-op/rollback/bootstrap/private preservation PASS (' + version + ')')


def drift_after_rename(php):
    with fixture(php) as (root, app, wrapper, module, originals, sentinels):
        rename = module.replace
        def drift(source, target, **kwargs):
            result = rename(source, target, **kwargs)
            if source == 'stage-0.code': changed_bootstrap(root, app)
            return result
        module.replace = drift
        result, output = cli(wrapper, 'apply'); assert result == 1, output; no_success(output)
        session = next(module.BACKUPS.glob('repair-*')); value = module.load(session)
        assert value['phase'] == 'manual_review' and module.PATHS[0] in value['uncertain']
        assert b'synthetic external bootstrap edit retained' in (app / 'lib/bootstrap.php').read_bytes()
        preserve(app, sentinels, allow_bootstrap=True)
        print('REAL_PHP_82 post-rename prerequisite loss/uncertain journal/manual review PASS')


def drift_after_applied_journal(php):
    with fixture(php) as (root, app, wrapper, module, originals, sentinels):
        journal = module.journal
        def drift(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': changed_bootstrap(root, app)
            return result
        module.journal = drift
        result, output = cli(wrapper, 'apply'); assert result == 1, output; no_success(output)
        session = next(module.BACKUPS.glob('repair-*')); value = module.load(session)
        assert value['phase'] == 'applied' and value['intent'] is None and not value['uncertain']
        for path in module.PATHS: module.verify_lease(path, value['files'][path]['installed'])
        preserve(app, sentinels, allow_bootstrap=True)
        print('REAL_PHP_82 late applied-journal prerequisite loss/no success/all installed leases retained PASS')


def drift_during_rollback(php):
    with fixture(php) as (root, app, wrapper, module, originals, sentinels):
        result, output = cli(wrapper, 'apply'); assert result == 0, output
        session = next(module.BACKUPS.glob('repair-*')); rename = module.replace
        def drift(source, target, **kwargs):
            result = rename(source, target, **kwargs)
            if source.startswith('restore-'): changed_bootstrap(root, app)
            return result
        module.replace = drift
        result, output = cli(wrapper, 'rollback', '--variant', 'main93', '--session', session.name)
        assert result == 1, output; no_success(output)
        value = module.load(session)
        assert value['phase'] == 'manual_review' and module.PATHS[-1] in value['uncertain']
        for path in module.PATHS[:-1]: module.verify_lease(path, value['files'][path]['installed'])
        assert (app / module.PATHS[-1]).read_bytes() == originals[module.PATHS[-1]]
        preserve(app, sentinels, allow_bootstrap=True)
        print('REAL_PHP_82 rollback prerequisite loss/uncertain original/other installed leases retained PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--php', default=shutil.which('php')); args = parser.parse_args()
    if not args.php: raise ValueError('A real PHP8.2 CLI is required for this temporary fixture')
    php = str(Path(args.php).resolve())
    basic(php); drift_after_rename(php); drift_after_applied_journal(php); drift_during_rollback(php)
    return 0


if __name__ == '__main__': raise SystemExit(main())
