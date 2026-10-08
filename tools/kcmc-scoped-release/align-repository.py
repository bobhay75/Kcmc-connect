#!/usr/bin/env python3
"""Align the cPanel checkout only after the scoped runtime installation succeeds.

Python 3.6+. The target is the exact approved October 8 runtime CI commit.
Origin HTTPS/SSH forms identify the repository; fetch uses public HTTPS only.
No stash, reset, discard, push, cPanel deployment, or config edits are used.
"""
from __future__ import print_function
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

REPO = Path('/home/bobsome1/repositories/Kcmc-connect-live')
BASE = 'ae004a659a7c2fb334296fa41f54dd5263f4d5c0'
TARGET = 'f4442fc4cce2121828544b79b8ba3591c5fe0dab'
URL = 'https://github.com/bobhay75/Kcmc-connect.git'
ORIGINS = set([URL, URL[:-4], 'git@github.com:bobhay75/Kcmc-connect.git',
               'git@github.com:bobhay75/Kcmc-connect',
               'ssh://git@github.com/bobhay75/Kcmc-connect.git',
               'ssh://git@github.com/bobhay75/Kcmc-connect'])
LIMIT = 32 * 1024 * 1024

class Refusal(Exception):
    pass

def require(ok, message):
    if not ok:
        raise Refusal(message)

def regular(path):
    info = os.lstat(str(path))
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            info.st_uid == os.getuid(), 'Nonstandard file ownership/link/type; review required')
    return info

def physical(directory):
    require(directory.is_absolute(), 'Absolute checkout required')
    current = Path('/')
    for part in directory.parts[1:]:
        current = current / part
        info = os.lstat(str(current))
        require(stat.S_ISDIR(info.st_mode), 'Linked or missing checkout directory')
    return (info.st_dev, info.st_ino)

def environment():
    result = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    result.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': '/dev/null',
                   'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_ATTR_NOSYSTEM': '1',
                   'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_OPTIONAL_LOCKS': '0',
                   'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/bin/false',
                   'SSH_ASKPASS': '/bin/false', 'LC_ALL': 'C'})
    return result

OPTIONS = ['-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
           '-c', 'core.attributesFile=/dev/null', '-c', 'core.untrackedCache=false',
           '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
           '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
           '-c', 'fetch.fsckObjects=true', '-c', 'transfer.fsckObjects=true',
           '-c', 'fetch.writeCommitGraph=false', '-c', 'submodule.recurse=false',
           '-c', 'merge.autoStash=false', '-c', 'merge.verifySignatures=false',
           '-c', 'branch.main.mergeOptions=',
           '-c', 'credential.helper=', '-c', 'http.extraHeader=',
           '-c', 'http.sslVerify=true', '-c', 'protocol.allow=never',
           '-c', 'protocol.https.allow=always']

