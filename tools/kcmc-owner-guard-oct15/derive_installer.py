#!/usr/bin/env python3
"""Derive four owner guards with frozen transactions and a read-only bootstrap lease."""
from __future__ import print_function
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
FIXTURES = {
    'owner-account-guard-reviewed.json': 'd872e4deb60baca4cade936412c9706294a3e8a5a2e671acddc59493ca52e527',
    'push-owner-link-reviewed.json': 'b6ca2c3e1e218627643aa9d5962ccc11b535242bb7e4e5c25303afd776f32042',
}
SESSION_FIXTURE_SHA256 = '85acda478e90d091f46f290018ab4eca65283e380b0eefa87752b1d27a8128c8'
PATHS = ('lib/password-lifecycle.php', 'admin/users.php', 'admin/password-resets.php', 'member/notifications.php')
COMMIT = '93c72f4fc430d311e01108d3a30d0561bb701c9d'
PREREQUISITE_SHA256 = 'd4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(source, old, new):
    if source.count(old) != 1: raise ValueError('Frozen derivation anchor changed')
    return source.replace(old, new, 1)


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

def derive_engine(raw, files):
    if sha(raw) != ENGINE_SHA256: raise ValueError('Frozen transaction engine hash changed')
    source = raw.decode('utf-8')
    replacements = (
        ('"""Three pinned KCMC PHP repairs; Python 3.6+, offline, no application execution."""',
         '"""Four pinned KCMC owner guards; Python 3.6+, offline, no application execution."""'),
        ("BACKUPS = Path('/home/bobsome1/kcmc-minimal-repair-backups')",
         "BACKUPS = Path('/home/bobsome1/kcmc-owner-guard-backups')"),
        ("RELEASE = 'kcmc-minimal-repair-20261014'", "RELEASE = 'kcmc-owner-guard-20261015-main93'"),
        ("PATHS = ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php')", 'PATHS = ' + repr(PATHS)),
        ('Repair inventory is not exactly the three reviewed files', 'Repair inventory is not exactly the four reviewed files'),
        ('Backup staging and all three code files must use the same filesystem; no replacement made',
         'Backup staging and all four code files must use the same filesystem; no replacement made'),
    )
    for old, new in replacements: source = once(source, old, new)
    line = 'FILES = json.loads(' + repr(json.dumps(files, separators=(',', ':'))) + ')'
    source, count = re.subn(r'^FILES = json\.loads\(.*\)$', lambda unused: line, source, flags=re.MULTILINE)
    if count != 1: raise ValueError('Frozen inventory line changed')
    begin = source.index('def lint(session):\n'); end = source.index('\n\ndef bundle_lease(', begin)
    source = source[:begin] + STAGE_CHECK.rstrip('\n') + source[end:]
    if source.count("+ '.php'") != 5: raise ValueError('Frozen staging suffix literals changed')
    return source.replace("+ '.php'", "+ '.code'")


def verify_runtime():
    records = {}
    for name, expected in FIXTURES.items():
        raw = (HERE / 'provenance' / name).read_bytes()
        if sha(raw) != expected: raise ValueError('Exact owner source fixture changed')
        fixture = json.loads(raw.decode('utf-8'))
        if fixture['source_commit'] != COMMIT: raise ValueError('Canonical owner source changed')
        if set(records) & set(fixture['files']): raise ValueError('Owner source fixtures overlap')
        records.update(fixture['files'])
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    baseline = json.loads((HERE / 'evidence/baseline.json').read_text())
    if set(runtime) != {'main93'} or tuple(runtime['main93']) != PATHS or set(records) != set(PATHS):
        raise ValueError('Exact four-file owner scope changed')
    if baseline['source_commit'] != COMMIT or set(baseline['files']) != set(PATHS): raise ValueError('Exact baseline scope changed')
    for path in PATHS:
        item = runtime['main93'][path]; record = records[path]
        if item['replacements'] != record['replacements']: raise ValueError('Owner delta is not the reviewed source delta')
        before = (HERE / 'evidence/main93' / path).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(before)).encode('ascii') + b'\0' + before).hexdigest()
        if baseline['files'][path] != {'sha256': sha(before), 'bytes': len(before), 'git_blob_sha1': blob}: raise ValueError('Canonical baseline bytes changed')
        if sha(before) != item['before_sha256'] or len(before) != item['before_bytes'] or item['before_sha256'] != record['before_sha256']: raise ValueError('Owner preimage changed')
        after = before
        for old, new in item['replacements']:
            if after.count(old.encode('utf-8')) != 1: raise ValueError('Owner repair anchor changed')
            after = after.replace(old.encode('utf-8'), new.encode('utf-8'), 1)
        if sha(after) != item['after_sha256'] or len(after) != item['after_bytes'] or item['after_sha256'] != record['after_sha256']: raise ValueError('Owner target changed')
        for old, new in reversed(item['replacements']):
            if after.count(new.encode('utf-8')) != 1: raise ValueError('Owner reverse anchor changed')
            after = after.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
        if after != before: raise ValueError('Owner delta is not exactly reversible')
    return runtime


