#!/usr/bin/env python3
"""Reproduce the pinned single-file installer from the frozen transaction engine."""
from __future__ import print_function

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
STAGE_CHECK = '''def lint(session):
    """Check pinned stage bytes only; Node --check is an off-host release gate."""
    for index, path in enumerate(PATHS):
        data, info = read(Path(session) / ('stage-' + str(index) + '.js'))
        item = FILES[path]
        require(info['mode'] == 0o600 and info['sha256'] == item['after_sha256'] and
                info['bytes'] == item['after_bytes'], 'Pinned JavaScript stage bytes changed')
'''


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen derivation anchor changed')
    return source.replace(old, new, 1)


def derive(engine, files):
    if hashlib.sha256(engine).hexdigest() != ENGINE_SHA256:
        raise ValueError('Frozen transaction engine hash changed')
    source = engine.decode('utf-8')
    changes = (
        ('"""Three pinned KCMC PHP repairs; Python 3.6+, offline, no application execution."""',
         '"""One pinned KCMC app.js repair; Python 3.6+, offline, no application execution."""'),
        ("BACKUPS = Path('/home/bobsome1/kcmc-minimal-repair-backups')",
         "BACKUPS = Path('/home/bobsome1/kcmc-skip-repair-backups')"),
        ("PHP = '/opt/cpanel/ea-php82/root/usr/bin/php'\n", ''),
        ("RELEASE = 'kcmc-minimal-repair-20261014'", "RELEASE = 'kcmc-skip-repair-20261014'"),
        ("PATHS = ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php')",
         "PATHS = ('app.js',)"),
        ('Repair inventory is not exactly the three reviewed files',
         'Repair inventory is not exactly the reviewed app.js file'),
        ('Backup staging and all three code files must use the same filesystem; no replacement made',
         'Backup staging and app.js must use the same filesystem; no replacement made'),
        ('Staged PHP 8.2 syntax verification failed; no live replacement. Private session: ',
         'Pinned staged JavaScript byte verification failed; no live replacement. Private session: '),
    )
    for old, new in changes:
        source = once(source, old, new)
    inventory = 'FILES = json.loads(' + repr(json.dumps(files, separators=(',', ':'))) + ')'
    source, count = re.subn(r'^FILES = json\.loads\(.*\)$', lambda unused: inventory, source, flags=re.MULTILINE)
    if count != 1:
        raise ValueError('Frozen inventory line changed')
    begin, end = source.index('def lint(session):\n'), source.index('\n\ndef bundle_lease(', source.index('def lint(session):\n'))
    source = source[:begin] + STAGE_CHECK.rstrip('\n') + source[end:]
    # Exactly six mechanically identical private code-name suffix literals:
    # one in the former lint body, and five in staging / backup / restore.
    # The former lint body has already been replaced above.
    if source.count("+ '.php'") != 5:
        raise ValueError('Frozen private filename literals changed')
    source = source.replace("+ '.php'", "+ '.js'")
    return source.encode('utf-8')


if __name__ == '__main__':
    engine = (HERE / 'provenance/frozen-minimal-installer.py').read_bytes()
    files = json.loads((HERE / 'runtime-reviewed.json').read_text())
    (HERE / 'installer.py').write_bytes(derive(engine, files))
