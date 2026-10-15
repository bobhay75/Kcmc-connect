#!/usr/bin/env python3
"""Pinned KCMC owner account/UI repair; Python 3.6+, offline, reversible."""
from __future__ import print_function
import argparse
import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import types

VARIANTS = ('main93',)
PRIVATE_BACKUP_ROOT = '/home/bobsome1/kcmc-owner-guard-backups'
PHP82_LOCATIONS = (
    '/opt/cpanel/ea-php82/root/usr/bin/php',
    '/opt/alt/php82/usr/bin/php',
    '/opt/alt/php82/usr/bin/php-cli',
    '/usr/local/bin/ea-php82',
)
EMBEDDED = {'main93': ['#!/usr/bin/env python3\n"""Four pinned KCMC owner guards; Python 3.6+, offline, no application execution."""\nfrom __future__ import print_function\n\nimport argparse\nimport contextlib\nimport datetime\nimport fcntl\nimport hashlib\nimport json\nimport os\nfrom pathlib import Path\nimport re\nimport signal\nimport stat\nimport subprocess\nimport sys\nimport uuid\n\nAPP = Path(\'/home/bobsome1/public_html/kcmc-connect\')\nBACKUPS = Path(\'/home/bobsome1/kcmc-owner-guard-backups\')\nUID, GID = 2162, 2147\nPHP = \'/opt/cpanel/ea-php82/root/usr/bin/php\'\nRELEASE = \'kcmc-owner-guard-20261015-main93\'\nPATHS = (\'lib/password-lifecycle.php\', \'admin/users.php\', \'admin/password-resets.php\', \'member/notifications.php\')\nMAX_BYTES = 131072\n# GENERATED_REVIEWED_REPLACEMENTS\nFILES = json.loads(\'{"lib/password-lifecycle.php":{"before_sha256":"6ae3f838d154bbe83d2bb5edfa77132cdc006bf9be5236977110e2cf2fd0c85e","after_sha256":"80f49fd1de0a073c5d8a2bb224831e57ba85ad89c2e3e3d2a44db2cb64fa9692","before_bytes":6046,"after_bytes":6103,"replacements":[["    if ($actorId === \\\'\\\' || $targetId === \\\'\\\' || hash_equals($actorId, $targetId)) return false;\\\\n    $actorRole = kcmc_role($actor);","    if ($actorId === \\\'\\\' || $targetId === \\\'\\\' || hash_equals($actorId, $targetId)) return false;\\\\n    if (kcmc_is_designated_owner($target)) return false;\\\\n    $actorRole = kcmc_role($actor);"]]},"admin/users.php":{"before_sha256":"7eee24ce34d9d3fabe0fb227f3c92f93d4339f80389d82584b6a58be4c9faed3","after_sha256":"66f3871c779251bc35b0d96b40df2fc36a7d6e357e701f164f50cf06cd848555","before_bytes":15525,"after_bytes":15783,"replacements":[["            elseif ($targetId === ($current[\\\'id\\\'] ?? \\\'\\\')) $error = \\\'You cannot disable your own account.\\\';\\\\n","            elseif ($targetId === ($current[\\\'id\\\'] ?? \\\'\\\')) $error = \\\'You cannot disable your own account.\\\';\\\\n            elseif (kcmc_is_designated_owner($target)) $error = \\\'Another administrator cannot change the designated owner account.\\\';\\\\n"],["<?php if (($member[\\\'id\\\'] ?? \\\'\\\') !== ($current[\\\'id\\\'] ?? \\\'\\\')): ?><form method=\\\\"post\\\\"><input type=\\\\"hidden\\\\" name=\\\\"csrf\\\\" value=\\\\"<?=kcmc_h(kcmc_csrf())?>\\\\"><input type=\\\\"hidden\\\\" name=\\\\"action\\\\" value=\\\\"set_active\\\\">","<?php if (($member[\\\'id\\\'] ?? \\\'\\\') !== ($current[\\\'id\\\'] ?? \\\'\\\') && !kcmc_is_designated_owner($member)): ?><form method=\\\\"post\\\\"><input type=\\\\"hidden\\\\" name=\\\\"csrf\\\\" value=\\\\"<?=kcmc_h(kcmc_csrf())?>\\\\"><input type=\\\\"hidden\\\\" name=\\\\"action\\\\" value=\\\\"set_active\\\\">"],["<?php else: ?>Current user<?php endif; ?></span></div><?php endforeach; ?>","<?php else: ?><?=($member[\\\'id\\\'] ?? \\\'\\\') === ($current[\\\'id\\\'] ?? \\\'\\\') ? \\\'Current user\\\' : \\\'Designated owner account\\\'?><?php endif; ?></span></div><?php endforeach; ?>"]]},"admin/password-resets.php":{"before_sha256":"d32838fe3d7483bb4ba6fbd1fc948672d6187bd34c0c47c65c5ed720fd75f4af","after_sha256":"263a233c57c4413378c7839736af4131850dc84f8dac82a6268f829e19107157","before_bytes":7967,"after_bytes":8206,"replacements":[["$error = \\\'This account is outside your password-reset authority. Use Account Security for your own password; elevated administrator resets require the Recovery administrator.\\\';","$error = kcmc_is_designated_owner($target) ? \\\'Another administrator cannot reset the designated owner account. The owner can change their password through Account Security.\\\' : \\\'This account is outside your password-reset authority. Use Account Security for your own password; elevated administrator resets require the Recovery administrator.\\\';"],["<?php else: ?><span class=\\\\"portal-fine\\\\">Recovery administrator required</span><?php endif; ?>","<?php else: ?><span class=\\\\"portal-fine\\\\"><?=kcmc_is_designated_owner($target) ? \\\'Designated owner account\\\' : \\\'Recovery administrator required\\\'?></span><?php endif; ?>"]]},"member/notifications.php":{"before_sha256":"58c1c85095270ce554a097e260f61ef4c0fff4807a82c1bb8dbc787ba1fa069c","after_sha256":"ba09e7eb974c1f36ff545cfca6bc9f6ea855933eb74c3db1595ec182c151afcf","before_bytes":2357,"after_bytes":2365,"replacements":[["<?php if (kcmc_can_publish($user)): ?><a class=\\\\"btn secondary\\\\" href=\\\\"<?=kcmc_h(kcmc_url(\\\'admin/push.php\\\'))?>\\\\">Send update</a><?php endif; ?>","<?php if (kcmc_is_designated_owner($user)): ?><a class=\\\\"btn secondary\\\\" href=\\\\"<?=kcmc_h(kcmc_url(\\\'admin/push.php\\\'))?>\\\\">Send update</a><?php endif; ?>"]]}}\')\nLEASE_KEYS = (\'sha256\', \'bytes\', \'dev\', \'ino\', \'mtime_ns\', \'ctime_ns\', \'mode\', \'uid\', \'gid\', \'nlink\')\n\n\nclass Refusal(RuntimeError):\n    pass\n\n\ndef require(ok, message):\n    if not ok:\n        raise Refusal(message)\n\n\ndef digest(data):\n    return hashlib.sha256(data).hexdigest()\n\n\ndef caller():\n    require((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) == (UID, UID, GID, GID),\n            \'Run as the hosting account UID 2162 / GID 2147; no change made\')\n\n\ndef inventory():\n    require(tuple(FILES) == PATHS, \'Repair inventory is not exactly the four reviewed files\')\n    require(APP.is_absolute() and BACKUPS.is_absolute() and APP != BACKUPS and\n            \'public_html\' not in BACKUPS.parts, \'Invalid fixed repair roots\')\n    for path in PATHS:\n        item = FILES[path]\n        require(set(item) == set([\'before_sha256\', \'after_sha256\', \'before_bytes\', \'after_bytes\', \'replacements\']),\n                \'Invalid embedded repair inventory\')\n        require(all(re.match(r\'\\A[0-9a-f]{64}\\Z\', item[key]) for key in (\'before_sha256\', \'after_sha256\')) and\n                all(isinstance(item[key], int) and 0 < item[key] <= MAX_BYTES for key in (\'before_bytes\', \'after_bytes\')),\n                \'Invalid embedded code hashes\')\n        require(isinstance(item[\'replacements\'], list) and item[\'replacements\'] and\n                all(isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) for v in pair) and pair[0]\n                    for pair in item[\'replacements\']), \'Invalid embedded replacements\')\n\n\nclass Parent(object):\n    """Retain every no-follow ancestor descriptor until its operation finishes."""\n    def __init__(self, path):\n        self.path, self.opened = Path(path), []\n\n    def __enter__(self):\n        require(self.path.is_absolute(), \'Absolute parent required\')\n        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW\n        fd = os.open(\'/\', flags)\n        self.opened.append((fd, Path(\'/\')))\n        current = Path(\'/\')\n        try:\n            for part in self.path.parts[1:]:\n                current = current / part\n                fd = os.open(part, flags, dir_fd=fd)\n                self.opened.append((fd, current))\n            self.fd = fd\n            self.check()\n            return self\n        except BaseException:\n            self.__exit__(None, None, None)\n            raise\n\n    def check(self):\n        for fd, path in self.opened:\n            visible, held = os.lstat(str(path)), os.fstat(fd)\n            require(stat.S_ISDIR(visible.st_mode) and (visible.st_dev, visible.st_ino) == (held.st_dev, held.st_ino),\n                    \'A parent directory changed or became linked\')\n            if path == APP or APP in path.parents:\n                require((visible.st_uid, visible.st_gid) == (UID, GID) and\n                        not (stat.S_IMODE(visible.st_mode) & 0o7002), \'Unsafe application directory owner/mode\')\n            if path == BACKUPS or BACKUPS in path.parents:\n                require((visible.st_uid, visible.st_gid, stat.S_IMODE(visible.st_mode)) == (UID, GID, 0o700),\n                        \'Unsafe private directory owner/mode\')\n\n    def __exit__(self, *args):\n        for fd, _ in reversed(self.opened):\n            os.close(fd)\n        self.opened = []\n\n\ndef metadata(info, data):\n    return {\'sha256\': digest(data), \'bytes\': len(data), \'dev\': info.st_dev, \'ino\': info.st_ino,\n            \'mtime_ns\': info.st_mtime_ns, \'ctime_ns\': info.st_ctime_ns, \'mode\': stat.S_IMODE(info.st_mode),\n            \'uid\': info.st_uid, \'gid\': info.st_gid, \'nlink\': info.st_nlink}\n\n\ndef same(actual, expected):\n    return all(actual[key] == expected[key] for key in LEASE_KEYS)\n\n\ndef read_at(parent, name):\n    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, \'O_NOATIME\', 0)\n    fd = os.open(name, flags, dir_fd=parent.fd)\n    try:\n        before = os.fstat(fd)\n        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == UID and before.st_gid == GID,\n                \'Nonregular, linked or foreign-owned file refused\')\n        require(0 < before.st_size <= MAX_BYTES, \'Unexpected code/metadata size\')\n        chunks, size = [], 0\n        while True:\n            part = os.read(fd, 65536)\n            if not part:\n                break\n            chunks.append(part)\n            size += len(part)\n            require(size <= MAX_BYTES, \'Oversized file refused\')\n        data = b\'\'.join(chunks)\n        after = os.fstat(fd)\n        first, last = metadata(before, data), metadata(after, data)\n        require(same(first, last) and len(data) == before.st_size, \'File changed during read\')\n        visible = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)\n        require(same(metadata(visible, data), last) and stat.S_ISREG(visible.st_mode), \'File replaced during read\')\n        parent.check()\n        return data, last\n    finally:\n        os.close(fd)\n\n\ndef read(path):\n    path = Path(path)\n    with Parent(path.parent) as parent:\n        return read_at(parent, path.name)\n\n\ndef live(path):\n    data, info = read(APP / path)\n    require(info[\'mode\'] in (0o644, 0o664), \'Code mode must already be 0644 or 0664: \' + path)\n    return data, info\n\n\ndef verify_lease(path, expected):\n    _, actual = live(path)\n    require(same(actual, expected), \'Code lease changed: \' + path)\n    return actual\n\n\ndef inspect():\n    caller()\n    inventory()\n    found, kinds = {}, []\n    for path in PATHS:\n        data, info = live(path)\n        item = FILES[path]\n        matches = [kind for kind in (\'before\', \'after\') if info[\'sha256\'] == item[kind + \'_sha256\'] and\n                   info[\'bytes\'] == item[kind + \'_bytes\']]\n        require(len(matches) == 1, \'Unknown code bytes: \' + path)\n        kinds.append(matches[0])\n        found[path] = (data, info)\n    require(len(set(kinds)) == 1, \'Mixed before/after code bundle refused; no repair made\')\n    for path in PATHS:\n        verify_lease(path, found[path][1])\n    return kinds[0], found\n\n\ndef repair(path, data):\n    item = FILES[path]\n    require(digest(data) == item[\'before_sha256\'] and len(data) == item[\'before_bytes\'], \'Repair preimage changed\')\n    for old, new in item[\'replacements\']:\n        old, new = old.encode(\'utf-8\'), new.encode(\'utf-8\')\n        require(data.count(old) == 1, \'Repair anchor is not unique: \' + path)\n        data = data.replace(old, new, 1)\n    require(digest(data) == item[\'after_sha256\'] and len(data) == item[\'after_bytes\'], \'Repair output hash mismatch\')\n    return data\n\n\ndef private_dir(path, create=False):\n    path = Path(path)\n    with Parent(path.parent) as parent:\n        if create:\n            try:\n                os.mkdir(path.name, 0o700, dir_fd=parent.fd)\n                os.fsync(parent.fd)\n            except FileExistsError:\n                pass\n        info = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)\n        require(stat.S_ISDIR(info.st_mode) and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (UID, GID, 0o700),\n                \'Backup directory owner/group/mode refused\')\n        parent.check()\n\n\ndef write_private(path, data):\n    path = Path(path)\n    with Parent(path.parent) as parent:\n        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent.fd)\n        try:\n            os.fchmod(fd, 0o600)\n            require((os.fstat(fd).st_uid, os.fstat(fd).st_gid) == (UID, GID), \'Staging ownership refused\')\n            view = memoryview(data)\n            while view:\n                n = os.write(fd, view)\n                require(n > 0, \'Private write failed\')\n                view = view[n:]\n            os.fsync(fd)\n            parent.check()\n            visible = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)\n            held = os.fstat(fd)\n            require((visible.st_dev, visible.st_ino, visible.st_nlink) == (held.st_dev, held.st_ino, 1),\n                    \'Private file path changed\')\n            os.fsync(parent.fd)\n        finally:\n            os.close(fd)\n\n\ndef replace(source, target, **kwargs):\n    os.replace(source, target, **kwargs)\n\n\ndef journal(session, value):\n    private_dir(session)\n    path = Path(session) / \'journal.json\'\n    try:\n        _, info = read(path)\n        require(info[\'mode\'] == 0o600, \'Unsafe journal mode\')\n    except FileNotFoundError:\n        pass\n    temporary = Path(session) / (\'.journal-\' + uuid.uuid4().hex)\n    write_private(temporary, (json.dumps(value, indent=2, sort_keys=True) + \'\\n\').encode(\'ascii\'))\n    with Parent(session) as parent:\n        parent.check()\n        replace(temporary.name, path.name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)\n        os.fsync(parent.fd)\n        parent.check()\n\n\ndef session_name(name):\n    require(isinstance(name, str) and re.match(r\'\\Arepair-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\\Z\', name),\n            \'Use the exact private repair session name\')\n    return BACKUPS / name\n\n\ndef load(session):\n    require(Path(session).parent == BACKUPS, \'Session escaped fixed backup root\')\n    session_name(Path(session).name)\n    private_dir(BACKUPS)\n    private_dir(session)\n    data, meta = read(Path(session) / \'journal.json\')\n    require(meta[\'mode\'] == 0o600, \'Unsafe journal permissions\')\n    value = json.loads(data.decode(\'ascii\'))\n    require(isinstance(value, dict) and set(value) == set([\'release\', \'app\', \'phase\', \'intent\', \'uncertain\', \'files\']) and\n            value[\'release\'] == RELEASE and value[\'app\'] == str(APP) and isinstance(value[\'files\'], dict) and\n            set(value[\'files\']) == set(PATHS) and\n            value[\'phase\'] in (\'prepared\', \'applying\', \'applied\', \'rolling_back\', \'rolled_back\', \'manual_review\') and\n            (value[\'intent\'] is None or value[\'intent\'] in PATHS) and isinstance(value[\'uncertain\'], list) and\n            all(isinstance(path, str) for path in value[\'uncertain\']) and\n            len(set(value[\'uncertain\'])) == len(value[\'uncertain\']) and\n            all(path in PATHS for path in value[\'uncertain\']), \'Journal scope/phase refused\')\n    for path in PATHS:\n        record = value[\'files\'][path]\n        require(isinstance(record, dict) and set(record) == set([\'original\', \'candidate\', \'installed\']), \'Invalid journal file record\')\n        for kind, info in record.items():\n            require(info is None and kind != \'original\' or isinstance(info, dict) and set(info) == set(LEASE_KEYS) and\n                    isinstance(info[\'sha256\'], str) and re.match(r\'\\A[0-9a-f]{64}\\Z\', info[\'sha256\']) and\n                    all(type(info[key]) is int and info[key] >= 0 for key in LEASE_KEYS if key != \'sha256\') and\n                    info[\'mode\'] in (0o644, 0o664) and info[\'uid\'] == UID and info[\'gid\'] == GID and info[\'nlink\'] == 1,\n                    \'Invalid journal lease\')\n            if info is not None:\n                source = \'before\' if kind == \'original\' else \'after\'\n                require(info[\'sha256\'] == FILES[path][source + \'_sha256\'] and info[\'bytes\'] == FILES[path][source + \'_bytes\'],\n                        \'Journal code source mismatch\')\n    return value\n\n\ndef unfinished(except_session=None):\n    try:\n        private_dir(BACKUPS)\n    except FileNotFoundError:\n        return\n    with Parent(BACKUPS) as parent:\n        names = os.listdir(parent.fd)\n        parent.check()\n    for name in names:\n        if not name.startswith(\'repair-\') or name == except_session:\n            continue\n        value = load(session_name(name))\n        require(value[\'phase\'] in (\'applied\', \'rolled_back\'), \'Unfinished repair requires review: \' + name)\n\n\n@contextlib.contextmanager\ndef locked():\n    private_dir(BACKUPS, create=True)\n    with Parent(BACKUPS) as parent:\n        fd = os.open(\'.repair.lock\', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent.fd)\n        try:\n            info = os.fstat(fd)\n            require(stat.S_ISREG(info.st_mode) and (info.st_nlink, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (1, UID, GID, 0o600),\n                    \'Unsafe repair lock\')\n            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n            visible = os.stat(\'.repair.lock\', dir_fd=parent.fd, follow_symlinks=False)\n            require((visible.st_dev, visible.st_ino) == (info.st_dev, info.st_ino), \'Repair lock path changed\')\n            def check_lock():\n                parent.check()\n                current = os.stat(\'.repair.lock\', dir_fd=parent.fd, follow_symlinks=False)\n                held = os.fstat(fd)\n                require(stat.S_ISREG(current.st_mode) and\n                        (current.st_dev, current.st_ino, current.st_nlink, current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode)) ==\n                        (info.st_dev, info.st_ino, 1, UID, GID, 0o600) and\n                        (held.st_dev, held.st_ino, held.st_nlink) == (info.st_dev, info.st_ino, 1), \'Repair lock lease changed\')\n            check_lock()\n            yield check_lock\n            check_lock()\n        finally:\n            os.close(fd)\n\n\ndef lint(session):\n    """Verify exact staged bytes and PHP syntax without executing application code."""\n    version = subprocess.check_output([PHP, \'-n\', \'-v\'], stderr=subprocess.STDOUT, timeout=15)\n    require(re.match(br\'\\APHP 8\\.2\\.[0-9]+\\b\', version) is not None, \'Fixed PHP 8.2 CLI required\')\n    for index, path in enumerate(PATHS):\n        staged = Path(session) / (\'stage-\' + str(index) + \'.code\')\n        data, info = read(staged)\n        item = FILES[path]\n        require(info[\'mode\'] == 0o600 and info[\'sha256\'] == item[\'after_sha256\'] and\n                info[\'bytes\'] == item[\'after_bytes\'], \'Pinned stage bytes changed\')\n        subprocess.check_output([PHP, \'-n\', \'-l\', str(staged)], stderr=subprocess.STDOUT, timeout=15)\n\ndef bundle_lease(value, check_lock):\n    check_lock()\n    for path in PATHS:\n        record = value[\'files\'][path]\n        verify_lease(path, record[\'installed\'] or record[\'original\'])\n\n\ndef backup_device():\n    with Parent(BACKUPS) as parent:\n        return os.fstat(parent.fd).st_dev\n\n\ndef move_code(source, path, expected, staged_expected, check_lock):\n    target = APP / path\n    with Parent(source.parent) as src, Parent(target.parent) as dst:\n        _, staged = read_at(src, source.name)\n        require(same(staged, staged_expected), \'Stage lease changed\')\n        require(staged[\'dev\'] == expected[\'dev\'], \'Stage and code target must use the same filesystem\')\n        _, actual = read_at(dst, target.name)\n        require(same(actual, expected), \'Target lease changed before replacement\')\n        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, \'O_NOATIME\', 0)\n        source_fd = os.open(source.name, flags, dir_fd=src.fd)\n        try:\n            target_fd = os.open(target.name, flags, dir_fd=dst.fd)\n            try:\n                # Keep both file descriptors through rename. The final check catches\n                # namespace/in-place changes; os.replace itself is not a kernel CAS.\n                check_lock()\n                src.check()\n                dst.check()\n                for parent, name, fd, lease in ((src, source.name, source_fd, staged_expected),\n                                               (dst, target.name, target_fd, expected)):\n                    held, visible = os.fstat(fd), os.stat(name, dir_fd=parent.fd, follow_symlinks=False)\n                    require(stat.S_ISREG(held.st_mode) and stat.S_ISREG(visible.st_mode) and\n                            all(metadata(held, b\'\')[key] == lease[key] and metadata(visible, b\'\')[key] == lease[key]\n                                for key in LEASE_KEYS if key not in (\'sha256\', \'bytes\')) and held.st_size == lease[\'bytes\'],\n                            \'Final file descriptor/path lease changed\')\n                replace(source.name, target.name, src_dir_fd=src.fd, dst_dir_fd=dst.fd)\n                os.fsync(dst.fd)\n                src.check()\n                dst.check()\n                check_lock()\n                _, installed = read_at(dst, target.name)\n                # Rename updates ctime; every other held candidate field must match.\n                require(all(installed[key] == staged_expected[key] for key in LEASE_KEYS if key != \'ctime_ns\'),\n                        \'Installed code identity changed\')\n                return installed\n            finally:\n                os.close(target_fd)\n        finally:\n            os.close(source_fd)\n\n\ndef set_stage_mode(path, mode):\n    with Parent(path.parent) as parent:\n        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent.fd)\n        try:\n            held = os.fstat(fd)\n            require(stat.S_ISREG(held.st_mode) and (held.st_nlink, held.st_uid, held.st_gid, stat.S_IMODE(held.st_mode)) == (1, UID, GID, 0o600),\n                    \'Unsafe private stage\')\n            os.fchmod(fd, mode)\n            os.fsync(fd)\n            parent.check()\n            _, info = read_at(parent, path.name)\n            require((info[\'dev\'], info[\'ino\']) == (held.st_dev, held.st_ino), \'Stage path replaced\')\n            return info\n        finally:\n            os.close(fd)\n\n\ndef restore_owned(session, value, check_lock):\n    """Restore only verified installed identities; intent alone never grants ownership."""\n    uncertain = list(value[\'uncertain\'])\n    if value[\'intent\'] is not None and value[\'intent\'] not in uncertain:\n        uncertain.append(value[\'intent\'])\n    value[\'uncertain\'] = uncertain\n    conflicts = []\n    value[\'phase\'] = \'rolling_back\'\n    try:\n        journal(session, value)\n    except BaseException:\n        pass  # Existing durable intent remains; leases also remain in memory.\n    for index in reversed(range(len(PATHS))):\n        path = PATHS[index]\n        record = value[\'files\'][path]\n        if record[\'installed\'] is None or path in uncertain:\n            continue\n        try:\n            check_lock()\n            verify_lease(path, record[\'installed\'])\n            data, original_meta = read(Path(session) / (\'original-\' + str(index) + \'.code\'))\n            require(original_meta[\'mode\'] == 0o600 and digest(data) == record[\'original\'][\'sha256\'], \'Original backup changed\')\n            staged = Path(session) / (\'restore-\' + uuid.uuid4().hex + \'.code\')\n            write_private(staged, data)\n            candidate = set_stage_mode(staged, record[\'original\'][\'mode\'])\n            verify_lease(path, record[\'installed\'])\n            value[\'intent\'] = path\n            journal(session, value)\n            restored = move_code(staged, path, record[\'installed\'], candidate, check_lock)\n            record[\'original\'] = restored\n            record[\'installed\'] = None\n            record[\'candidate\'] = None\n            value[\'intent\'] = uncertain[-1] if uncertain else None\n            journal(session, value)\n        except BaseException:\n            conflicts.append(path)\n            if value[\'intent\'] == path and path not in uncertain:\n                uncertain.append(path)\n    value[\'intent\'] = uncertain[-1] if uncertain else None\n    value[\'phase\'] = \'manual_review\' if uncertain or conflicts else \'rolled_back\'\n    try:\n        journal(session, value)\n    except BaseException:\n        value[\'phase\'] = \'manual_review\'\n    return value[\'phase\'] == \'rolled_back\'\n\n\ndef apply():\n    state, originals = inspect()\n    unfinished()\n    if state == \'after\':\n        return None\n    with locked() as check_lock:\n        unfinished()\n        state, originals = inspect()\n        if state == \'after\':\n            return None\n        device = backup_device()\n        require(all(originals[path][1][\'dev\'] == device for path in PATHS),\n                \'Backup staging and all four code files must use the same filesystem; no replacement made\')\n        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(\'%Y%m%dT%H%M%SZ\')\n        session = session_name(\'repair-\' + stamp + \'-\' + uuid.uuid4().hex)\n        private_dir(session, create=True)\n        value = {\'release\': RELEASE, \'app\': str(APP), \'phase\': \'prepared\', \'intent\': None, \'uncertain\': [],\n                 \'files\': {path: {\'original\': originals[path][1], \'candidate\': None, \'installed\': None} for path in PATHS}}\n        # Durable preparation precedes staging, so interrupted preparation is visible.\n        journal(session, value)\n        for index, path in enumerate(PATHS):\n            write_private(session / (\'original-\' + str(index) + \'.code\'), originals[path][0])\n            write_private(session / (\'stage-\' + str(index) + \'.code\'), repair(path, originals[path][0]))\n        try:\n            lint(session)\n        except BaseException:\n            value[\'phase\'] = \'rolled_back\'\n            journal(session, value)\n            raise Refusal(\'Staged PHP 8.2 syntax verification failed; no live replacement. Private session: \' + str(session))\n        bundle_lease(value, check_lock)\n        value[\'phase\'] = \'applying\'\n        journal(session, value)\n        previous = signal.getsignal(signal.SIGTERM)\n        def interrupted(signum, frame):\n            raise Refusal(\'Repair interrupted\')\n        signal.signal(signal.SIGTERM, interrupted)\n        try:\n            for index, path in enumerate(PATHS):\n                bundle_lease(value, check_lock)\n                staged = session / (\'stage-\' + str(index) + \'.code\')\n                candidate = set_stage_mode(staged, originals[path][1][\'mode\'])\n                require(candidate[\'sha256\'] == FILES[path][\'after_sha256\'], \'Stage bytes changed\')\n                value[\'files\'][path][\'candidate\'] = candidate\n                value[\'intent\'] = path\n                journal(session, value)\n                bundle_lease(value, check_lock)\n                value[\'files\'][path][\'installed\'] = move_code(staged, path, originals[path][1], candidate, check_lock)\n                value[\'intent\'] = None\n                journal(session, value)\n            bundle_lease(value, check_lock)\n            value[\'phase\'] = \'applied\'\n            journal(session, value)\n        except BaseException:\n            signal.signal(signal.SIGTERM, signal.SIG_IGN)\n            complete = restore_owned(session, value, check_lock)\n            raise Refusal((\'Repair failed; verified owned code restored.\' if complete else\n                           \'Repair stopped; uncertain or concurrent changes require manual review.\') +\n                          \' Private session: \' + str(session))\n        finally:\n            signal.signal(signal.SIGTERM, previous)\n        return session\n\n\ndef rollback(name):\n    caller()\n    inventory()\n    session = session_name(name)\n    with locked() as check_lock:\n        unfinished(except_session=name)\n        value = load(session)\n        require(value[\'phase\'] == \'applied\' and value[\'intent\'] is None and not value[\'uncertain\'],\n                \'Only a fully verified applied session may roll back\')\n        bundle_lease(value, check_lock)\n        require(restore_owned(session, value, check_lock), \'Rollback stopped for manual review. Private session: \' + str(session))\n    return session\n\n\ndef main():\n    parser = argparse.ArgumentParser(description=__doc__)\n    parser.add_argument(\'action\', nargs=\'?\', default=\'check\', choices=(\'check\', \'apply\', \'rollback\'))\n    parser.add_argument(\'--session\', help=\'Exact private session basename; rollback only\')\n    args = parser.parse_args()\n    try:\n        require((args.action == \'rollback\') == (args.session is not None), \'Session is required only for rollback\')\n        if args.action == \'check\':\n            state, files = inspect()\n            unfinished()\n            print(\'CHECK \' + (\'READY\' if state == \'before\' else \'ALREADY_REPAIRED\'))\n            for path in PATHS:\n                print(\'CODE \' + path + \' sha256=\' + files[path][1][\'sha256\'])\n            print(\'Read-only check complete; no application, data or repository operation.\')\n        elif args.action == \'apply\':\n            session = apply()\n            print(\'ALREADY_REPAIRED; no replacement or new backup.\' if session is None else \'REPAIRED \' + \', \'.join(PATHS))\n            if session is not None:\n                print(\'PRIVATE_ROLLBACK \' + str(session))\n                print(\'ROLLBACK_COMMAND python3 installer.py rollback --session \' + session.name)\n        else:\n            print(\'ROLLED_BACK \' + str(rollback(args.session)))\n        return 0\n    except (Refusal, OSError, ValueError, subprocess.SubprocessError) as error:\n        # Metadata-only diagnostics: never print subprocess output or source bytes.\n        message = str(error) if isinstance(error, Refusal) else type(error).__name__ + \'; check refused safely\'\n        print(\'REFUSED \' + message, file=sys.stderr)\n        return 1\n\n\nif __name__ == \'__main__\':\n    sys.exit(main())\n', 'd2d18525ed3f17e0c5962ef5e84ebd4075bf318f8811fa25e1287a5e730bb444']}
PREREQUISITE = {'path': 'lib/bootstrap.php', 'sha256': 'd4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263', 'bytes': 24274, 'source_commit': '93c72f4fc430d311e01108d3a30d0561bb701c9d', 'canonical_before_sha256': '96590431ef787a6a689a3c9e1655cdb4cac10c7c86e5cde8f579cd0b3571c518', 'session_fixture_sha256': '85acda478e90d091f46f290018ab4eca65283e380b0eefa87752b1d27a8128c8'}

