#!/usr/bin/env python3
"""Derive three exact fish-home repair engines from a frozen transaction engine."""
from __future__ import print_function
import difflib
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
PATHS = ('index.php', 'public-presentation.css', 'sw.js')
VARIANTS = ('live154', 'main130', 'livecalendar')
ROOT = HERE.parents[1] / 'KCMC-Connect-Phase6-Recreated'

def verify_livecalendar_preimage():
    proof=json.loads((HERE/'provenance/livecalendar-index-derivation.json').read_text())
    fixture=(HERE/'provenance/event-calendar-reviewed.json').read_bytes()
    before=(HERE/'evidence/live154/index.php').read_bytes()
    if sha(fixture)!='a26b9938efc2e4edcabb4d33ad902b33e1b34bf46809715d04b94c0d1c1f1f92' or sha(before)!='fa828f80c7f3c3b5ec47d815933f7df247f6ba4e542f9e5261182fb006b83723':
        raise ValueError('Frozen calendar fixture or approved public base changed')
    pairs=json.loads(fixture.decode('utf-8'))['modified']['index.php']['replacements']
    if len(pairs)!=3:
        raise ValueError('Frozen calendar replacement count changed')
    after=before
    for old,new in pairs:
        old,new=old.encode('utf-8'),new.encode('utf-8')
        if after.count(old)!=1:
            raise ValueError('Frozen calendar anchor is not unique')
        after=after.replace(old,new,1)
    if sha(after)!='745bdc1f31824b8962ef49440a83e313dbdea70e4a8e0620ff746049f656df3d' or len(after)!=33550 or after!=(HERE/'evidence/livecalendar/index.php').read_bytes():
        raise ValueError('Reconstructed calendar index does not match the exact host receipt')
    if proof['base_sha256']!=sha(before) or proof['base_bytes']!=len(before) or proof['patch_sha256']!=sha(fixture) or proof['replacement_count']!=len(pairs) or proof['after_sha256']!=sha(after) or proof['after_bytes']!=len(after):
        raise ValueError('Calendar preimage provenance metadata changed')
    for path in ('public-presentation.css','sw.js'):
        if (HERE/'evidence/livecalendar'/path).read_bytes()!=(HERE/'evidence/live154'/path).read_bytes():
            raise ValueError('Calendar variant must retain exact installed public CSS and worker')
    return after

def sha(data):
    return hashlib.sha256(data).hexdigest()

def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen derivation anchor changed')
    return source.replace(old, new, 1)

STAGE_CHECK = '''def lint(session):
    """Check all exact stage bytes and lint only PHP, without executing the app."""
    version = subprocess.check_output([PHP, '-n', '-v'], stderr=subprocess.STDOUT, timeout=15)
    require(re.match(br'\\APHP 8\\.2\\.[0-9]+\\b', version) is not None, 'Fixed PHP 8.2 CLI required')
    for index, path in enumerate(PATHS):
        staged = Path(session) / ('stage-' + str(index) + '.code')
        data, info = read(staged)
        item = FILES[path]
        require(info['mode'] == 0o600 and info['sha256'] == item['after_sha256'] and
                info['bytes'] == item['after_bytes'], 'Pinned stage bytes changed')
        if path.endswith('.php'):
            subprocess.check_output([PHP, '-n', '-l', str(staged)], stderr=subprocess.STDOUT, timeout=15)
'''

def derive_engine(raw, variant, files):
    if sha(raw) != ENGINE_SHA256:
        raise ValueError('Frozen transaction engine hash changed')
    source = raw.decode('utf-8')
    changes = (
        ('"""Three pinned KCMC PHP repairs; Python 3.6+, offline, no application execution."""',
         '"""Three pinned fish-home files; Python 3.6+, offline, no application execution."""'),
        ("BACKUPS = Path('/home/bobsome1/kcmc-minimal-repair-backups')",
         "BACKUPS = Path('/home/bobsome1/kcmc-fish-home-" + variant + "-backups')"),
        ("RELEASE = 'kcmc-minimal-repair-20261014'", "RELEASE = 'kcmc-fish-home-20261014-" + variant + "'"),
        ("PATHS = ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php')", "PATHS = " + repr(PATHS)),
        ('Staged PHP 8.2 syntax verification failed; no live replacement. Private session: ',
         'Pinned stage / PHP 8.2 verification failed; no live replacement. Private session: '),
    )
    for old, new in changes:
        source = once(source, old, new)
    line = 'FILES = json.loads(' + repr(json.dumps(files, separators=(',', ':'))) + ')'
    source, count = re.subn(r'^FILES = json\.loads\(.*\)$', lambda unused: line, source, flags=re.MULTILINE)
    if count != 1:
        raise ValueError('Frozen inventory line changed')
    begin = source.index('def lint(session):\n')
    end = source.index('\n\ndef bundle_lease(', begin)
    source = source[:begin] + STAGE_CHECK.rstrip('\n') + source[end:]
    if source.count("+ '.php'") != 5:
        raise ValueError('Frozen staging suffix literals changed')
    source = source.replace("+ '.php'", "+ '.code'")
    return source