def git(args, raw=False):
    command = ['git'] + ([] if raw else OPTIONS + ['-C', str(REPO)]) + args
    result = subprocess.run(command, cwd='/', env=environment(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0, 'Git check/update refused; repository left for review')
    return result.stdout

def settings():
    config = REPO / '.git/config'
    info = regular(config)
    raw = config.read_bytes()
    entries = git(['config', '--file', str(config), '--no-includes', '--null', '--list'], raw=True)
    values = {}
    for item in entries.split(b'\0'):
        if item:
            key, separator, value = item.partition(b'\n')
            require(separator, 'Unexpected Git configuration format')
            values.setdefault(key.decode('utf-8').lower(), []).append(value)
    blocked = ('include.', 'includeif.', 'extensions.', 'filter.', 'url.', 'http.', 'credential.')
    require(not any(key.startswith(blocked) for key in values),
            'Checkout has include/filter/network-extension settings; separate review required')
    for key in ('core.worktree', 'core.sparsecheckout', 'core.sparsecheckoutcone', 'core.splitindex'):
        require(key not in values, 'Checkout uses redirected/sparse/split settings; review required')
    require(values.get('core.bare', [b'false']) == [b'false'], 'Bare checkout refused')
    origins = values.get('remote.origin.url', [])
    require(len(origins) == 1 and origins[0].decode('utf-8') in ORIGINS,
            'Origin is not the expected credential-free GitHub repository')
    return (hashlib.sha256(raw).hexdigest(), stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)

def standard_repo():
    identity = physical(REPO)
    physical(REPO / '.git')
    regular(REPO / '.git/HEAD')
    require((REPO / '.git/HEAD').read_bytes() == b'ref: refs/heads/main\n',
            'Checkout is not ordinary main')
    for path in ('commondir', 'shallow', 'info/grafts', 'objects/info/alternates',
                 'objects/info/http-alternates', 'info/sparse-checkout', 'refs/replace', 'worktrees',
                 'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer'):
        require(not (REPO / '.git' / path).exists(), 'Checkout has alternate/shared history or worktree state')
    require(not list((REPO / '.git').glob('sharedindex.*')), 'Shared index requires separate review')
    for directory, dirs, files in os.walk(str(REPO / '.git'), followlinks=False):
        for name in dirs:
            physical(Path(directory) / name)
        for name in files:
            regular(Path(directory) / name)
    attrs = REPO / '.git/info/attributes'
    require(not attrs.exists() or attrs.stat().st_size == 0, 'Local conversion attributes require review')
    config = settings()
    version = git(['--version'], raw=True).decode('ascii')
    match = re.search(r'git version (\d+)\.(\d+)', version)
    require(match and tuple(map(int, match.groups())) >= (2, 32), 'Git 2.32+ is required')
    require(git(['rev-parse', '--show-toplevel']).strip() == str(REPO).encode(), 'Worktree location mismatch')
    require(git(['rev-parse', '--absolute-git-dir']).strip() == str(REPO / '.git').encode(), 'Git directory mismatch')
    return identity, config

def source_tree(commit):
    tree = {}
    for entry in git(['ls-tree', '-rz', '--full-tree', commit]).split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        path = name.decode('utf-8')
        require(mode in (b'100644', b'100755') and kind == b'blob' and
                all(part not in ('', '.', '..') for part in path.split('/')) and
                not path.startswith('/') and not path.endswith('/.gitattributes') and
                path not in ('.gitattributes', '.gitmodules'), 'Nonstandard source tree requires review')
        tree[path] = (mode, oid)
    return tree

def clean(commit):
    require(git(['rev-parse', '--verify', 'HEAD']).strip().decode('ascii') == commit,
            'HEAD changed; no update authorized for this checkout')
    tree = source_tree(commit)
    require(all(not entry or entry.startswith(b'H ') for entry in
                git(['ls-files', '-v', '-z']).split(b'\0')),
            'Assume-unchanged or skip-worktree flags require review')
    index = {}
    for entry in git(['ls-files', '--stage', '-z']).split(b'\0'):
        if entry:
            header, name = entry.split(b'\t', 1)
            mode, oid, stage = header.split()
            require(stage == b'0', 'Unmerged index requires review')
            index[name.decode('utf-8')] = (mode, oid)
    require(index == tree, 'Staged changes require review; nothing will be discarded')
    seen = set()
    for directory, dirs, files in os.walk(str(REPO), followlinks=False):
        if Path(directory) == REPO:
            dirs.remove('.git')
        for name in dirs:
            info = os.lstat(str(Path(directory) / name))
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                    info.st_gid == os.getgid(), 'Nonstandard worktree directory ownership/link')
        for name in files:
            path = Path(directory) / name
            relative = str(path.relative_to(REPO))
            require(relative in tree, 'Untracked or ignored files require review; nothing will be discarded')
            info = regular(path)
            mode, oid = tree[relative]
            require(info.st_gid == os.getgid() and stat.S_IMODE(info.st_mode) ==
                    (0o755 if mode == b'100755' else 0o644), 'Local file modes/ownership require review')
            require(info.st_size <= LIMIT, 'Oversized tracked file requires review')
            data = path.read_bytes()
            digest = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest().encode()
            require(digest == oid, 'Tracked edits require review; nothing will be discarded')
            seen.add(relative)
    require(seen == set(tree), 'Missing tracked files require review')
    require(not git(['status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignored']),
            'Worktree/index flags or local changes require review')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'align'])
    args = parser.parse_args()
    update_started = False
    try:
        identity, config = standard_repo()
        clean(BASE)
        if args.action == 'check':
            print('Repository baseline is clean and ordinary. No files or refs changed.')
            return 0
        require(re.match(r'\A[0-9a-f]{40}\Z', TARGET),
                'Alignment is on hold until the approved Oct 8 target and successful install are verified')
        git(['fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
             '--no-auto-maintenance', URL, TARGET])
        require(git(['cat-file', '-t', TARGET]).strip() == b'commit', 'Pinned target is not a commit')
        git(['merge-base', '--is-ancestor', BASE, TARGET])
        source_tree(TARGET)
        require(physical(REPO) == identity and settings() == config, 'Checkout/settings changed during fetch')
        clean(BASE)
        caller_umask = os.umask(0o022)
        try:
            update_started = True
            git(['merge', '--ff-only', '--no-autostash', '--no-verify-signatures', TARGET])
        finally:
            os.umask(caller_umask)
        require(physical(REPO) == identity and settings() == config, 'Checkout/settings changed during update')
        clean(TARGET)
        print('Repository main aligned to approved commit. No live app deployment was invoked.')
        return 0
    except (Refusal, OSError, ValueError, UnicodeError):
        if update_started:
            print('REVIEW REQUIRED: checkout update was attempted but could not be verified. Inspect repository HEAD/worktree before retrying; no live app deployment was invoked.', file=sys.stderr)
        else:
            print('REFUSED: repository alignment stopped before the checkout update; no stash/reset/discard or live deployment was used.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