class Refusal(RuntimeError):
    pass

def require(ok, message):
    if not ok:
        raise Refusal(message)

def load_engines():
    require(set(EMBEDDED)==set(VARIANTS),'Embedded variant inventory refused')
    for variant in VARIANTS:
        source, expected=EMBEDDED[variant]
        require(isinstance(source,str) and isinstance(expected,str) and
                hashlib.sha256(source.encode('utf-8')).hexdigest()==expected,
                'Embedded transaction engine checksum mismatch')
    engines={}
    for variant in VARIANTS:
        source, unused=EMBEDDED[variant]
        module=types.ModuleType('kcmc_owner_'+variant)
        module.__file__='<verified-owner-'+variant+'>'
        exec(compile(source,module.__file__,'exec'),module.__dict__)
        engines[variant]=module
    return engines

@contextlib.contextmanager
def prerequisite_guard(module):
    """Lease the approved bootstrap read-only through the frozen lock callback."""
    module.caller(); module.inventory()
    path = PREREQUISITE['path']
    unused, expected = module.live(path)
    module.require(expected['sha256'] == PREREQUISITE['sha256'] and expected['bytes'] == PREREQUISITE['bytes'],
                   'Approved post-session bootstrap required; no repair made. Use diagnose for code hashes only.')
    module.verify_lease(path, expected)
    frozen_locked = module.locked
    @contextlib.contextmanager
    def guarded_locked():
        module.verify_lease(path, expected)
        with frozen_locked() as frozen_check:
            def checked():
                module.verify_lease(path, expected)
                frozen_check()
                module.verify_lease(path, expected)
            checked()
            yield checked
            checked()
        module.verify_lease(path, expected)
    module.locked = guarded_locked
    try:
        yield expected
    finally:
        module.locked = frozen_locked