def line_replacements(before, after):
    old, new = before.decode('utf-8').splitlines(True), after.decode('utf-8').splitlines(True)
    pairs=[]
    for tag, a, b, c, d in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        anchor=''.join(old[a:b]); replacement=''.join(new[c:d])
        if not anchor:
            # Use one unchanged preceding line as the unique insertion anchor.
            anchor=old[a-1]; replacement=anchor+replacement
        if before.decode('utf-8').count(anchor) != 1:
            raise ValueError('Application repair anchor is not unique')
        pairs.append([anchor,replacement])
    return pairs

def build_runtime():
    main=HERE/'evidence/main130'
    replacements={path:line_replacements((main/path).read_bytes(),(ROOT/path).read_bytes()) for path in PATHS}
    runtime={}
    for variant in VARIANTS:
        files={}
        after_dir=HERE/'evidence'/('after-'+variant); after_dir.mkdir(exist_ok=True)
        for path in PATHS:
            before=(HERE/'evidence'/variant/path).read_bytes(); after=before
            pairs=json.loads(json.dumps(replacements[path]))
            for pair in pairs:
                if variant in ('live154','livecalendar'):
                    pair[0]=pair[0].replace('home-option-b-20261013','home-audit-20261013').replace('public-only-option-b-20261013','public-only-home-audit-20261013')
                anchor,replacement=[v.encode('utf-8') for v in pair]
                if after.count(anchor)!=1:
                    raise ValueError('Variant repair anchor changed: '+variant+'/'+path)
                after=after.replace(anchor,replacement,1)
            if variant=='main130' and after!=(ROOT/path).read_bytes():
                raise ValueError('Main output is not exact reviewed application source')
            (after_dir/path).write_bytes(after)
            files[path]={'before_sha256':sha(before),'after_sha256':sha(after),'before_bytes':len(before),'after_bytes':len(after),'replacements':pairs}
        runtime[variant]=files
    return runtime

def build(from_source=False):
    raw=(HERE/'provenance/frozen-minimal-installer.py').read_bytes()
    verify_livecalendar_preimage()
    if from_source:
        runtime=build_runtime()
        (HERE/'runtime-reviewed.json').write_text(json.dumps(runtime,indent=2,sort_keys=True)+'\n')
        runtime=json.loads((HERE/'runtime-reviewed.json').read_text())
    else:
        runtime=json.loads((HERE/'runtime-reviewed.json').read_text())
    sources={variant:derive_engine(raw,variant,runtime[variant]) for variant in VARIANTS}
    payload={variant:[source,sha(source.encode('utf-8'))] for variant,source in sources.items()}
    wrapper=(HERE/'wrapper.py.in').read_text()
    if wrapper.count('# EMBEDDED_ENGINES')!=1:
        raise ValueError('Wrapper embedding anchor changed')
    wrapper=wrapper.replace('# EMBEDDED_ENGINES','EMBEDDED = '+repr(payload))
    (HERE/'installer.py').write_text(wrapper)
    (HERE/'provenance.json').write_text(json.dumps({'frozen_engine_sha256':ENGINE_SHA256,'embedded_engines':{variant:payload[variant][1] for variant in sources},'installer_sha256':sha(wrapper.encode('utf-8')),'scope':list(PATHS)},indent=2)+'\n')
    print('Derived installer SHA256 '+sha(wrapper.encode('utf-8')))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-source',action='store_true',help='Refresh reviewed deltas from the approved main fixture and candidate application')
    parser.add_argument('--runtime-root',type=Path,default=ROOT,help='Candidate app for --from-source; never a hosting override')
    args=parser.parse_args()
    ROOT=args.runtime_root
    build(args.from_source)
