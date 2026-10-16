#!/usr/bin/env python3
"""Five bounded checks using current Python; no host or network calls."""
import sys
sys.dont_write_bytecode = True
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'kcmc-oct14-repo-metadata.py'
HELPER = Path(os.environ.get('KCMC_METADATA_HELPER', str(HERE / 'kcmc-scoped-release-oct13/align-repository.py')))
raw = SOURCE.read_bytes()
ast.parse(raw.decode(), feature_version=(3, 6))
spec = importlib.util.spec_from_file_location('metadata_diagnostic', str(SOURCE))
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                   GIT_AUTHOR_NAME='Synthetic', GIT_AUTHOR_EMAIL='synthetic@example.invalid',
                   GIT_COMMITTER_NAME='Synthetic', GIT_COMMITTER_EMAIL='synthetic@example.invalid')

with tempfile.TemporaryDirectory(prefix='kcmc-metadata-fixture-') as folder:
    repo = Path(folder) / 'repo'
    repo.mkdir()
    def git(*arguments):
        return subprocess.check_output(['git', '-C', str(repo)] + list(arguments),
                                       env=environment, stderr=subprocess.PIPE)
    git('init', '--initial-branch=main')
    escaped = 'escaped\n' + chr(27) + '[31m.txt'
    for name in ('tracked.txt', 'script.sh', escaped):
        (repo / name).write_text('Synthetic fixture, never read by metadata scan\n')
        (repo / name).chmod(0o644)
    (repo / 'script.sh').chmod(0o755)
    git('add', '.')
    git('commit', '-m', 'Synthetic fixture')
    helper = diagnostic.load_helper(HELPER)
    helper.REPO = repo
    helper.BASELINE_IDS = (git('rev-parse', 'HEAD').decode().strip(),)
    helper.TARGET = 'f' * 40
    git('remote', 'add', 'origin', helper.URL)
    original_read = Path.read_bytes
    def forbid_contents(path):
        if repo in path.parents and '.git' not in path.relative_to(repo).parts:
            raise AssertionError('Worktree content read')
        return original_read(path)
    with mock.patch.object(Path, 'read_bytes', forbid_contents):
        (repo / 'tracked.txt').chmod(0o664)
        (repo / 'script.sh').chmod(0o644)
        rows = {row['path']: row for row in diagnostic.scan(helper)['mismatches']}
        assert rows['tracked.txt']['mode'] == '0664'
        assert rows['script.sh']['expected_mode'] == '0755'
        print('Group-write and executable-mode differences: PASS')
        (repo / 'tracked.txt').chmod(0o644)
        (repo / 'script.sh').chmod(0o755)
        real_stat = os.lstat
        target = str(repo / 'tracked.txt')
        def changed_gid(path, *arguments, **options):
            info = real_stat(path, *arguments, **options)
            if str(path) == target:
                fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid')
                return types.SimpleNamespace(**{key: os.getgid() + 1 if key == 'st_gid'
                                                else getattr(info, key) for key in fields})
            return info
        with mock.patch.object(os, 'lstat', changed_gid):
            rows = {row['path']: row for row in diagnostic.scan(helper)['mismatches']}
            assert rows['tracked.txt']['gid'] == os.getgid() + 1
        print('Numeric group mismatch: PASS')
        (repo / escaped).chmod(0o664)
        encoded = json.dumps(diagnostic.scan(helper), ensure_ascii=True)
        assert chr(27) not in encoded and '\\n' in encoded and '\\u001b' in encoded
        (repo / escaped).chmod(0o644)
        print('Path control characters escaped: PASS')
        secret = 'SECRET_CONFIGURATION_VALUE_DO_NOT_PRINT'
        git('remote', 'set-url', 'origin', 'https://' + secret + '@github.com/bobhay75/Kcmc-connect.git')
        output = io.StringIO()
        saved_argv, saved_loader = sys.argv, diagnostic.load_helper
        try:
            sys.argv = ['diagnostic', 'verified-helper']
            diagnostic.load_helper = lambda path: helper
            with contextlib.redirect_stdout(output):
                assert diagnostic.main() == 1
        finally:
            sys.argv, diagnostic.load_helper = saved_argv, saved_loader
        assert secret not in output.getvalue() and json.loads(output.getvalue())['result'] == 'REFUSED'
        git('remote', 'set-url', 'origin', helper.URL)
        print('Credential/config value withheld: PASS')
        (repo / 'tracked.txt').unlink()
        (repo / 'tracked.txt').symlink_to(Path(folder) / 'SECRET_PRIVATE_TARGET')
        try:
            diagnostic.scan(helper)
        except diagnostic.Refusal as error:
            assert error.reason == 'Tracked file ownership/type/link requires review'
        else:
            raise AssertionError('Tracked symlink was accepted')
        print('Tracked symlink refused without target/content access: PASS')

print('PASS: five bounded checks; Python 3.6 grammar; no worktree contents, host or network calls.')
print('Diagnostic SHA256: ' + hashlib.sha256(raw).hexdigest())
