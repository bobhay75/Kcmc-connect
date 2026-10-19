#!/usr/bin/env python3
"""Exercise the offline welcome package and read-only host refusal boundaries."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT/'tools/prepare-welcome-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    manifest, entries = release.build(work/'first.zip')
    release.build(work/'second.zip')
    assert (work/'first.zip').read_bytes() == (work/'second.zip').read_bytes(), 'Reproducible review archive'
    stage = work/'stage'
    with zipfile.ZipFile(work/'first.zip') as archive:
        archive.extractall(stage)

    def check(app, expected):
        result = subprocess.run([sys.executable, '-I', '-B', str(stage/'check-release.py'), str(app)], capture_output=True, text=True)
        assert (result.returncode == 0) == expected, result.stdout+result.stderr
        return result.stdout

    for variant in ('main', 'livecalendar'):
        app = work/variant
        for n in release.MODIFIED:
            target=app/n;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(entries['before/'+variant+'/'+n])
        for n in manifest['variants'][variant]['guards']:
            data=release.image(release.BASE,n)
            if variant=='livecalendar' and n=='public-presentation.css':
                data=release.git('show',release.BASE+':tools/kcmc-follow-up-oct18/evidence/public/livecalendar/'+n)
            target=app/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        assert 'CHECK '+variant+' before' in check(app,True)
        for n in release.MODIFIED+release.ADDED:
            target=app/n;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(entries['after/'+n])
            if n!=release.ADDED[-1]: check(app,False)  # Incomplete/mixed tuples fail closed.
        assert 'CHECK '+variant+' after' in check(app,True)
        target=app/'index.php';raw=target.read_bytes()
        target.write_bytes(raw+b'changed');check(app,False);target.write_bytes(raw)
        target.chmod(0o755);check(app,False);target.chmod(0o644)
        outside=work/(variant+'-outside.php');outside.write_bytes(raw)
        target.unlink();target.symlink_to(outside);check(app,False)
        target.unlink();target.write_bytes(raw)
        css=app/'public-presentation.css';data=css.read_bytes()
        css.write_bytes(data+b'changed');check(app,False);css.write_bytes(data)
        assert 'after' in check(app,True)
        # Demonstrate the exact recorded rollback tuple, including removal of additions.
        for n in release.MODIFIED: (app/n).write_bytes(entries['before/'+variant+'/'+n])
        for n in release.ADDED: (app/n).unlink()
        assert 'before' in check(app,True)
    (stage/'manifest.json').write_bytes((stage/'manifest.json').read_bytes()+b' ')
    check(work/'main',False)
print('PASS: reproducible archive, both variants, before/after/rollback tuples, tampering, mixed states, unsafe modes, symlinks and guard refusal')
