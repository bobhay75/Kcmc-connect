#!/usr/bin/env python3
"""Freeze the two reviewed offline engines into one Python 3.6+ runner."""
from __future__ import print_function

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_FILES = (
    ('php', HERE.parent / 'kcmc-minimal-repair-oct14' / 'installer.py',
     '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'),
    ('skip', HERE.parent / 'kcmc-skip-repair-oct14' / 'installer.py',
     '3d92c48e16062af4d75994cdaedbbb4234df58b8c7e86ddf4214817f41dc01db'),
)

HEADER = '''#!/usr/bin/env python3
"""Four pinned KCMC code fixes in two independent groups; Python 3.6+, offline."""
from __future__ import print_function

import argparse
import hashlib
import sys
import types

GROUPS = ('php', 'skip')
'''

RUNTIME = '''

class Refusal(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def load_engines():
    """Verify every exact UTF-8 source before executing any definitions."""
    require(set(EMBEDDED) == set(GROUPS), 'Embedded engine inventory refused')
    for group in GROUPS:
        source, expected = EMBEDDED[group]
        require(isinstance(source, str) and isinstance(expected, str) and
                hashlib.sha256(source.encode('utf-8')).hexdigest() == expected,
                'Embedded ' + group + ' engine checksum mismatch; no host inspection')
    engines = {}
    for group in GROUPS:
        source, unused_expected = EMBEDDED[group]
        module = types.ModuleType('kcmc_frozen_' + group + '_engine')
        module.__file__ = '<embedded-kcmc-' + group + '-engine>'
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
        engines[group] = module
    return engines


def safe_message(error, engines):
    known = (Refusal,) + tuple(engines[group].Refusal for group in GROUPS if group in engines)
    return str(error) if isinstance(error, known) else 'Unexpected failure; refused safely'


def preflight(engines):
    """Both bundles and both private journals pass before either apply starts."""
    results = {}
    for group in GROUPS:
        module = engines[group]
        try:
            state, files = module.inspect()
            module.unfinished()
        except BaseException as error:
            raise Refusal('GROUP ' + group + ' PREFLIGHT_REFUSED ' + safe_message(error, engines))
        results[group] = (state, files)
    return results


def report_checked(group, module, result):
    state, files = result
    print('GROUP ' + group + ' CHECK ' + ('READY' if state == 'before' else 'ALREADY_REPAIRED'))
    for path in module.PATHS:
        print('CODE ' + group + ' ' + path + ' sha256=' + files[path][1]['sha256'])
    print('PRIVATE_BACKUP_ROOT ' + group + ' ' + str(module.BACKUPS))


def rollback_command(group, session):
    # The published download block always saves this standalone file as installer.py.
    return 'python3 installer.py rollback --group ' + group + ' --session ' + session.name


def report_session(group, module, session, phase):
    print('PRIVATE_SESSION ' + group + ' ' + str(session))
    print('JOURNAL_PHASE ' + group + ' ' + phase)
    if phase == 'applied':
        print('ROLLBACK_COMMAND ' + rollback_command(group, session))


def session_names(module):
    """Read-only diagnostics through the inherited no-follow private-root checks."""
    try:
        module.private_dir(module.BACKUPS)
    except FileNotFoundError:
        return set()
    with module.Parent(module.BACKUPS) as parent:
        names = module.os.listdir(parent.fd)
        parent.check()
    result = set()
    for name in names:
        if name.startswith('repair-'):
            module.session_name(name)
            result.add(name)
    return result


def report_failed_sessions(group, module, previous):
    if previous is None:
        print('SESSION_STATUS ' + group + ' UNVERIFIED; inspect the fixed private backup root')
        return
    try:
        names = session_names(module) - previous
    except BaseException:
        print('SESSION_STATUS ' + group + ' UNVERIFIED; inspect the fixed private backup root')
        return
    for name in sorted(names):
        session = module.session_name(name)
        try:
            value = module.load(session)
            phase = value['phase']
        except BaseException:
            phase = 'unverified'
        report_session(group, module, session, phase)


def apply_groups(engines):
    results = preflight(engines)
    for group in GROUPS:
        report_checked(group, engines[group], results[group])
    print('Groups apply separately; a later failure keeps an earlier successful repair.')
    for group in GROUPS:
        module = engines[group]
        previous = None
        try:
            previous = session_names(module)
            session = module.apply()
        except BaseException as error:
            print('GROUP ' + group + ' APPLY_FAILED ' + safe_message(error, engines), file=sys.stderr)
            report_failed_sessions(group, module, previous)
            return 1
        if session is None:
            print('GROUP ' + group + ' ALREADY_REPAIRED; no replacement or new backup.')
        else:
            print('GROUP ' + group + ' APPLIED ' + ', '.join(module.PATHS))
            report_session(group, module, session, 'applied')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='check', choices=('check', 'apply', 'rollback'))
    parser.add_argument('--group', choices=GROUPS, help='Required only for an independent rollback')
    parser.add_argument('--session', help='Exact private session basename; rollback only')
    args = parser.parse_args()
    engines = {}
    try:
        require((args.action == 'rollback') == (args.group is not None) and
                (args.action == 'rollback') == (args.session is not None),
                'Rollback requires both --group and --session; check/apply accept neither')
        engines = load_engines()
        if args.action == 'check':
            results = preflight(engines)
            for group in GROUPS:
                report_checked(group, engines[group], results[group])
            print('Read-only check complete; no code replacement or new private backup.')
            return 0
        if args.action == 'apply':
            return apply_groups(engines)
        module = engines[args.group]
        session = module.rollback(args.session)
        print('GROUP ' + args.group + ' ROLLED_BACK')
        report_session(args.group, module, session, 'rolled_back')
        return 0
    except BaseException as error:
        print('REFUSED ' + safe_message(error, engines), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
'''


def generate():
    entries = []
    # Finish validation of both inputs before writing the generated artifact.
    for group, path, expected in ENGINE_FILES:
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError('Frozen ' + group + ' engine checksum mismatch')
        source = data.decode('utf-8')
        if source.encode('utf-8') != data:
            raise ValueError('Frozen engine is not exact UTF-8')
        compile(source, '<reviewed-' + group + '-engine>', 'exec')
        entries.append('    ' + repr(group) + ': (' + repr(source) + ', ' + repr(expected) + '),\n')
    output = (HEADER + '\nEMBEDDED = {\n' + ''.join(entries) + '}\n' + RUNTIME).encode('utf-8')
    compile(output, '<combined-runner>', 'exec')
    path = HERE / 'installer.py'
    path.write_bytes(output)
    path.chmod(0o600)
    print('GENERATED ' + str(path))
    print('SHA256 ' + hashlib.sha256(output).hexdigest())
    return path


if __name__ == '__main__':
    generate()
