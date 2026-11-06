#!/usr/bin/env python3
"""Read-only comparison of a review package and an explicitly selected host tree.

Prints hashes of a fixed set of public/application files and existence of protected
paths. It does not read configuration, private records, or editorial content.
It does not install, modify or remove anything.
"""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

FILES = ['index.php', 'bulletin.php', 'care.php', 'lib/bootstrap.php',
         'lib/screen-navigation.php', 'admin/index.php', 'admin/home.php',
         'admin/login.php', 'admin/setup.php', 'admin/save.php', 'admin/posts.php',
         'admin/event-create.php', 'admin/connections.php', 'admin/rsvps.php',
         'member/login.php', 'member/logout.php', 'sw.js', '.htaccess']
PROTECTED = ['config.php', 'data/content.json', 'data/private', 'backups']

def inspect(root, relative, digest):
    path = root
    for part in relative.split('/'):
        path = path / part
        try: info = path.lstat()
        except FileNotFoundError: return {'state':'missing'}
        if stat.S_ISLNK(info.st_mode): return {'state':'symlink'}
    if not digest: return {'state':'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'other'}
    if not stat.S_ISREG(info.st_mode): return {'state':'not_regular'}
    h=hashlib.sha256()
    try:
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1024*1024),b''): h.update(block)
    except OSError: return {'state':'unreadable'}
    return {'state':'file','sha256':h.hexdigest()}

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('host_root',type=Path)
p.add_argument('candidate_root',type=Path)
a=p.parse_args()
host=a.host_root.resolve(strict=True); candidate=a.candidate_root.resolve(strict=True)
if not host.is_dir() or not candidate.is_dir() or host==candidate or host in candidate.parents or candidate in host.parents:
    p.error('provide two distinct, non-overlapping directories')
result={'mode':'read-only','files':{},'protected_presence':{}}
for path in FILES:
    left=inspect(host,path,True); right=inspect(candidate,path,True)
    result['files'][path]={'host':left,'candidate':right,'same':left.get('state')=='file' and left==right}
for path in PROTECTED: result['protected_presence'][path]=inspect(host,path,False)
result['limitations']=['No private/config/editorial content was read.', 'Scheduled jobs, active sessions, server configuration and mail were not inspected.', 'Differences are not authorization to deploy.']
print(json.dumps(result,indent=2,sort_keys=True))
