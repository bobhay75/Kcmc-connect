#!/usr/bin/env python3
"""Build a fixed-account, offline functional review transaction. Never calls a host."""
import argparse,hashlib,importlib.util,json,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from tony_function_source_layer import FunctionalLayer,MODIFIED as ALL_MODIFIED,ADDED as ALL_ADDED,PIN as SOURCE_PIN
PREFIX='KCMC-Connect-Phase6-Recreated/'
BASE='cac1420a905bba78a4a54651c69a8e77b57b2450'
MODIFIED=tuple(sorted(ALL_MODIFIED-{'assets/visuals/SOURCE.md'}))
ADDED=tuple(sorted(ALL_ADDED))
GUARDS=('public-presentation.css','styles.css','lib/bootstrap.php','lib/connection-intake.php',
        'lib/event-calendar.php','lib/public-presentation.php','lib/screen-navigation.php',
        'app-theme.css','app-navigation.js','manifest.webmanifest','assets/icons/icon-192.png',
        'assets/icons/icon-512.png','assets/visuals/kcmc-building-original-20261018.jpg',
        'assets/visuals/kcmc-traditional-sanctuary-20261018.jpg','assets/visuals/kcmc-contemporary-gathering-20261018.jpg')
ORDER=ADDED+('lib/visitor-welcome.php',)+tuple(n for n in MODIFIED if n not in ('lib/visitor-welcome.php','index.php','sw.js'))+('index.php','sw.js')
FROZEN_PIN='e405bc0cda2b7787d573fa2f436915e5d7c4339e03b511609b867ae9c01a0eb1'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def metadata(raw):return None if raw is None else {'sha256':digest(raw),'bytes':len(raw)}
def source(name):return subprocess.check_output(['git','--no-replace-objects','show',BASE+':'+PREFIX+name],cwd=ROOT)
def encode(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def adapter(manifest_pin):
    raw=(HERE/'frozen-pr161-adapter.py').read_bytes()
    assert digest(raw)==FROZEN_PIN,'Frozen adapter source changed'
    text=raw.decode()
    start=text.index('MODIFIED = ');end=text.index('MAX_BYTES = ',start)
    constants='MODIFIED = '+repr(MODIFIED)+'\nADDED = '+repr(ADDED)+'\nPATHS = MODIFIED + ADDED\nORDER = '+repr(ORDER)+'\nGUARDS = '+repr(GUARDS)+'\n'
    text=text[:start]+constants+text[end:]
    text=text.replace('kcmc-brand-oct20-backups','kcmc-tony-functions-oct20-backups').replace('kcmc-brand-oct20-pr161','kcmc-tony-functions-oct20-pr163')
    text=text.replace("MANIFEST_PIN = '84ed0526d049b04d066d0498efc96b098eb05f54a267600b6aa0256b821967ed'",'MANIFEST_PIN = '+repr(manifest_pin))
    text=text.replace("return session / ('before-' + name)","return session / ('before-' + name.replace('/', '__'))")
    text=text.replace("allowed = {'before-' + name for name in MODIFIED}","allowed = {backup_path(session, name).name for name in MODIFIED}")
    text=text.replace("for name in ('index.php', 'sw.js', 'home-welcome.css'):","for name in ('index.php', 'sw.js') + tuple(n for n in MODIFIED if n not in ('index.php', 'sw.js')):")
    text=text.replace("temporary = session / ('restore-' + uuid.uuid4().hex + '-' + name)","temporary = session / ('restore-' + uuid.uuid4().hex + '-' + name.replace('/', '__'))")
    old="""            lint = subprocess.run([php, '-n', '-l', str(staged['index.php'][0])],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            need(lint.returncode == 0, 'Host PHP lint failed before any live replacement')"""
    new="""            for name in PATHS:
                if not name.endswith('.php'): continue
                lint = subprocess.run([php, '-n', '-l', str(staged[name][0])],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                need(lint.returncode == 0, 'Host PHP lint failed before any live replacement: ' + name)"""
    assert text.count(old)==1,'Exact lint adapter anchor required';text=text.replace(old,new)
    text=text.replace('install-brand.py','install-functions.py').replace('PR161 public-brand transaction','PR163 functional transaction').replace('exactly the thirteen manifest targets','exactly the fourteen manifest targets')
    return text.encode()

def build(destination):
    layer=FunctionalLayer(ROOT)
    spec=importlib.util.spec_from_file_location('historical_brand_builder',ROOT/'tools/prepare-brand-release.py')
    historical=importlib.util.module_from_spec(spec);spec.loader.exec_module(historical)
    entries={'README.md':(HERE/'README.md').read_bytes(), 'mail-readiness.php':(HERE/'mail-readiness.php').read_bytes()}
    for name in MODIFIED:entries['before/'+name]=layer.before(name)
    for name in MODIFIED+ADDED:entries['after/'+name]=(ROOT/PREFIX/name).read_bytes()
    variants={}
    for variant in ['main','livecalendar']:
        guards={}
        for name in GUARDS:
            raw=source(name)
            if variant=='livecalendar' and name=='public-presentation.css':
                raw=subprocess.check_output(['git','--no-replace-objects','show',BASE+':tools/kcmc-follow-up-oct18/evidence/public/livecalendar/public-presentation.css'],cwd=ROOT)
            guards[name]=metadata(raw)
        variants[variant]={'guards':guards,'before':{n:metadata(entries.get('before/'+n)) for n in MODIFIED+ADDED},'after':{n:metadata(entries['after/'+n]) for n in MODIFIED+ADDED}}
    manifest={'baseline_commit':BASE,'functional_fixture_sha256':SOURCE_PIN,'payloads':{n:metadata(raw) for n,raw in entries.items()},'variants':variants}
    raw=encode(manifest);entries['manifest.json']=raw
    entries['check-release.py']=historical.CHECKER.replace('__MANIFEST_PIN__',repr(digest(raw))).encode()
    entries['install-functions.py']=adapter(digest(raw))
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,10,20,0,0,0));info.external_attr=0o100644<<16;z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
    return manifest,entries
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    build(args.output);print(json.dumps({'path':str(args.output.resolve()),'sha256':digest(args.output.read_bytes()),'bytes':args.output.stat().st_size,'deployment_performed':False},indent=2))
