#!/usr/bin/env python3
"""Report tracked-file mode/group mismatches; never read worktree contents."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

HELPER_SHA256 = '1ed8ce0980638f8ff1488a6fda785f6aa6a12c8db03bfe8e75cc13c81955e0a6'

class Refusal(Exception):
    def __init__(self, reason, path=None):
        self.reason, self.path = reason, path

def require(ok, reason, path=None):
    if not ok:
        raise Refusal(reason, path)

def load_helper(path):
    descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                info.st_uid == os.getuid() and info.st_size == 14570, 'Verified helper file refused')
        raw = stream.read(14571)
    require(hashlib.sha256(raw).hexdigest() == HELPER_SHA256, 'Verified helper hash refused')
    helper = types.ModuleType('read_only_metadata_helper')
    exec(compile(raw, '<verified-helper>', 'exec'), helper.__dict__)
    return helper

def scan(helper):
    identity, config = helper.standard_repo()
    head = helper.git(['rev-parse', '--verify', 'HEAD']).strip().decode('ascii')
    require(re.match(r'\A[0-9a-f]{40}\Z', head) is not None and
            head in set(helper.BASELINE_IDS + (helper.TARGET,)), 'HEAD is outside the approved diagnostic scope')
    tree = helper.source_tree(head)
    require(all(not row or row.startswith(b'H ') for row in helper.git(['ls-files', '-v', '-z']).split(b'\0')),
            'Index flags require review; no metadata report produced')
    index = {}
    for row in helper.git(['ls-files', '--stage', '-z']).split(b'\0'):
        if row:
            header, name = row.split(b'\t', 1)
            mode, oid, stage = header.split()
            require(stage == b'0', 'Unmerged index; no metadata report produced')
            index[name.decode('utf-8')] = (mode, oid)
    require(index == tree, 'Staged changes; no metadata report produced')
    caller_uid, caller_gid = os.getuid(), os.getgid()
    observed, observed_dirs, rows = {}, {}, []
    for name, (mode, oid) in sorted(tree.items()):
        require(not name.startswith('/') and all(p not in ('', '.', '..', '.git') for p in name.split('/')),
                'Unsafe tracked pathname; no metadata report produced')
        path = helper.REPO / name
        helper.physical(path.parent)
        current = helper.REPO
        for part in path.parent.relative_to(helper.REPO).parts:
            current = current / part
            directory = os.lstat(str(current))
            require(stat.S_ISDIR(directory.st_mode) and directory.st_uid == caller_uid and
                    directory.st_gid == caller_gid, 'Tracked directory ownership/type requires review',
                    str(current.relative_to(helper.REPO)))
            observed_dirs[current] = (directory.st_dev, directory.st_ino, directory.st_uid, directory.st_gid)
        info = os.lstat(str(path))
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == caller_uid,
                'Tracked file ownership/type/link requires review', name)
        expected = 0o755 if mode == b'100755' else 0o644
        observed[name] = (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_uid, info.st_gid)
        if stat.S_IMODE(info.st_mode) != expected or info.st_gid != caller_gid:
            rows.append({'path': name, 'mode': format(stat.S_IMODE(info.st_mode), '04o'),
                         'expected_mode': format(expected, '04o'), 'uid': info.st_uid,
                         'gid': info.st_gid, 'expected_gid': caller_gid})
    final_identity, final_config = helper.standard_repo()
    require((final_identity, final_config) == (identity, config) and
            helper.git(['rev-parse', '--verify', 'HEAD']).strip().decode('ascii') == head and
            helper.git(['ls-files', '--stage', '-z']) == b''.join(
                mode + b' ' + oid + b' 0\t' + name.encode('utf-8') + b'\0'
                for name, (mode, oid) in sorted(index.items())),
            'Repository changed during diagnostic; no metadata report produced')
    for directory, expected in observed_dirs.items():
        helper.physical(directory)
        info = os.lstat(str(directory))
        require((info.st_dev, info.st_ino, info.st_uid, info.st_gid) == expected,
                'Tracked directory changed during diagnostic; no metadata report produced',
                str(directory.relative_to(helper.REPO)))
    for name, expected in observed.items():
        helper.physical((helper.REPO / name).parent)
        info = os.lstat(str(helper.REPO / name))
        require((info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_uid, info.st_gid) == expected,
                'Tracked metadata changed during diagnostic; no metadata report produced', name)
    return {'result': 'TRACKED_METADATA_REPORT', 'head': head, 'caller_uid': caller_uid,
            'caller_gid': caller_gid, 'tracked_files_checked': len(tree),
            'contents_checked': False, 'mismatches': rows}

def main():
    helper = None
    try:
        require(len(sys.argv) == 2, 'Pass the checksum-verified alignment helper file')
        helper = load_helper(Path(sys.argv[1]))
        report = scan(helper)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 0
    except Exception as error:
        report = {'result': 'REFUSED'}
        if isinstance(error, Refusal):
            report['reason'] = error.reason
            if error.path is not None:
                report['path'] = error.path
        elif helper is not None and isinstance(error, helper.Refusal) and str(error) in helper.SAFE_REFUSAL_REASONS:
            report['reason'] = str(error)
        else:
            report['reason'] = 'Read-only metadata check stopped; raw error text is withheld'
            if isinstance(error, OSError) and type(error.errno) is int:
                report['errno'] = error.errno
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 1

if __name__ == '__main__':
    sys.exit(main())
