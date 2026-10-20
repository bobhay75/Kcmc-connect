#!/usr/bin/env python3
"""Exercise the exact branding bundle and both guarded host variants offline."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('brand_release',ROOT/'tools/prepare-brand-release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

with tempfile.TemporaryDirectory() as td:
    work=Path(td)
    manifest,entries=release.build(work/'first.zip')
    release.build(work/'second.zip')
    assert (work/'first.zip').read_bytes()==(work/'second.zip').read_bytes(), 'Reproducible archive'
    assert not any(Path(name).name=='content.json' or '__pycache__' in name for name in entries), 'No live store or bytecode in bundle'
    stage=work/'stage'
    with zipfile.ZipFile(work/'first.zip') as archive: archive.extractall(stage)

    def check(app,expected):
        result=subprocess.run([sys.executable,'-I','-B',str(stage/'check-release.py'),str(app)],capture_output=True,text=True)
        assert (result.returncode==0)==expected,result.stdout+result.stderr
        return result.stdout

    for variant in ('main','livecalendar'):
        app=work/variant
        for name in release.MODIFIED:
            target=app/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(entries['before/'+name])
        for name in release.GUARDS:
            target=app/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(release.guard(variant,name))
        assert 'CHECK '+variant+' before' in check(app,True)
        for name in release.ADDED+release.MODIFIED:
            target=app/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(entries['after/'+name])
            if name!=release.MODIFIED[-1]: check(app,False)
        assert 'CHECK '+variant+' after' in check(app,True)
        target=app/'index.php';raw=target.read_bytes()
        target.write_bytes(raw+b'changed');check(app,False);target.write_bytes(raw)
        target.chmod(0o755);check(app,False);target.chmod(0o644)
        outside=work/(variant+'-outside.php');outside.write_bytes(raw)
        target.unlink();target.symlink_to(outside);check(app,False)
        target.unlink();target.write_bytes(raw)
        css=app/'public-presentation.css';raw_css=css.read_bytes()
        css.write_bytes(raw_css+b'changed');check(app,False);css.write_bytes(raw_css)
        payload=stage/'after/index.php';payload_raw=payload.read_bytes()
        payload.write_bytes(payload_raw+b'changed');check(app,False);payload.write_bytes(payload_raw)
        publisher=stage/'content-publication/publish.py';publisher_raw=publisher.read_bytes()
        publisher.write_bytes(publisher_raw+b'changed');check(app,False);publisher.write_bytes(publisher_raw)
        assert 'after' in check(app,True)
        for name in release.MODIFIED: (app/name).write_bytes(entries['before/'+name])
        for name in release.ADDED: (app/name).unlink()
        assert 'before' in check(app,True)
    (stage/'manifest.json').write_bytes((stage/'manifest.json').read_bytes()+b' ')
    check(work/'main',False)
print('PASS: reproducible 13-file branding bundle; main/livecalendar before/after/rollback; mixed states, source/payload/guard tampering, unsafe modes and symlinks refused')