def select(engines):
    matches=[]
    refusals=[]
    # Every accepted variant's backup root must be safe and have no unfinished operation.
    for variant in VARIANTS:
        engines[variant].caller()
        engines[variant].inventory()
        engines[variant].unfinished()
    for variant in VARIANTS:
        try:
            state,files=engines[variant].inspect()
            matches.append((variant,state,files))
        except engines[variant].Refusal as error:
            safe={'A parent directory changed or became linked', 'Unsafe application directory owner/mode',
                  'Nonregular, linked or foreign-owned file refused', 'Unexpected code/metadata size',
                  'Oversized file refused', 'File changed during read', 'File replaced during read',
                  'Mixed before/after code bundle refused; no repair made'}
            for path in engines[variant].PATHS:
                safe.update(('Unknown code bytes: '+path, 'Code mode must already be 0644 or 0664: '+path,
                             'Code lease changed: '+path))
            reason=str(error) if str(error) in safe else 'Read-only preflight guard refused'
            refusals.append(variant+': '+reason)
    require(len(matches)==1,'Unknown or mixed owner-guard bundle; no repair made. Use diagnose for code hashes only. '+ '; '.join(refusals))
    return matches[0]

def diagnose(engines):
    """Read only fixed repair/prerequisite code hashes; never account/config contents."""
    module=engines[VARIANTS[0]]
    module.caller();module.inventory()
    found={}
    paths = module.PATHS + (PREREQUISITE['path'],)
    for path in paths:
        unused,found[path]=module.live(path)
    for path in paths:
        module.verify_lease(path,found[path])
    for path in paths:
        info=found[path]
        print('CODE '+path+' sha256='+info['sha256']+' bytes='+str(info['bytes'])+
              ' mode='+format(info['mode'],'04o')+' uid='+str(info['uid'])+
              ' gid='+str(info['gid'])+' links='+str(info['nlink']))
    print('Hashes-only read-only diagnostic complete; no code, backup, data or repository operation.')

