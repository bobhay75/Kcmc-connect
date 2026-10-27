#!/usr/bin/env python3
"""Run local host-overlay checks using an owner-supplied, hash-verified snapshot."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

if len(sys.argv)!=2: raise SystemExit('Usage: test-host-overlay.py SNAPSHOT_DIR')
snapshot=Path(sys.argv[1]).resolve(strict=True)
script=Path(__file__).resolve().with_name('host-overlay.py')
with tempfile.TemporaryDirectory(prefix='kcmc-overlay-test-') as tmp:
    out=Path(tmp)/'out'
    subprocess.run([sys.executable,str(script),str(snapshot),str(out)],check=True,stdout=subprocess.DEVNULL)
    home=(out/'index.php').read_text(); old=(snapshot/'index.php').read_text()
    assert 'kcmc-gold-hero.webp' in home and 'kcmc-gold-hero.webp' in old
    assert 'member/timeclock.php' not in home and 'My account' not in home
    editor=(out/'admin/index.php').read_text()
    assert 'worship_streams[' in editor and 'public_event' in editor
    assert 'publication-designer.php' not in editor
    assert 'member sign-in' not in (out/'bulletin.php').read_text()
    assert "addEventListener('push'" not in (out/'sw.js').read_text()
    guard=(out/'lib/bootstrap.php').read_text()
    assert "'member' => ['login.php', 'logout.php']" in guard
    assert "'api' => ['content.php', 'connection.php', 'rsvp.php']" in guard
    login=(out/'member/login.php').read_text()
    assert "in_array(kcmc_role($user), ['pastor_admin', 'recovery_admin'], true)" in login
    assert (out/'care.php').exists()
    result=subprocess.run([sys.executable,str(script),str(snapshot),str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert result.returncode!=0, 'Must reject an existing output directory'
    altered=Path(tmp)/'altered';shutil.copytree(snapshot,altered)
    with (altered/'index.php').open('a') as f: f.write('changed')
    invalid=Path(tmp)/'invalid'
    result=subprocess.run([sys.executable,str(script),str(altered),str(invalid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert result.returncode!=0 and not invalid.exists(), 'Must reject an altered snapshot without producing output'
    print('PASS: host hashes, retained content controls, route policy, navigation, push removal and stale-snapshot refusal')
    print('Static checks only; PHP, HTTP, actual hosting and browser acceptance are still required.')
