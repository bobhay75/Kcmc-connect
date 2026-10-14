#!/usr/bin/env python3
"""Pinned KCMC code transaction. Python 3.6+, no application bootstrap."""
from __future__ import print_function

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import ssl
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

APP_ROOT = Path('/home/bobsome1/public_html/kcmc-connect')
BACKUP_ROOT = Path('/home/bobsome1/kcmc-release-backups')
COMMIT = '154b779a0ea3d27a11300bfe0454f8a7c4aca355'
SOURCE_ROOT = 'https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' + COMMIT + '/KCMC-Connect-Phase6-Recreated/'
PUBLIC_ROOT = 'https://bobsome1.com/kcmc-connect/'
MAX_BYTES = 16 * 1024 * 1024
CONTENT_PATH = 'data/content.json'
PUBLISHER_STORES = ('publications.json', 'publication-media.json')
BASELINE_IDS = ('268bebca444bd4970bb4ecaa0d6eceb6a11988fd', '4225fce8968747ad4f828a9a36087b04fd020484')
# Two complete allowlisted preimage bundles; no mixtures of their bytes are accepted.
BASELINES = json.loads('{"268bebca444bd4970bb4ecaa0d6eceb6a11988fd": {"admin/publication-designer.php": {"bytes": 36010, "mode": 420, "sha256": "b9e05cd22cbb5b98f04031f548ca7237661827c367d6608669adf8df4e612758"}, "assets/icons/icon-512.png": {"bytes": 4769, "mode": 420, "sha256": "e14220ab44f5061853e0fcb8db711e2d08acb8ab91a880bd3ee0a5c01ff11aac"}, "assets/visuals/kcmc-building-retouched-20261009.jpg": null, "assets/visuals/trunk-or-treat-2026.svg": null, "index.php": {"bytes": 34495, "mode": 420, "sha256": "6051d3ac749818e2cd3487224febe7f5df2e267e8fbd470dd0f24ad21bb14830"}, "lib/bootstrap.php": {"bytes": 21742, "mode": 420, "sha256": "32cff7ba681a9c5163be880af62a358b331b6dbfe91b0fce9621497ef9413b31"}, "manifest.webmanifest": {"bytes": 773, "mode": 420, "sha256": "1b14edb76bcdf80ed633d74c7a8e93140c27eb59f654bfee49d3b154a126a29a"}, "public-presentation.css": {"bytes": 11532, "mode": 420, "sha256": "11f54646d626418dca4672593df42286609527b9ba154cc5cf83401707afebe0"}, "public-presentation.js": {"bytes": 6173, "mode": 420, "sha256": "eb1b70aa00615b2acd75b3173612d56da66d7a03ddff73271ce84c85f432e354"}, "sw.js": {"bytes": 5705, "mode": 420, "sha256": "dee7ee1f397f78bee54b82de08762debbe0b574c1748ae2ab1da84be2393493f"}}, "4225fce8968747ad4f828a9a36087b04fd020484": {"admin/publication-designer.php": {"bytes": 39622, "mode": 420, "sha256": "0a5507d65e570b7ff6983adda3464edd8cd53bb8d4cd9636f91fc37d3e929268"}, "assets/icons/icon-512.png": {"bytes": 49783, "mode": 420, "sha256": "074bebf3a765ae96147b38bcced3ae7e1b05e48498dde1ab8a0dadfa37c1f5e5"}, "assets/visuals/kcmc-building-retouched-20261009.jpg": {"bytes": 260696, "mode": 420, "sha256": "57310f0bdb44d4521951d1840a3591272765ea0d854909d332bce5db87f5d6de"}, "assets/visuals/trunk-or-treat-2026.svg": {"bytes": 5851, "mode": 420, "sha256": "655428d44e4f5c1a43ab62a047c4050cb57d4581c30e5de67e0b0527b7c1ede8"}, "index.php": {"bytes": 33077, "mode": 420, "sha256": "3d692cbd995000c8ebf9013431136e0069530b002f18a162f0a6fad21f9ba4d6"}, "lib/bootstrap.php": {"bytes": 22616, "mode": 420, "sha256": "8c21edc4b25eecade0f792cf20038c73b71270934d0932e4e72432dc8b57d903"}, "manifest.webmanifest": {"bytes": 773, "mode": 420, "sha256": "811afe8914a44b8f5ada3affc27e71714acfa8adfc79e16348189016342d49da"}, "public-presentation.css": {"bytes": 12710, "mode": 420, "sha256": "74234242dc8a47c37ed7b4a433d9b9deccbc416737b546bc977408f3f82e4c54"}, "public-presentation.js": {"bytes": 7250, "mode": 420, "sha256": "bfc4e7a6ab3cb11bae76a74be5d1cdc0912ae00e32f1d66bedf128ec7aabfcc9"}, "sw.js": {"bytes": 5917, "mode": 420, "sha256": "d4f328cc16048ee8f0ce23e7d4d5b70d414d282df74d50a9421acc058b68cdc5"}}}')
# Public targets use latest source; preserved Operations code uses the older approved baseline.
FILES = json.loads('{"admin/publication-designer.php": {"baseline_sha256": "b9e05cd22cbb5b98f04031f548ca7237661827c367d6608669adf8df4e612758", "bytes": 39622, "sha256": "0a5507d65e570b7ff6983adda3464edd8cd53bb8d4cd9636f91fc37d3e929268"}, "assets/icons/icon-512.png": {"baseline_sha256": "e14220ab44f5061853e0fcb8db711e2d08acb8ab91a880bd3ee0a5c01ff11aac", "bytes": 49783, "sha256": "074bebf3a765ae96147b38bcced3ae7e1b05e48498dde1ab8a0dadfa37c1f5e5"}, "assets/visuals/kcmc-building-retouched-20261009.jpg": {"baseline_sha256": null, "bytes": 260696, "sha256": "57310f0bdb44d4521951d1840a3591272765ea0d854909d332bce5db87f5d6de"}, "assets/visuals/trunk-or-treat-2026.svg": {"baseline_sha256": null, "bytes": 5851, "sha256": "655428d44e4f5c1a43ab62a047c4050cb57d4581c30e5de67e0b0527b7c1ede8"}, "index.php": {"baseline_sha256": "6051d3ac749818e2cd3487224febe7f5df2e267e8fbd470dd0f24ad21bb14830", "bytes": 32695, "sha256": "fa828f80c7f3c3b5ec47d815933f7df247f6ba4e542f9e5261182fb006b83723"}, "lib/bootstrap.php": {"baseline_sha256": "32cff7ba681a9c5163be880af62a358b331b6dbfe91b0fce9621497ef9413b31", "bytes": 22616, "sha256": "8c21edc4b25eecade0f792cf20038c73b71270934d0932e4e72432dc8b57d903"}, "manifest.webmanifest": {"baseline_sha256": "1b14edb76bcdf80ed633d74c7a8e93140c27eb59f654bfee49d3b154a126a29a", "bytes": 773, "sha256": "811afe8914a44b8f5ada3affc27e71714acfa8adfc79e16348189016342d49da"}, "public-presentation.css": {"baseline_sha256": "11f54646d626418dca4672593df42286609527b9ba154cc5cf83401707afebe0", "bytes": 16638, "sha256": "05f0b5527d2df49c77a96162362e732397706469c97733fa859c93e89b3f601f"}, "public-presentation.js": {"baseline_sha256": "eb1b70aa00615b2acd75b3173612d56da66d7a03ddff73271ce84c85f432e354", "bytes": 7250, "sha256": "bfc4e7a6ab3cb11bae76a74be5d1cdc0912ae00e32f1d66bedf128ec7aabfcc9"}, "sw.js": {"baseline_sha256": "dee7ee1f397f78bee54b82de08762debbe0b574c1748ae2ab1da84be2393493f", "bytes": 5914, "sha256": "cc8fefeec21f97d279e80472a76edfd0023392c2ad65e74c4bf56b192e657faf"}}')
GUARDS = json.loads('{".htaccess": "993e7a8936737dbf9ba852e60604141de15e24d7399e644393282ed99b7ff690", "admin/audit-export.php": "2c328dc679741ca125d67d26d694b5d2ba9a511fd3b8eee06e4647ff818636e2", "admin/audit.php": "07fd9e1806925faa64e65bc9b916dfc61f8dfd96e8498941ff9628885706d867", "admin/backup.php": "b0beb08b0a475394c0c6d6a50e3e46643ae8602c5892742ddd593cab5c2610ec", "admin/health.php": "8f89221fdabaaad204fc7005136c8fb559f6ca9f7ad9238a764dc86b8d1eb409", "admin/index.php": "9233559775bdcd1a95bce16c4a06d80d085a0e51e52aadc214985bcba750b5a0", "admin/operations.php": "036400973e8f5f3367087602b9a4c94fae06a508b57c479cb7f25334dea9a236", "admin/publication-media.php": "1ce8b5d44756593a6bd678c8a81232248177f5e6c158e90ab52843b2cdd29488", "admin/publication-projects.php": "df4065f13e757f9d9310a8ce01cb1174df94e8dd52f32246c84a010697650312", "admin/push.php": "4b1ac6b56c2d2ae3e80d5880ba1019b8936c701a16c63b0b06b1260a2a173b67", "admin/restore.php": "3d06f27e5b6fc8885c278736fbde63dca0fc7fe4e18697a6709b70ba03136b6d", "admin/timecards-export.php": "0e8889e16261e2f321e18a69272b442b09f12a7f374113bbec13f900143c08dd", "admin/timecards-print.php": "17c4d58cebf787448a8a1ec4a3ed9305f6079d26ae13ac45a8b76c14149a8cc8", "admin/timecards.php": "6950397e9f8d8c88bba1bd5696f62e84419f795d79922877898d89c71d9b6d47", "assets/visuals/kcmc-building-2024.webp": "cd2a12a3211b89ee523bef80a4fee5c3ed7429f6404b2d23530bae61f600e0fb", "assets/visuals/kcmc-ministry-group.jpg": "94fdec9c87cafdb00ca59c2f977145007debbe633b8036c4f5db0cd2670e6e4a", "assets/visuals/kcmc-stage-2014.webp": "904827c79e9332706b8c19c73d4cb211c116629a0f974f4d6df211596df6c994", "assets/visuals/kcmc-worship-2017.webp": "4593491d1f8f2d8592bc6382928eb51a41170b910ed2bd2271c491a7866315a8", "care.php": "0c48c6d5dab7c18329158c68152c441d7194aa334daf074ac663a294e6b3855e", "member/login.php": "2db61ebc38cbb126a6f67d858bdb60e2553ea015d36cfdced869828887ddc4de", "member/timeclock.php": "7864fdee399f90ae5a5bea97fa4c0bf9b5a6a23255f4de31051d21c03bf1663d"}')
BASELINE_EXPECTATIONS = json.loads('{"admin/publication-designer.php": {"bytes": 36010, "mode": 420}, "assets/icons/icon-512.png": {"bytes": 4769, "mode": 420}, "index.php": {"bytes": 34495, "mode": 420}, "lib/bootstrap.php": {"bytes": 21742, "mode": 420}, "manifest.webmanifest": {"bytes": 773, "mode": 420}, "public-presentation.css": {"bytes": 11532, "mode": 420}, "public-presentation.js": {"bytes": 6173, "mode": 420}, "sw.js": {"bytes": 5705, "mode": 420}}')
GIT_SHAS = json.loads('{"admin/publication-designer.php": "9a4dc7b1d84858af9fa284620aa5f0ffc57cc5f9", "assets/icons/icon-512.png": "ed024ce0547e75741202ac7a50514c52db21477e", "assets/visuals/kcmc-building-retouched-20261009.jpg": "3c4d4bb1de598968936fc426e3bef8edc6821030", "assets/visuals/trunk-or-treat-2026.svg": "0da5d8a1b7d0734eb4734374f17e26e2658c943a", "index.php": "d4986630c5a8d1157a5617345a9eb6213f08860b", "lib/bootstrap.php": "1626fc5f43a9fefce17faa5b5a6b8ca1c35665b6", "manifest.webmanifest": "e69d1a4cc464e739a2ae68f615b4c56eccb1d892", "public-presentation.css": "2c30da18867451f6364880eadd5a7ead8d93f4b5", "public-presentation.js": "3cfac1f1406f9434f65ae1f33136be46e3051afe", "sw.js": "b8722b2a3e66db37127c479b7aec8ce2e708ebdf"}')
ABSENT_GUARDS = set(['lib/operations-owner.php'])
OWNER_GUARD_PATHS = set('admin/' + name for name in
                        ['audit-export.php', 'audit.php', 'backup.php', 'health.php', 'operations.php',
                         'push.php', 'restore.php', 'timecards-export.php', 'timecards-print.php', 'timecards.php'])
