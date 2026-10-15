#!/usr/bin/env python3
"""Derive exact session bundles without changing the frozen transaction policy."""
from __future__ import print_function
import ast
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ENGINE_SHA256='4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
FIXTURE_SHA256='85acda478e90d091f46f290018ab4eca65283e380b0eefa87752b1d27a8128c8'
PATHS=('lib/session-lifetime.php','lib/bootstrap.php','member/login.php','member/password.php')
COMMITS={'live154':'154b779a0ea3d27a11300bfe0454f8a7c4aca355','main93':'93c72f4fc430d311e01108d3a30d0561bb701c9d'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def once(source,old,new):
    if source.count(old)!=1:raise ValueError('Frozen derivation anchor changed')
    return source.replace(old,new,1)

STAGE_CHECK='''def lint(session):
    """Verify exact staged bytes and PHP syntax without executing application code."""
    version = subprocess.check_output([PHP, '-n', '-v'], stderr=subprocess.STDOUT, timeout=15)
    require(re.match(br'\\APHP 8\\.2\\.[0-9]+\\b', version) is not None, 'Fixed PHP 8.2 CLI required')
    for index, path in enumerate(PATHS):
        staged = Path(session) / ('stage-' + str(index) + '.code')
        data, info = read(staged)
        item = FILES[path]
        require(info['mode'] == 0o600 and info['sha256'] == item['after_sha256'] and
                info['bytes'] == item['after_bytes'], 'Pinned stage bytes changed')
        subprocess.check_output([PHP, '-n', '-l', str(staged)], stderr=subprocess.STDOUT, timeout=15)
'''
RECOVERY_ANCHOR="""            verify_lease(path, record['installed'])
            data, original_meta = read(Path(session) / ('original-' + str(index) + '.php'))
"""
RECOVERY_SAFE="""            verify_lease(path, record['installed'])
            if index == 0 and (uncertain or conflicts):
                conflicts.append(path)
                continue
            data, original_meta = read(Path(session) / ('original-' + str(index) + '.php'))
"""

def derive_engine(raw,variant,files):
    if sha(raw)!=ENGINE_SHA256:raise ValueError('Frozen transaction engine hash changed')
    source=raw.decode('utf-8')
    replacements=(
        ('"""Three pinned KCMC PHP repairs; Python 3.6+, offline, no application execution."""',
         '"""Four pinned KCMC session repairs; Python 3.6+, offline, no application execution."""'),
        ("BACKUPS = Path('/home/bobsome1/kcmc-minimal-repair-backups')",
         "BACKUPS = Path('/home/bobsome1/kcmc-session-"+variant+"-backups')"),
        ("RELEASE = 'kcmc-minimal-repair-20261014'", "RELEASE = 'kcmc-session-repair-20261015-"+variant+"'"),
        ("PATHS = ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php')", 'PATHS = '+repr(PATHS)),
        ('Repair inventory is not exactly the three reviewed files','Repair inventory is not exactly the four reviewed files'),
        ('Backup staging and all three code files must use the same filesystem; no replacement made',
         'Backup staging and all four code files must use the same filesystem; no replacement made'),
    )
    for old,new in replacements:source=once(source,old,new)
    # A backwards-compatible helper must not be downgraded while a newer
    # consumer may remain. Preserve its verified installed lease and require
    # manual review rather than claiming complete recovery.
    source=once(source,RECOVERY_ANCHOR,RECOVERY_SAFE)
    line='FILES = json.loads('+repr(json.dumps(files,separators=(',',':')))+')'
    source,count=re.subn(r'^FILES = json\.loads\(.*\)$',lambda unused:line,source,flags=re.MULTILINE)
    if count!=1:raise ValueError('Frozen inventory line changed')
    begin=source.index('def lint(session):\n');end=source.index('\n\ndef bundle_lease(',begin)
    source=source[:begin]+STAGE_CHECK.rstrip('\n')+source[end:]
    if source.count("+ '.php'")!=5:raise ValueError('Frozen staging suffix literals changed')
    source=source.replace("+ '.php'","+ '.code'")
    return source

def verify_runtime():
    raw=(HERE/'provenance/session-credential-reviewed.json').read_bytes()
    if sha(raw)!=FIXTURE_SHA256:raise ValueError('Reviewed session delta fixture changed')
    fixture=json.loads(raw.decode('utf-8'));runtime=json.loads((HERE/'runtime-reviewed.json').read_text())
    baseline=json.loads((HERE/'evidence/baseline.json').read_text())
    if set(runtime)!=set(COMMITS) or set(baseline)!=set(COMMITS):raise ValueError('Variant inventory changed')
    inventory=json.loads((HERE/'provenance/oct13-approved-inventory.json').read_text())
    if inventory['commit']!=COMMITS['live154']:raise ValueError('Approved October13 source changed')
    for path,item in (('lib/bootstrap.php',inventory['files']['lib/bootstrap.php']),('member/login.php',inventory['preserve_guards']['member/login.php'])):
        expected=runtime['live154'][path]
        if item['sha256']!=expected['before_sha256'] or item['bytes']!=expected['before_bytes']:raise ValueError('Approved host inventory does not corroborate the exact preimage')
    for variant,commit in COMMITS.items():
        if tuple(runtime[variant])!=PATHS or baseline[variant]['source_commit']!=commit:raise ValueError('Runtime order/source changed')
        for path in PATHS:
            before=(HERE/'evidence'/variant/path).read_bytes();item=runtime[variant][path]
            if item['replacements']!=fixture['files'][path]['replacements']:raise ValueError('Session repair must use exactly the same reviewed literal replacements')
            proof=baseline[variant]['files'][path]
            blob=hashlib.sha1(('blob '+str(len(before))+'\0').encode('ascii')+before).hexdigest()
            if sha(before)!=item['before_sha256'] or len(before)!=item['before_bytes'] or proof!={'sha256':sha(before),'bytes':len(before),'git_blob_sha1':blob}:raise ValueError('Exact approved baseline changed')
            after=before
            for old,new in item['replacements']:
                if after.count(old.encode('utf-8'))!=1:raise ValueError('Repair anchor changed')
                after=after.replace(old.encode('utf-8'),new.encode('utf-8'),1)
            if sha(after)!=item['after_sha256'] or len(after)!=item['after_bytes']:raise ValueError('Exact session target changed')
            reverted=after
            for old,new in reversed(item['replacements']):
                if reverted.count(new.encode('utf-8'))!=1:raise ValueError('Reverse repair anchor changed')
                reverted=reverted.replace(new.encode('utf-8'),old.encode('utf-8'),1)
            if reverted!=before:raise ValueError('Repair is not exactly reversible')
            if variant=='main93' and (item['before_sha256']!=fixture['files'][path]['before_sha256'] or item['after_sha256']!=fixture['files'][path]['after_sha256']):raise ValueError('Canonical repair byte pins changed')
    return runtime

def build():
    raw=(HERE/'provenance/frozen-minimal-installer.py').read_bytes();runtime=verify_runtime()
    sources={variant:derive_engine(raw,variant,runtime[variant]) for variant in COMMITS}
    payload={variant:[source,sha(source.encode('utf-8'))] for variant,source in sources.items()}
    wrapper=(HERE/'wrapper.py.in').read_text()
    if wrapper.count('# EMBEDDED_ENGINES')!=1:raise ValueError('Embedding anchor changed')
    wrapper=wrapper.replace('# EMBEDDED_ENGINES','EMBEDDED = '+repr(payload))
    (HERE/'installer.py').write_text(wrapper)
    (HERE/'provenance.json').write_text(json.dumps({'frozen_engine_sha256':ENGINE_SHA256,'reviewed_delta_sha256':FIXTURE_SHA256,'embedded_engines':{variant:payload[variant][1] for variant in COMMITS},'installer_sha256':sha(wrapper.encode('utf-8')),'scope':list(PATHS),'approved_source_commits':COMMITS,'dependency_recovery_delta':{'before':RECOVERY_ANCHOR,'after':RECOVERY_SAFE}},indent=2)+'\n')
    print('Derived installer SHA256 '+sha(wrapper.encode('utf-8')))

if __name__=='__main__':build()