def verify_prerequisite():
    prerequisite = json.loads((HERE / 'prerequisite-reviewed.json').read_text())
    expected = {'path': 'lib/bootstrap.php', 'sha256': PREREQUISITE_SHA256, 'bytes': 24274,
        'source_commit': COMMIT, 'canonical_before_sha256': '96590431ef787a6a689a3c9e1655cdb4cac10c7c86e5cde8f579cd0b3571c518',
        'session_fixture_sha256': SESSION_FIXTURE_SHA256}
    if prerequisite != expected or prerequisite['path'] in PATHS: raise ValueError('Read-only prerequisite scope changed')
    content = (HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()
    if sha(content) != PREREQUISITE_SHA256 or len(content) != prerequisite['bytes']: raise ValueError('Exact installed bootstrap evidence changed')
    raw = (HERE / 'provenance/session-credential-reviewed.json').read_bytes()
    if sha(raw) != SESSION_FIXTURE_SHA256: raise ValueError('Session prerequisite fixture changed')
    record = json.loads(raw.decode('utf-8'))['files']['lib/bootstrap.php']
    if record['after_sha256'] != sha(content) or record['before_sha256'] != prerequisite['canonical_before_sha256']: raise ValueError('Canonical prerequisite pins changed')
    for old, new in reversed(record['replacements']):
        if content.count(new.encode('utf-8')) != 1: raise ValueError('Prerequisite reverse anchor changed')
        content = content.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
    if sha(content) != prerequisite['canonical_before_sha256']: raise ValueError('Canonical prerequisite preimage changed')
    return prerequisite


def build():
    runtime = verify_runtime(); prerequisite = verify_prerequisite()
    raw = (HERE / 'provenance/frozen-minimal-installer.py').read_bytes()
    source = derive_engine(raw, runtime['main93']); payload = {'main93': [source, sha(source.encode('utf-8'))]}
    wrapper = (HERE / 'wrapper.py.in').read_text()
    if wrapper.count('# EMBEDDED_ENGINES') != 1 or wrapper.count('# EMBEDDED_PREREQUISITE') != 1: raise ValueError('Embedding anchor changed')
    wrapper = wrapper.replace('# EMBEDDED_ENGINES', 'EMBEDDED = ' + repr(payload))
    wrapper = wrapper.replace('# EMBEDDED_PREREQUISITE', 'PREREQUISITE = ' + repr(prerequisite))
    (HERE / 'installer.py').write_text(wrapper)
    proof = {'frozen_engine_sha256': ENGINE_SHA256, 'reviewed_delta_sha256': FIXTURES,
        'session_prerequisite_delta_sha256': SESSION_FIXTURE_SHA256, 'embedded_engines': {'main93': payload['main93'][1]},
        'installer_sha256': sha(wrapper.encode('utf-8')), 'scope': list(PATHS), 'canonical_source_commit': COMMIT,
        'read_only_prerequisite': prerequisite,
        'transaction_policy': 'All frozen engine functions/classes unchanged except exact stage-byte syntax lint and .code staging suffix; wrapper composes existing lease callback with bootstrap lease.'}
    (HERE / 'provenance.json').write_text(json.dumps(proof, indent=2) + '\n')
    print('Derived installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