ALLOWED = set(['admin/publication-designer.php', 'assets/icons/icon-512.png', 'assets/visuals/kcmc-building-retouched-20261009.jpg', 'assets/visuals/trunk-or-treat-2026.svg', 'index.php', 'lib/bootstrap.php', 'manifest.webmanifest', 'public-presentation.css', 'public-presentation.js', 'sw.js'])


class Refusal(RuntimeError):
    pass


class AlreadyCurrent(object):
    """A verified existing runtime; no backup session or replacement occurred."""
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_hash(path, data):
    if path in GIT_SHAS:
        header = b'blob ' + str(len(data)).encode('ascii') + b'\0'
        require(hashlib.sha1(header + data).hexdigest() == GIT_SHAS[path], 'Approved Git blob mismatch: ' + path)


def require(ok, message):
    if not ok:
        raise Refusal(message)


def relative(path):
    require(isinstance(path, str) and path and '\\' not in path and
            all(p not in ('', '.', '..') for p in path.split('/')), 'Unsafe relative path')
    require(not path.startswith('/'), 'Absolute inventory path refused')
    return path


class Parent(object):
    """Hold no-follow directory descriptors through each file operation."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.opened = []

    def __enter__(self):
        require(self.directory.is_absolute(), 'Absolute directory required')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open('/', flags)
        self.opened.append((fd, Path('/')))
        current = Path('/')
        try:
            for name in self.directory.parts[1:]:
                current = current / name
                fd = os.open(name, flags, dir_fd=fd)
                self.opened.append((fd, current))
            self.fd = fd
            self.check()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def check(self):
        for fd, path in self.opened:
            actual, held = os.lstat(str(path)), os.fstat(fd)
            require(stat.S_ISDIR(actual.st_mode) and actual.st_ino == held.st_ino and
                    actual.st_dev == held.st_dev, 'Directory changed or linked: ' + str(path))

    def __exit__(self, *args):
        for fd, _ in reversed(self.opened):
            os.close(fd)
        self.opened = []


def metadata(info, data):
    return {'sha256': digest(data), 'bytes': len(data), 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'dev': info.st_dev, 'ino': info.st_ino,
            'mtime_ns': info.st_mtime_ns, 'atime_ns': info.st_atime_ns}


def read_file(path, missing=False):
    path = Path(path)
    with Parent(path.parent) as parent:
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent.fd)
        except FileNotFoundError:
            require(missing, 'Required file missing: ' + str(path))
            return None, None
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                    'Non-regular or hardlinked file refused: ' + str(path))
            require(before.st_size <= MAX_BYTES, 'Oversized file refused: ' + str(path))
            pieces = []
            while True:
                part = os.read(fd, min(65536, MAX_BYTES + 1 - sum(map(len, pieces))))
                if not part:
                    break
                pieces.append(part)
                require(sum(map(len, pieces)) <= MAX_BYTES, 'Oversized file refused')
            data = b''.join(pieces)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    'File changed while reading: ' + str(path))
            parent.check()
            visible = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)
            require(visible.st_ino == before.st_ino and visible.st_dev == before.st_dev and
                    visible.st_nlink == 1, 'File replaced while reading: ' + str(path))
            return data, metadata(before, data)
        finally:
            os.close(fd)


def private_dir(path):
    path = Path(path)
    with Parent(path.parent) as parent:
        try:
            os.mkdir(path.name, 0o700, dir_fd=parent.fd)
        except FileExistsError:
            pass
        info = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, 'Private directory permissions/owner refused: ' + str(path))
        parent.check()


def nested_private(path, root):
    root, path = Path(root), Path(path)
    require(str(path).startswith(str(root) + os.sep), 'Private path escaped session')
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        private_dir(current)


def write_private(path, data):
    path = Path(path)
    with Parent(path.parent) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent.fd)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.fchmod(fd, 0o600)
            parent.check()
        finally:
            os.close(fd)


def private_path(path):
    path = Path(path)
    require(str(path).startswith(str(BACKUP_ROOT) + os.sep), 'Backup path escaped protected root')
    current = BACKUP_ROOT
    for name in [None] + list(path.parent.relative_to(BACKUP_ROOT).parts):
        if name is not None:
            current = current / name
        info = os.lstat(str(current))
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, 'Unsafe protected directory: ' + str(current))


def read_private(path):
    private_path(path)
    data, info = read_file(path)
    require(info['mode'] == 0o600 and info['uid'] == os.getuid(), 'Unsafe protected file permissions')
    return data, info


def atomic_replace(src, dst, **kwargs):
    os.replace(src, dst, **kwargs)


def journal(session, value):
    path = Path(session) / 'manifest.json'
    if path.exists() or path.is_symlink():
        _, old = read_file(path)
        require(old['mode'] == 0o600 and old['uid'] == os.getuid(), 'Unsafe journal permissions')
    temp = Path(session) / ('manifest-' + uuid.uuid4().hex + '.tmp')
    write_private(temp, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8'))
    with Parent(session) as parent:
        atomic_replace(temp.name, path.name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)
        os.fsync(parent.fd)


@contextlib.contextmanager
def locked():
    require('/public_html/' not in str(BACKUP_ROOT) + '/', 'Backup must be outside public_html')
    private_dir(BACKUP_ROOT)
    with Parent(BACKUP_ROOT) as parent:
        fd = os.open('.install.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent.fd)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                    info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                    'Unsafe installation lock')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refusal('Another scoped installation is running')
            parent.check()
            yield
        finally:
            os.close(fd)


def inventory():
    require(re.match(r'\A[0-9a-f]{40}\Z', COMMIT) is not None, 'October 13 release requires an approved immutable runtime SHA')
    require(set(BASELINES) == set(BASELINE_IDS), 'Unknown baseline bundle')
    for bundle in BASELINES.values():
        require(isinstance(bundle, dict) and set(bundle) == set(FILES), 'Incomplete baseline bundle')
        for item in bundle.values():
            require(item is None or (isinstance(item, dict) and set(item) == set(['sha256', 'bytes', 'mode']) and
                    isinstance(item['sha256'], str) and re.match(r'\A[0-9a-f]{64}\Z', item['sha256']) is not None and
                    isinstance(item['bytes'], int) and 0 < item['bytes'] <= MAX_BYTES and
                    isinstance(item['mode'], int) and 0 <= item['mode'] <= 0o7777), 'Invalid baseline preimage')
    require(FILES and set(FILES) == ALLOWED, 'Incomplete or out-of-scope inventory')
    require(set(GIT_SHAS) == set(FILES), 'Incomplete approved Git blob inventory')
    require('sw.js' in FILES, 'Service worker must be part of this release')
    for path, item in FILES.items():
        relative(path)
        require(set(item) == set(['sha256', 'bytes', 'baseline_sha256']), 'Unexpected inventory fields')
        require(re.match(r'\A[0-9a-f]{64}\Z', item['sha256']) is not None and
                isinstance(item['bytes'], int) and 0 < item['bytes'] <= MAX_BYTES, 'Invalid approved source metadata')
        require(item['baseline_sha256'] is None or
                re.match(r'\A[0-9a-f]{64}\Z', item['baseline_sha256']) is not None, 'Invalid baseline hash')
    for path, expected in GUARDS.items():
        relative(path)
        require(path not in FILES and re.match(r'\A[0-9a-f]{64}\Z', expected) is not None, 'Invalid protected guard')
    for path in ABSENT_GUARDS:
        relative(path)
        require(path not in FILES and path not in GUARDS, 'Invalid protected absence guard')
    require(OWNER_GUARD_PATHS.issubset(set(GUARDS)), 'Incomplete deferred owner guard scope')


def fetch_bytes(path):
    url = SOURCE_ROOT + urllib.parse.quote(relative(path), safe='/')
    request = urllib.request.Request(url, headers={'User-Agent': 'KCMC-pinned-code-transaction'})
    with urllib.request.urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
        require(response.geturl() == url and response.status == 200, 'Pinned source redirect/status refused')
        data = response.read(FILES[path]['bytes'] + 1)
    require(len(data) == FILES[path]['bytes'] and digest(data) == FILES[path]['sha256'], 'Approved download hash mismatch: ' + path)
    source_hash(path, data)
    return data


def validate_svg(data):
    require(isinstance(data, bytes) and data and len(data) <= MAX_BYTES, 'Invalid SVG bytes')
    require(b'\0' not in data, 'SVG non-UTF8 encoding refused')
    try:
        data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise Refusal('SVG non-UTF8 encoding refused')
    require(re.search(br'<!\s*(?:DOCTYPE|ENTITY)', data, re.I) is None, 'SVG declarations/entities refused')
    require(re.search(br'<\?(?!xml\s)', data, re.I) is None, 'SVG processing instruction refused')
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError):
        raise Refusal('SVG XML parse failed')
    require(root.tag == '{http://www.w3.org/2000/svg}svg', 'SVG namespace/root refused')
    for element in root.iter():
        local = element.tag.rsplit('}', 1)[-1].lower()
        require(element.tag.startswith('{http://www.w3.org/2000/svg}') and
                local not in ('script', 'foreignobject', 'style', 'animate', 'animatemotion', 'animatetransform', 'set'),
                'SVG active/foreign content refused')
        for key, value in element.attrib.items():
            name = key.rsplit('}', 1)[-1].lower()
            require(not name.startswith('on') and name not in ('base', 'style'), 'SVG active/base/style attribute refused')
            if name in ('href', 'src'):
                require(value.startswith('#') and len(value) > 1, 'SVG external reference refused')
        values = list(element.attrib.values()) + [element.text or '', element.tail or '']
        for value in values:
            require('\\' not in value, 'SVG escaped presentation value refused')
            require('@import' not in value.lower() and '@font-face' not in value.lower(), 'SVG external style refused')
            for reference in re.findall(r'url\s*\(([^)]*)\)', value, re.I):
                reference = reference.strip().strip('"\'')
                require(reference.startswith('#') and len(reference) > 1, 'SVG external style reference refused')
    return root


def validate_staged_media(php, path, staged):
    if path.endswith('.svg'):
        data, _ = read_private(staged)
        validate_svg(data)
        mime = subprocess.check_output([php, '-r',
                '$f=finfo_open(FILEINFO_MIME_TYPE); echo finfo_file($f,$argv[1]);', '--', staged]).decode('ascii').strip()
        require(mime == 'image/svg+xml', 'Staged SVG MIME refused')
    elif path.endswith(('.png', '.jpg', '.jpeg')):
        code = ('$i=@getimagesize($argv[1]); if(!$i) exit(1); '
                '$f=finfo_open(FILEINFO_MIME_TYPE); echo json_encode(['
                '"width"=>$i[0],"height"=>$i[1],"type"=>$i[2],"mime"=>finfo_file($f,$argv[1])]);')
        info = json.loads(subprocess.check_output([php, '-r', code, '--', staged]).decode('utf-8'))
        expected = ('image/png', 3) if path.endswith('.png') else ('image/jpeg', 2)
        require(isinstance(info, dict) and info.get('mime') == expected[0] and info.get('type') == expected[1] and
                isinstance(info.get('width'), int) and isinstance(info.get('height'), int) and
                info['width'] > 0 and info['height'] > 0, 'Staged raster MIME/dimensions refused')
        if path == 'assets/icons/icon-512.png':
            require(info['width'] == 512 and info['height'] == 512, 'Staged icon must be 512 by 512')


def lint_staged(records):
    candidates = ['/opt/cpanel/ea-php82/root/usr/bin/php', 'php8.2', 'php82', 'php']
    php = None
    for candidate in candidates:
        executable = candidate if os.path.isfile(candidate) else shutil.which(candidate)
        if not executable:
            continue
        try:
            version = int(subprocess.check_output([executable, '-r', 'echo PHP_VERSION_ID;'], stderr=subprocess.STDOUT).strip())
        except (OSError, ValueError, subprocess.CalledProcessError):
            continue
        if 80200 <= version < 80300:
            php = executable
            break
    require(php is not None, 'PHP 8.2 CLI required; no application files were changed')
    subprocess.check_call([php, '-r', 'exit(function_exists("finfo_open") && function_exists("getimagesize") ? 0 : 1);'], stdout=subprocess.DEVNULL)
    node = shutil.which('node')
    for item in records:
        staged = item['staged']
        if item['path'].endswith('.php'):
            subprocess.check_call([php, '-l', staged], stdout=subprocess.DEVNULL)
        elif node and item['path'].endswith('.js'):
            subprocess.check_call([node, '--check', staged], stdout=subprocess.DEVNULL)
        elif item['path'].endswith(('.svg', '.png', '.jpg', '.jpeg')):
            validate_staged_media(php, item['path'], staged)
    print('Staged PHP 8.2 syntax verified; JavaScript syntax ' + ('verified' if node else 'unavailable on host (approved CI source remains hash-pinned)'))


def verify_http():
    checks = [('', ['data-hero-photo', 'kcmc-building-retouched-20261009.jpg',
                    'public-presentation.css?v=home-audit-20261013',
                    'public-presentation.js?v=blue-fish-menu-20261009', 'manifest.webmanifest?v=3.0.1']),
              ('member/login.php', ['Staff Sign In']),
              ('admin/publication-designer.php', ['Staff Sign In']),
              ('admin/publication-projects.php', ['Staff Sign In']),
              ('admin/publication-media.php', ['Staff Sign In'])]
    for route, markers in checks:
        url = PUBLIC_ROOT + route
        request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'KCMC-read-only-release-check'})
        with urllib.request.urlopen(request, timeout=45, context=ssl.create_default_context()) as response:
            parsed, base = urllib.parse.urlparse(response.geturl()), urllib.parse.urlparse(PUBLIC_ROOT)
            require(response.status == 200 and parsed.scheme == 'https' and parsed.netloc == base.netloc and
                    parsed.path.startswith(base.path), 'Public verification redirect/status refused')
            if route.startswith('admin/'):
                require(parsed.path == base.path + 'member/login.php', 'Anonymous admin route must reach staff sign-in')
            body = response.read(MAX_BYTES + 1)
            require(len(body) <= MAX_BYTES, 'Public verification response too large')
        text = body.decode('utf-8')
        require(all(marker in text for marker in markers), 'Public marker check failed: ' + (route or 'home'))
    static = [(path, '') for path in FILES if not path.endswith('.php')]
    static += [('manifest.webmanifest', '?v=3.0.1'), ('assets/icons/icon-512.png', '?v=3.0.3')]
    for path, query in static:
        approved = FILES[path]
        url = PUBLIC_ROOT + urllib.parse.quote(path, safe='/') + query
        request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'KCMC-read-only-release-check'})
        with urllib.request.urlopen(request, timeout=45, context=ssl.create_default_context()) as response:
            require(response.status == 200 and response.geturl() == url, 'Static verification redirect/status refused: ' + path)
            body = response.read(approved['bytes'] + 1)
        require(len(body) == approved['bytes'] and digest(body) == approved['sha256'], 'Public static hash mismatch: ' + path)
        if path == 'sw.js':
            require(b'kcmc-connect-v3.0.3-public-only-home-audit-20261013' in body, 'Service worker release marker refused')
        elif path == 'manifest.webmanifest':
            manifest = json.loads(body.decode('utf-8'))
            require(isinstance(manifest, dict) and isinstance(manifest.get('icons'), list) and
                    any(icon.get('src') == 'assets/icons/icon-512.png?v=3.0.3' and icon.get('sizes') == '512x512' and
                        icon.get('type') == 'image/png' for icon in manifest['icons'] if isinstance(icon, dict)),
                    'Manifest repaired icon marker refused')


def check_expected(path, expected, exact=False):
    _, actual = read_file(APP_ROOT / path, missing=True)
    if expected is None:
        require(actual is None, 'Expected missing target appeared: ' + path)
        return None
    require(actual is not None and actual['sha256'] == expected['sha256'] and
            actual['bytes'] == expected['bytes'], 'Live hash drift: ' + path)
    keys = ['mode', 'uid', 'gid'] + (['dev', 'ino', 'mtime_ns'] if exact else [])
    require(all(actual[k] == expected[k] for k in keys), 'Live metadata drift: ' + path)
    return actual


def protected_capture():
    records = {}
    for path, expected in GUARDS.items():
        _, info = read_file(APP_ROOT / path)
        require(info['sha256'] == expected, 'Protected baseline drift: ' + path)
        records[path] = info
    for path in ABSENT_GUARDS:
        _, info = read_file(APP_ROOT / path, missing=True)
        require(info is None, 'Excluded owner helper is already present; deployment requires review: ' + path)
        records[path] = None
    _, content = read_file(APP_ROOT / CONTENT_PATH)
    records[CONTENT_PATH] = content
    return records


def private_store_root():
    configured = os.environ.get('KCMC_PRIVATE_DATA_DIR', '').strip()
    root = Path(configured.rstrip('/') if configured else APP_ROOT / 'data/private')
    require(root.is_absolute() and root != Path('/') and all(part not in ('.', '..') for part in root.parts),
            'Publisher storage path is unresolved')
    try:
        with Parent(root) as directory:
            directory.check()
    except OSError:
        raise Refusal('Publisher storage directory is missing or linked; resolve host storage before deployment')
    return root


@contextlib.contextmanager
def publisher_locked():
    # These are the same lock names used by the approved PHP JSON updater.
    # Only lock metadata can be created; no JSON store is created or changed.
    root = private_store_root()
    descriptors = []
    with Parent(root) as directory:
        try:
            for name in PUBLISHER_STORES:
                fd = os.open(name + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                             0o640, dir_fd=directory.fd)
                descriptors.append(fd)
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                        not (stat.S_IMODE(info.st_mode) & 0o022), 'Unsafe Publisher lock file')
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Refusal('Publisher storage is busy; keep Publisher idle during deployment')
            directory.check()
            yield
            directory.check()
        finally:
            for fd in reversed(descriptors):
                os.close(fd)


def capture_stores():
    root = private_store_root()
    with Parent(root) as directory:
        info = os.fstat(directory.fd)
        files = {}
        for name in PUBLISHER_STORES:
            _, files[name] = read_file(root / name, missing=True)
        directory.check()
    return {'root': str(root), 'dev': info.st_dev, 'ino': info.st_ino, 'files': files}


def check_stores(expected):
    actual = capture_stores()
    require(all(actual[key] == expected[key] for key in ('root', 'dev', 'ino')),
            'Publisher storage location changed; code downgrade refused')
    for name in PUBLISHER_STORES:
        old, current = expected['files'][name], actual['files'][name]
        require((old is None and current is None) or (old is not None and current is not None and
                all(current[key] == old[key] for key in ('sha256', 'bytes', 'mode', 'uid', 'gid', 'dev', 'ino', 'mtime_ns'))),
                'Publisher store changed; code downgrade refused to preserve newer publications')


def check_protected(records):
    for path, expected in records.items():
        check_expected(path, expected, exact=True)


def check_owner_protected(records):
    for path in OWNER_GUARD_PATHS | ABSENT_GUARDS:
        check_expected(path, records[path], exact=True)


def read_session(session):
    session = Path(session)
    require(session.parent == BACKUP_ROOT and session.name.startswith('release-'), 'Unknown backup session')
    require(session.is_dir(), 'Backup session does not exist')
    data, info = read_private(session / 'manifest.json')
    require(info['mode'] == 0o600 and info['uid'] == os.getuid(), 'Unsafe session manifest')
    value = json.loads(data.decode('utf-8'))
    require(isinstance(value, dict) and set(value) == set(['version', 'app', 'commit', 'phase', 'baseline_id', 'files', 'protected', 'publisher', 'intent']) and
            value['version'] == 1 and value['phase'] in ('prepared', 'applying', 'applied', 'failed', 'rolling_back', 'rolled_back'),
            'Unknown session journal format')
    require(isinstance(value['files'], dict) and isinstance(value['protected'], dict) and
            value['commit'] == COMMIT and value['app'] == str(APP_ROOT) and
            set(value['files']) == set(FILES), 'Session scope/source mismatch')
    require(value['intent'] is None or value['intent'] in FILES, 'Unknown session installation intent')
    require(value['baseline_id'] in BASELINE_IDS, 'Unknown session baseline')
    bundle = BASELINES[value['baseline_id']]
    metadata_keys = set(['sha256', 'bytes', 'mode', 'uid', 'gid', 'dev', 'ino', 'mtime_ns', 'atime_ns'])
    def valid_metadata(record):
        require(isinstance(record, dict) and set(record) == metadata_keys and
                isinstance(record['sha256'], str) and re.match(r'\A[0-9a-f]{64}\Z', record['sha256']) is not None and
                all(isinstance(record[key], int) and record[key] >= 0 for key in metadata_keys - set(['sha256'])) and
                record['bytes'] <= MAX_BYTES and record['mode'] <= 0o7777, 'Invalid session file metadata')
    for path, record in value['files'].items():
        require(isinstance(record, dict) and set(record) == set(['approved', 'original', 'installed', 'candidate']) and
                record['approved'] == FILES[path], 'Session approved hash changed')
        baseline = record['original']
        if baseline is not None:
            valid_metadata(baseline)
        expected = bundle[path]
        require((baseline is None if expected is None else baseline is not None and
                all(baseline[key] == expected[key] for key in ('sha256', 'bytes', 'mode'))),
                'Session selected baseline preimage changed')
        for kind in ('candidate', 'installed'):
            if record[kind] is not None:
                valid_metadata(record[kind])
                require(record[kind]['sha256'] == FILES[path]['sha256'] and record[kind]['bytes'] == FILES[path]['bytes'],
                        'Session installation source changed')
    require(set(value['protected']) == set(GUARDS) | ABSENT_GUARDS | set([CONTENT_PATH]), 'Session protected scope changed')
    for path, record in value['protected'].items():
        if path in ABSENT_GUARDS:
            require(record is None, 'Session protected absence changed')
        else:
            valid_metadata(record)
    for path, expected in GUARDS.items():
        require(value['protected'][path]['sha256'] == expected, 'Session protected hash changed')
    publisher = value['publisher']
    require(isinstance(publisher, dict) and set(publisher) == set(['root', 'dev', 'ino', 'files']) and
            isinstance(publisher['root'], str) and Path(publisher['root']).is_absolute() and
            isinstance(publisher['dev'], int) and isinstance(publisher['ino'], int) and
            isinstance(publisher['files'], dict) and set(publisher['files']) == set(PUBLISHER_STORES),
            'Session Publisher scope changed')
    for record in publisher['files'].values():
        if record is not None:
            valid_metadata(record)
    return value


def select_baseline(originals):
    matches = []
    for baseline_id in BASELINE_IDS:
        expected = BASELINES[baseline_id]
        if all((originals[path][1] is None if expected[path] is None else
                originals[path][1] is not None and all(originals[path][1][key] == expected[path][key]
                for key in ('sha256', 'bytes', 'mode'))) for path in FILES):
            matches.append(baseline_id)
    require(len(matches) == 1, 'Live files are not one complete approved baseline; mixed or newer files require review')
    return matches[0]


def prepare_unlocked():
    inventory()
    originals = {}
    protected = protected_capture()
    publisher = capture_stores()
    for path, approved in FILES.items():
        data, info = read_file(APP_ROOT / path, missing=True)
        originals[path] = (data, info)
    baseline_id = select_baseline(originals)
    name = 'release-' + datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
    session = BACKUP_ROOT / name
    private_dir(session)
    private_dir(session / 'stage')
    private_dir(session / 'originals')
    records, lint = {}, []
    for path, approved in FILES.items():
        staged = session / 'stage' / path
        nested_private(staged.parent, session)
        data = fetch_bytes(path)
        require(len(data) == approved['bytes'] and digest(data) == approved['sha256'], 'Stage source mismatch: ' + path)
        source_hash(path, data)
        write_private(staged, data)
        old, info = originals[path]
        if info is not None:
            backup = session / 'originals' / path
            nested_private(backup.parent, session)
            write_private(backup, old)
        records[path] = {'approved': approved, 'original': info, 'installed': None, 'candidate': None}
        lint.append({'path': path, 'staged': str(staged)})
    content, info = read_file(APP_ROOT / CONTENT_PATH)
    require(info['sha256'] == protected[CONTENT_PATH]['sha256'], 'Editorial content changed during backup')
    backup = session / 'originals' / CONTENT_PATH
    nested_private(backup.parent, session)
    write_private(backup, content)
    lint_staged(lint)
    for path, record in records.items():
        check_expected(path, record['original'], exact=True)
        data, info = read_private(session / 'stage' / path)
        require(info['mode'] == 0o600 and digest(data) == record['approved']['sha256'], 'Staged source changed: ' + path)
        with Parent((APP_ROOT / path).parent) as target_parent:
            require(info['dev'] == os.fstat(target_parent.fd).st_dev,
                    'Stage and target are on different filesystems: ' + path)
    check_protected(protected)
    check_stores(publisher)
    value = {'version': 1, 'app': str(APP_ROOT), 'commit': COMMIT, 'phase': 'prepared',
             'baseline_id': baseline_id, 'files': records, 'protected': protected, 'publisher': publisher, 'intent': None}
    journal(session, value)
    return session


def prepare():
    with locked(), publisher_locked():
        return prepare_unlocked()


def order(paths, restoring=False):
    def priority(path):
        if path == 'sw.js':
            return (99, path)
        if path.startswith('assets/'):
            rank = 0
        elif path == 'lib/bootstrap.php':
            rank = 1
        elif path in ('public-presentation.css', 'public-presentation.js'):
            rank = 2
        elif path in ('manifest.webmanifest', 'admin/publication-media.php', 'admin/publication-projects.php'):
            rank = 3
        elif path == 'admin/publication-designer.php':
            rank = 4
        else:
            rank = 5
        return (-rank if restoring else rank, path)
    return sorted(paths, key=priority)


def installation_candidate(session, path, record):
    data, candidate = read_private(Path(session) / 'stage' / path)
    require(candidate['sha256'] == record['approved']['sha256'] and
            candidate['bytes'] == record['approved']['bytes'], 'Stage verification failed: ' + path)
    with Parent((APP_ROOT / path).parent) as dest:
        require(candidate['dev'] == os.fstat(dest.fd).st_dev, 'Stage/target filesystem changed: ' + path)
        original = record['original']
        candidate.update({'mode': original['mode'] if original else 0o644,
                          'uid': original['uid'] if original else os.getuid(),
                          'gid': original['gid'] if original else os.fstat(dest.fd).st_gid})
    return candidate


def install_one(session, path, record):
    approved, original = record['approved'], record['original']
    target, staged = APP_ROOT / path, Path(session) / 'stage' / path
    data, info = read_private(staged)
    require(digest(data) == approved['sha256'] and len(data) == approved['bytes'], 'Staged source drift: ' + path)
    with Parent(target.parent) as dest, Parent(staged.parent) as source:
        check_expected(path, original, exact=True)
        candidate = record['candidate']
        mode, uid, gid = candidate['mode'], candidate['uid'], candidate['gid']
        require(info['dev'] == os.fstat(dest.fd).st_dev, 'Stage/target filesystem changed: ' + path)
        fd = os.open(staged.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source.fd)
        try:
            held = os.fstat(fd)
            require(stat.S_ISREG(held.st_mode) and held.st_nlink == 1 and
                    held.st_ino == candidate['ino'] and held.st_dev == candidate['dev'] and
                    held.st_mtime_ns == candidate['mtime_ns'], 'Stage replaced or hardlinked')
            os.fchown(fd, uid, gid)
            os.fchmod(fd, mode)
            os.fsync(fd)
            verified, actual = read_file(staged)
            require(actual['sha256'] == approved['sha256'] and actual['bytes'] == approved['bytes'] and
                    all(actual[k] == candidate[k] for k in ['dev', 'ino', 'mtime_ns', 'mode', 'uid', 'gid']),
                    'Stage changed before replacement: ' + path)
        finally:
            os.close(fd)
        dest.check(); source.check()
        check_expected(path, original, exact=True)
        check_protected(read_session(session)['protected'])
        atomic_replace(staged.name, target.name, src_dir_fd=source.fd, dst_dir_fd=dest.fd)
        os.fsync(dest.fd)
        dest.check()
    _, installed = read_file(target)
    require(installed['sha256'] == approved['sha256'] and installed['bytes'] == approved['bytes'] and
            (installed['mode'], installed['uid'], installed['gid']) == (mode, uid, gid), 'Postwrite verification failed: ' + path)
    return installed


def check_transaction(value):
    for path, record in value['files'].items():
        check_expected(path, record['installed'] if record['installed'] else record['original'], exact=True)
    check_protected(value['protected'])
    check_stores(value['publisher'])


def rollback_unlocked(session, automatic=False):
    value = read_session(session)
    require(value['phase'] in ('applying', 'applied', 'failed', 'rolling_back', 'rolled_back'), 'Session has no applied code to roll back')
    if not automatic:
        check_owner_protected(value['protected'])
    check_stores(value['publisher'])
    # Aggregate source/live validation precedes every rollback mutation.
    current = {}
    for path, record in value['files'].items():
        old = record['original']
        if old:
            data, _ = read_private(Path(session) / 'originals' / path)
            require(digest(data) == old['sha256'] and len(data) == old['bytes'], 'Backup hash mismatch: ' + path)
        _, actual = read_file(APP_ROOT / path, missing=True)
        baseline = actual is None if old is None else actual is not None and actual['sha256'] == old['sha256'] and all(actual[k] == old[k] for k in ['mode', 'uid', 'gid'])
        lease = record['installed'] or record.get('candidate')
        approved = actual is not None and lease is not None and all(actual[k] == lease[k] for k in
                   ['sha256', 'bytes', 'mode', 'uid', 'gid', 'dev', 'ino', 'mtime_ns'])
        require(baseline or approved, 'Newer live edit prevents rollback: ' + path)
        if value['phase'] == 'applied' and not automatic:
            require(approved, 'Applied file changed before rollback: ' + path)
        current[path] = (actual, approved and not baseline)
    value['phase'] = 'rolling_back'
    try:
        journal(session, value)
    except BaseException:
        # Automatic recovery can use the durable applying/intent journal when
        # a disk failure prevents another journal write. Manual restore must
        # first record its resumable state.
        if not automatic:
            raise
    restore = Path(session) / 'rollback-stage'
    private_dir(restore)
    for path in order(value['files'], restoring=True):
        expected, changed = current[path]
        if not changed:
            continue
        record, target = value['files'][path], APP_ROOT / path
        with Parent(target.parent) as dest:
            check_stores(value['publisher'])
            check_expected(path, expected, exact=True)
            if not automatic:
                check_owner_protected(value['protected'])
            old = record['original']
            if old is None:
                os.unlink(target.name, dir_fd=dest.fd)
            else:
                data, _ = read_private(Path(session) / 'originals' / path)
                require(digest(data) == old['sha256'] and len(data) == old['bytes'], 'Backup changed before restore: ' + path)
                staged = restore / (uuid.uuid4().hex + '.restore')
                write_private(staged, data)
                fd = os.open(str(staged), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    os.fchown(fd, old['uid'], old['gid']); os.fchmod(fd, old['mode'])
                    os.utime(fd, ns=(old['atime_ns'], old['mtime_ns']))
                    os.fsync(fd)
                finally:
                    os.close(fd)
                with Parent(restore) as source:
                    dest.check(); source.check()
                    check_stores(value['publisher'])
                    check_expected(path, expected, exact=True)
                    if not automatic:
                        check_owner_protected(value['protected'])
                    atomic_replace(staged.name, target.name, src_dir_fd=source.fd, dst_dir_fd=dest.fd)
            os.fsync(dest.fd)
            dest.check()
        check_expected(path, old)
    for path, record in value['files'].items():
        check_expected(path, record['original'])
    value['phase'] = 'rolled_back'; value['intent'] = None
    check_stores(value['publisher'])
    try:
        journal(session, value)
    except BaseException:
        if not automatic:
            raise


def rollback(session, automatic=False):
    inventory()
    with locked(), publisher_locked():
        rollback_unlocked(Path(session), automatic=automatic)


def verify_current_unlocked():
    current = {}
    for path, approved in FILES.items():
        _, info = read_file(APP_ROOT / path, missing=True)
        current[path] = info
    if not all(info is not None and info['sha256'] == FILES[path]['sha256'] and
               info['bytes'] == FILES[path]['bytes'] for path, info in current.items()):
        return False
    for path, info in current.items():
        with Parent((APP_ROOT / path).parent) as parent:
            require(info['mode'] == 0o644 and info['uid'] == os.getuid() and
                    info['gid'] == os.fstat(parent.fd).st_gid,
                    'Current runtime ownership/mode refused: ' + path)
    protected, publisher = protected_capture(), capture_stores()
    verify_http()
    for path, info in current.items():
        check_expected(path, info, exact=True)
    check_protected(protected)
    check_stores(publisher)
    return True


def apply(session=None):
    inventory()
    with locked(), publisher_locked():
        if session is None and verify_current_unlocked():
            return AlreadyCurrent()
        session = prepare_unlocked() if session is None else Path(session)
        value = read_session(session)
        require(value['phase'] == 'prepared', 'Only a prepared session can apply')
        check_transaction(value)
        for path, record in value['files'].items():
            data, info = read_private(session / 'stage' / path)
            require(info['mode'] == 0o600 and digest(data) == record['approved']['sha256'] and
                    len(data) == record['approved']['bytes'], 'Stage verification failed: ' + path)
        value['phase'] = 'applying'
        journal(session, value)
        previous = signal.getsignal(signal.SIGTERM)
        def interrupted(signum, frame):
            raise RuntimeError('Installation interrupted by signal')
        signal.signal(signal.SIGTERM, interrupted)
        try:
            for path in order(value['files']):
                check_transaction(value)
                value['files'][path]['candidate'] = installation_candidate(session, path, value['files'][path])
                value['intent'] = path
                journal(session, value)
                value['files'][path]['installed'] = install_one(session, path, value['files'][path])
                value['intent'] = None
                journal(session, value)
            check_transaction(value)
            verify_http()
            check_transaction(value)
            value['phase'] = 'applied'
            journal(session, value)
        except BaseException as error:
            value['phase'] = 'failed'
            try:
                journal(session, value)
            except BaseException:
                pass
            try:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                rollback_unlocked(session, automatic=True)
            except BaseException as rollback_error:
                raise Refusal('Installation failed; automatic rollback refused: ' + str(rollback_error) + '. Private session: ' + str(session))
            raise Refusal('Installation failed and affected code was rolled back: ' + str(error) + '. Private session: ' + str(session))
        finally:
            signal.signal(signal.SIGTERM, previous)
        return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'apply', 'rollback'])
    parser.add_argument('--session', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'preflight':
            require(args.session is None, 'Preflight creates a new protected session')
            session = prepare()
            print('Preflight passed. No application code, editorial content, or private JSON records changed; coordination lock files may be created. Private session: ' + str(session))
        elif args.action == 'apply':
            session = apply(args.session)
            if isinstance(session, AlreadyCurrent):
                print('Pinned public runtime already present; read-only checks verified; no application file replaced.')
                print('No backup session or editorial/private JSON copy was created; coordination lock files may be created.')
            else:
                print('Pinned public code applied and read-only public markers verified. Private session: ' + str(session))
            print('Operations owner files were preserved; owner configuration requires separate verification.')
            print('Editorial/private records were not replaced; staff and physical-device acceptance remain separate.')
        else:
            require(args.session is not None, 'Rollback requires its exact protected session')
            rollback(args.session)
            print('Affected code restored. Editorial/private records were not replaced.')
    except (Refusal, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
