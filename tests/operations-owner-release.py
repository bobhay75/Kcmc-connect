"""Exercise the exact release repair against synthetic installed copies only."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'tools/release-operations-owner.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
os.environ.pop('KCMC_OPERATIONS_OWNER_USER_ID', None)

def refused(fn, label):
    try:
        fn()
    except RuntimeError:
        print('PASS:', label)
        return
    raise AssertionError(label)

with tempfile.TemporaryDirectory(prefix='kcmc-operations-release-') as tmp:
    work = Path(tmp).resolve()
    app = work / 'app'
    shutil.copytree(ROOT / 'KCMC-Connect-Phase6-Recreated', app)
    for name in release.FILES[1:]:
        p = app / name
        p.write_bytes(p.read_bytes().replace(release.GUARD, b'', 1).replace(release.ANCHOR, release.ANCHOR + b'// Synthetic installed customization.\n', 1))
    (app / release.HELPER).unlink()
    original = {p.relative_to(app).as_posix(): p.read_bytes() for p in app.rglob('*') if p.is_file()}
    refused(lambda: release.plan(app), 'unset owner configuration fails closed')
    with (app / '.htaccess').open('ab') as f:
        f.write(b'\nSetEnv KCMC_OPERATIONS_OWNER_USER_ID synthetic-owner\n')
    original['.htaccess'] = (app / '.htaccess').read_bytes()
    refused(lambda: release.prepare(app, app / 'unsafe-backup'), 'backup inside app refused')
    backup = work / 'backup'
    release.prepare(app, backup)
    assert all((app / name).read_bytes() == data for name, data in original.items())
    assert not (app / release.HELPER).exists()
    print('PASS: preparing never changes installed files')
    staged = backup / 'stage/admin/operations.php'
    good = staged.read_bytes()
    staged.write_bytes(good + b'changed')
    refused(lambda: release.apply(app, backup), 'stage tampering refused before any install')
    staged.write_bytes(good)
    live = app / 'admin/health.php'
    before = live.read_bytes()
    live.write_bytes(before + b'changed')
    refused(lambda: release.apply(app, backup), 'concurrent installed change refused')
    live.write_bytes(before)
    # A write failure restores all files already replaced.
    write = release.atomic_write
    def failing_write(path, data, mode):
        if path.name == 'health.php' and data != before:
            raise OSError('Synthetic installation failure')
        write(path, data, mode)
    release.atomic_write = failing_write
    try:
        release.apply(app, backup)
        raise AssertionError('Expected synthetic failure')
    except OSError:
        pass
    finally:
        release.atomic_write = write
    assert not (app / release.HELPER).exists()
    assert all((app / name).read_bytes() == data for name, data in original.items())
    print('PASS: interrupted install rolls back exact installed bytes')
    backup = work / 'second-backup'
    release.prepare(app, backup)
    release.apply(app, backup)
    for name, data in original.items():
        actual = (app / name).read_bytes()
        assert actual == (release.guard_route(data) if name in release.FILES else data), name
    assert (app / release.HELPER).read_bytes() == release.helper_bytes()
    assert all(a == b for a, b, mode in release.plan(app).values())
    refused(lambda: release.apply(app, backup), 'already-applied release refused')
    for data in [b'<?php\necho "output";\n' + release.ANCHOR,
                 b'<?php\n' + release.ANCHOR + b'kcmc_require_operations_owner();\n']:
        refused(lambda: release.guard_route(data), 'unexpected/partial prologue refused')
    print('PASS: exactly eleven guard files; installed customizations, public/private content and all other routes preserved; check is idempotent')
