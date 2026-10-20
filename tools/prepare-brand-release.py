#!/usr/bin/env python3
"""Build a reproducible, offline branding review bundle. Never deploys."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = 'ca0d6197b4be7339fd5937f216202a7e5fbdd13d'
EVIDENCE = 'tools/kcmc-follow-up-oct18/evidence/public/'
MODIFIED = ('index.php', 'home-welcome.css', 'sw.js')
ADDED = tuple('assets/visuals/kcmc-'+name+'-20261018.jpg' for name in (
    'traditional-sanctuary', 'traditional-worship', 'traditional-front', 'traditional-message',
    'contemporary-gathering', 'contemporary-fellowship', 'contemporary-music',
    'contemporary-room', 'contemporary-room-portrait', 'contemporary-after-service'))
GUARDS = ('public-presentation.css', 'public-presentation.js', 'styles.css', 'app.js',
          'lib/screen-navigation.php', 'app-theme.css', 'app-navigation.js',
          'manifest.webmanifest', 'assets/icons/icon-192.png', 'assets/icons/icon-512.png',
          'assets/visuals/kcmc-building-original-20261018.jpg')

CHECKER = '''#!/usr/bin/env python3
"""Read-only exact bundle preflight. No network, apply, force or configuration access."""
import hashlib,json,os,stat,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN=__MANIFEST_PIN__
def need(ok,message):
    if not ok: raise RuntimeError(message)
def read(root,name,missing=False):
    p=root/name
    for parent in p.parents:
        need(parent.is_dir() and not parent.is_symlink(),'Unsafe directory: '+str(parent))
    if not p.exists() and not p.is_symlink():
        need(missing,'Missing file: '+name); return None
    info=p.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and
         stat.S_IMODE(info.st_mode) in (0o644,0o664),'Unsafe file metadata: '+name)
    need(info.st_size<=16*1024*1024,'Oversized file: '+name)
    fd=os.open(str(p),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        actual=os.fstat(f.fileno())
        need((info.st_dev,info.st_ino)==(actual.st_dev,actual.st_ino),'File changed: '+name)
        data=f.read(16*1024*1024+1)
    final=p.lstat()
    fields=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns)
    need(fields(info)==fields(final) and len(data)==info.st_size,'File changed: '+name)
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def inspect(root):
    raw=(HERE/'manifest.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest()==PIN,'Release manifest changed')
    manifest=json.loads(raw)
    for name,pin in manifest['payloads'].items():
        need(read(HERE,name)==pin,'Staged release payload changed: '+name)
    matches=[]
    for variant,bundle in manifest['variants'].items():
        if all(read(root,n)==pin for n,pin in bundle['guards'].items()):
            for phase in ['before','after']:
                if all(read(root,n,True)==pin for n,pin in bundle[phase].items()):
                    matches.append((variant,phase))
    need(len(matches)==1,'Unknown, mixed or incomplete public bundle; installation refused')
    return matches[0]
if __name__=='__main__':
    try:
        need(len(sys.argv)==2,'Usage: python3 -I -B check-release.py /home/bobsome1/public_html/kcmc-connect')
        variant,phase=inspect(Path(os.path.abspath(sys.argv[1])))
        print('CHECK',variant,phase,'(read only; no installation performed)')
    except (OSError,RuntimeError,ValueError) as exc:
        print('REFUSED:',exc,file=sys.stderr);sys.exit(1)
'''

RUNBOOK = '''# KCMC branding and current-content release candidate — October 20

This review bundle performs no deployment. Verify its published ZIP SHA256,
extract it into a private staging directory outside public_html, and use the
preflight below before a separately authorized installation. Do not extract it
over the live app.

## Public branding scope

Replace exactly `index.php`, `home-welcome.css`, and `sw.js`; add exactly the ten
authentic photographs listed in manifest.json. The requested mission is added
beneath the existing welcome links and the photographs appear below it. Navy,
fish icon, original building/sky, service times, and phone structure stay intact.

The two independently pinned variants are `main` and `livecalendar`. The existing
welcome release already made their index.php identical. Their different
public-presentation.css files remain read-only guards. This package contains no
replacement for that customized stylesheet or any other guard. It contains no
private store, configuration, credentials, account code, or ledger.

```sh
python3 -I -B check-release.py /home/bobsome1/public_html/kcmc-connect
```

Continue only for the expected variant in `before` state. `after` means the exact
bundle is already installed. Unknown, mixed, missing, executable, symbolic-link,
hard-link, changed-guard, or changed-payload states are refused. There is no force
option. The checker writes nothing and verifies staged payloads as well as live
code. Preserve the emitted variant and manifest hash with the release record.

## Installation transaction

The established host transaction mechanism must implement this bounded sequence;
this offline bundle does not contain or authorize a host transaction adapter.

1. Under an exclusive deployment lock, repeat preflight. Take actual private
   backups of the three existing targets; record and verify their hashes, modes,
   ownership and original paths against the selected before tuple. Verify that
   all ten additions are absent. Use a private journal outside public_html.
2. Stage all thirteen `after/` files on the same filesystem. Verify each SHA256
   against manifest.json. Lint staged index.php with the host PHP 8.2+ CLI without
   executing application code. Preserve existing code ownership and 0644/0664
   modes; give added public images the same reviewed ownership and 0644 mode.
3. Recheck the full before tuple, guard hashes, original metadata, and stage
   hashes immediately before replacements. Install the ten images first, then
   home-welcome.css, index.php, and sw.js last using atomic file replacements.
   Record each outcome in the durable private journal.
4. Re-run the exact preflight and require the same variant in `after` state.
   Verify the public home at phone and desktop widths, mission, all ten pictures,
   native expansion, original sky/building, Visit/Watch/Events/Prayer/Family links,
   and a refreshed service worker. Capture the actual resulting public responses.

If a replacement or acceptance check fails, stop. Under the same lock, accept
only each target's recorded before or after image; refuse unknown concurrent
edits. Restore index.php and sw.js from actual backups before removing any new
photo. Restore home-welcome.css, then remove a new photo only if its bytes match
the exact installed image and no retained consumer references it. Preserve
metadata. Verify the original variant in `before` state. `before/` holds reference
bytes; actual host backups are authoritative for rollback. Do not restore an
entire app directory or overwrite any live content store.

Server rollback does not immediately refresh every already installed device.
Check online appearance and a fresh worker update before describing cache state.

## Separate current-content publication

`content-publication/` contains a separate, hash-verified record-level publisher
with check/apply/rollback commands. Follow its README after reviewing its exact
live action list and receiving publication authorization. Its four bulletin
fields and specific event/announcement changes are independent of the thirteen
branding files. Do not copy repository data/content.json to the live host.

The content recipe accepts only October 20–25 local dates, skips expired records,
preserves staff edits or refuses conflicts, and records private actual-byte
backups. It performs no message sending. Keep its receipts/backups outside the
public tree and outside source control.
'''


def git(*args):
    return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=ROOT)


def image(name):
    return git('show', BASE+':'+PREFIX+name)


def metadata(data):
    return None if data is None else {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def guard(variant, name):
    if variant == 'livecalendar' and name == 'public-presentation.css':
        return git('show', BASE+':'+EVIDENCE+'livecalendar/'+name)
    return image(name)


def build(destination):
    spec=importlib.util.spec_from_file_location('brand_layer',ROOT/'tests/welcome_home_source_layer.py')
    layer=importlib.util.module_from_spec(spec);spec.loader.exec_module(layer)
    reviewed=layer.WelcomeLayer()
    assert set(MODIFIED)==set(reviewed.brand['modified']) and set(ADDED)==set(reviewed.brand['added'])
    before={name:image(name) for name in MODIFIED}
    after={name:reviewed.functions.before(name) for name in MODIFIED+ADDED}
    for name in MODIFIED:
        assert before[name]==reviewed.brand_before[name], 'Pinned baseline mismatch: '+name
    for name in GUARDS:
        assert reviewed.functions.before(name)==image(name), 'Read-only prerequisite changed: '+name
    entries={'README.md':RUNBOOK.encode('utf-8')}
    for name,data in before.items(): entries['before/'+name]=data
    for name,data in after.items(): entries['after/'+name]=data
    for name in ('publish.py','reviewed-content.json','README.md'):
        entries['content-publication/'+name]=(ROOT/'tools/kcmc-content-oct20'/name).read_bytes()
    manifest={'baseline_commit':BASE,'brand_fixture_sha256':layer.BRAND_PIN,
              'payloads':{name:metadata(data) for name,data in entries.items()},'variants':{}}
    for variant in ('main','livecalendar'):
        manifest['variants'][variant]={
            'before':{name:metadata(before.get(name)) for name in MODIFIED+ADDED},
            'after':{name:metadata(after[name]) for name in MODIFIED+ADDED},
            'guards':{name:metadata(guard(variant,name)) for name in GUARDS}}
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8')
    entries['manifest.json']=raw
    entries['check-release.py']=CHECKER.replace('__MANIFEST_PIN__',repr(hashlib.sha256(raw).hexdigest())).encode('utf-8')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,10,20,0,0,0));info.external_attr=0o100644<<16
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
    return manifest,entries


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.output)
    print(json.dumps({'path':str(args.output.resolve()),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'bytes':args.output.stat().st_size,'deployment_performed':False},indent=2))