def php82_candidates():
    paths=list(PHP82_LOCATIONS)
    # The hosting account's ordinary PHP command is a final compatibility fallback.
    found=shutil.which('php')
    if found:
        paths.append(os.path.abspath(found))
    unique=[]
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique

def choose_php82_cli():
    """Version-only checks, before any private backup creation or staging."""
    for path in php82_candidates():
        try:
            output=subprocess.check_output([path,'-n','-v'],stderr=subprocess.STDOUT,timeout=8)
        except (OSError, subprocess.SubprocessError):
            continue
        match=re.match(br'\APHP (8\.2\.[0-9]+) \(cli\)(?:\s|\Z)',output)
        if match is not None:
            return path,match.group(1).decode('ascii')
    raise Refusal('No compatible PHP 8.2 CLI found; no backup or live replacement made')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='check',choices=('check','diagnose','apply','rollback'))
    parser.add_argument('--variant',choices=VARIANTS,help='Exact installed variant; rollback only')
    parser.add_argument('--session',help='Exact private session basename; rollback only')
    args=parser.parse_args()
    engines={}
    try:
        require((args.action=='rollback')==(args.variant is not None and args.session is not None),
                'Variant and session are required only for rollback')
        require(args.action=='rollback' or (args.variant is None and args.session is None),
                'No variant or session override for check/apply')
        engines=load_engines()
        if args.action=='diagnose':
            diagnose(engines)
        else:
            guarded_module = engines[VARIANTS[0]]
            with prerequisite_guard(guarded_module) as bootstrap_lease:
                if args.action=='rollback':
                    # Do not let another variant's incomplete operation be bypassed.
                    for variant in VARIANTS:
                        if variant!=args.variant:
                            engines[variant].caller();engines[variant].inventory();engines[variant].unfinished()
                    session=engines[args.variant].rollback(args.session)
                    guarded_module.verify_lease(PREREQUISITE['path'], bootstrap_lease)
                    print('ROLLED_BACK '+str(session))
                else:
                    variant,state,files=select(engines)
                    module=engines[variant]
                    print('VARIANT '+variant)
                    if state=='before':
                        php,version=choose_php82_cli()
                        module.PHP=php
                        print('PHP_CLI '+php+' PHP '+version)
                    if args.action=='check':
                        guarded_module.verify_lease(PREREQUISITE['path'], bootstrap_lease)
                        print('CHECK '+('READY' if state=='before' else 'ALREADY_REPAIRED'))
                        for path in module.PATHS:
                            print('CODE '+path+' sha256='+files[path][1]['sha256'])
                        print('Read-only check complete; no application, data or repository operation.')
                    else:
                        session=module.apply()
                        guarded_module.verify_lease(PREREQUISITE['path'], bootstrap_lease)
                        print('ALREADY_REPAIRED; no replacement or new backup.' if session is None else 'REPAIRED '+', '.join(module.PATHS))
                        if session is not None:
                            print('PRIVATE_ROLLBACK '+str(session))
                            print('ROLLBACK_COMMAND python3 installer.py rollback --variant '+variant+' --session '+session.name)
        return 0
    except BaseException as error:
        known=(Refusal,)+tuple(module.Refusal for module in engines.values())
        message=str(error) if isinstance(error,known) else 'Unexpected failure; refused safely'
        if message == 'Code lease changed: ' + PREREQUISITE['path']:
            message += '; existing private journals and installed leases are preserved for manual review'
        print('REFUSED '+message,file=sys.stderr)
        print('PRIVATE_BACKUP_ROOT '+PRIVATE_BACKUP_ROOT,file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
