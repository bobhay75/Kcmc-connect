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

APP_ROOT = Path('/home/bobsome1/public_html/kcmc-connect')
BACKUP_ROOT = Path('/home/bobsome1/kcmc-release-backups')
COMMIT = '61c70f590735522adbfd6be02dab6888924a54fd'
SOURCE_ROOT = 'https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' + COMMIT + '/KCMC-Connect-Phase6-Recreated/'
PUBLIC_ROOT = 'https://bobsome1.com/kcmc-connect/'
MAX_BYTES = 16 * 1024 * 1024
CONTENT_PATH = 'data/content.json'
PUBLISHER_STORES = ('publications.json', 'publication-media.json')
# Filled only from the reviewed immutable inventory and owner host receipt.
FILES = json.loads('{"admin/publication-designer.php": {"baseline_sha256": "d03b73fe34e3773c8aa0bc469778ad6b84089d584bd89c7e5f17239a915c702f", "bytes": 32506, "sha256": "fe401dba16db2bf2611dc2f8199965d6faad423efcfd085f0e65a14794329793"}, "admin/publication-media.php": {"baseline_sha256": null, "bytes": 7994, "sha256": "1ce8b5d44756593a6bd678c8a81232248177f5e6c158e90ab52843b2cdd29488"}, "admin/publication-projects.php": {"baseline_sha256": "c953df4f774ccd3df5c8969d2fcc88fe77e66ed9e690a37f062a4608e77aa8a8", "bytes": 9117, "sha256": "aaf667a192407869f5d0255dcb648f3253c41671423578cf39d1866a2aeab205"}, "assets/visuals/kcmc-bridge-logo-composite.png": {"baseline_sha256": null, "bytes": 3755093, "sha256": "0c56385f540160ae7c704c3496f8c7fd329b3a995faf75aa1f9832496a31c45d"}, "assets/visuals/kcmc-bridge-logo.jpg": {"baseline_sha256": null, "bytes": 67354, "sha256": "9926f5ee356f67aa076fd6912b9a4cea8e458f4e4202a6af2c49360c06ecc082"}, "assets/visuals/kcmc-bridge-wordmark.png": {"baseline_sha256": null, "bytes": 1715447, "sha256": "c67a448f587586e62eb3daf4f27912ea137c08011fa2e070aff89bd290d85a00"}, "assets/visuals/kcmc-church-wordmark.jpg": {"baseline_sha256": null, "bytes": 93545, "sha256": "957b2d8994596713673de3badc1a6abfb8044975e06c97af6ddb0f45c2e1effb"}, "assets/visuals/kcmc-congregation-gathering.jpg": {"baseline_sha256": null, "bytes": 277265, "sha256": "9bcf70bd63180f36330fc01a709b8c8dc73036cda9af935f9676fe2851a8a9e4"}, "assets/visuals/kcmc-family-outdoor-event.jpg": {"baseline_sha256": null, "bytes": 569816, "sha256": "6ca77e8f7f2b6d9bc7fc3b7e4338dca0d58809873209cb7c6a30494b9f163f5c"}, "assets/visuals/kcmc-kids-game-room.jpg": {"baseline_sha256": null, "bytes": 313874, "sha256": "094d137b2591821e7796dab7f5deaddd9733f7ab31ccd36551f9132205f50598"}, "assets/visuals/kcmc-kids-safari.jpg": {"baseline_sha256": null, "bytes": 359032, "sha256": "652fbe2f8eaaf1ce2eddfb187797cabb67d887b71fa17d14b4e2a06e22fc50bf"}, "assets/visuals/kcmc-kids-summer-group.jpg": {"baseline_sha256": null, "bytes": 175475, "sha256": "d45a5a91efa83c22ea41aa878ce4d7c0f7e4c254b238a9a2ebd1b9ac90e7824e"}, "index.php": {"baseline_sha256": "59eac1492cb976eb02fb11030ce46da71c943b514dc8b4ad660a718f791334a5", "bytes": 32929, "sha256": "0cd9bee7066cbcd3d18941b749ca5990f65e9ce3124f8330703add0143808a8f"}, "public-presentation.css": {"baseline_sha256": "d527b171de110a407529077630ef94b22a8afd355bdab9aabd3ad27e2812e927", "bytes": 9111, "sha256": "6e2183564ce17513ac1f85020e98f4c855ff89f0d8caac776b117bde8234bde2"}, "public-presentation.js": {"baseline_sha256": "9a25e8b69e5773ee8ca0cdd6b813f7a931ea4c489fd885088cf45dfb9697cc8d", "bytes": 5910, "sha256": "5dfe8c3dc99e5c8771f383157cdfc1f3def1f4e72810094a16e6203dbaf4c150"}, "sw.js": {"baseline_sha256": "762def01d565789b81a6c57d9eaa7cd546dbe0bbf42f415490e76eff890a6c9e", "bytes": 5679, "sha256": "11091e96760a045f952650a8e720ed02607307cb87173f5978cd9f246c6fdfd0"}}')
GUARDS = json.loads('{".htaccess": "993e7a8936737dbf9ba852e60604141de15e24d7399e644393282ed99b7ff690", "admin/audit.php": "07fd9e1806925faa64e65bc9b916dfc61f8dfd96e8498941ff9628885706d867", "admin/health.php": "8f89221fdabaaad204fc7005136c8fb559f6ca9f7ad9238a764dc86b8d1eb409", "admin/index.php": "9233559775bdcd1a95bce16c4a06d80d085a0e51e52aadc214985bcba750b5a0", "admin/timecards.php": "6950397e9f8d8c88bba1bd5696f62e84419f795d79922877898d89c71d9b6d47", "assets/visuals/kcmc-building-2024.webp": "cd2a12a3211b89ee523bef80a4fee5c3ed7429f6404b2d23530bae61f600e0fb", "assets/visuals/kcmc-ministry-group.jpg": "94fdec9c87cafdb00ca59c2f977145007debbe633b8036c4f5db0cd2670e6e4a", "assets/visuals/kcmc-stage-2014.webp": "904827c79e9332706b8c19c73d4cb211c116629a0f974f4d6df211596df6c994", "assets/visuals/kcmc-worship-2017.webp": "4593491d1f8f2d8592bc6382928eb51a41170b910ed2bd2271c491a7866315a8", "care.php": "0c48c6d5dab7c18329158c68152c441d7194aa334daf074ac663a294e6b3855e", "lib/bootstrap.php": "32cff7ba681a9c5163be880af62a358b331b6dbfe91b0fce9621497ef9413b31", "member/login.php": "2db61ebc38cbb126a6f67d858bdb60e2553ea015d36cfdced869828887ddc4de", "member/timeclock.php": "7864fdee399f90ae5a5bea97fa4c0bf9b5a6a23255f4de31051d21c03bf1663d"}')
BASELINE_EXPECTATIONS = json.loads('{"admin/publication-designer.php": {"bytes": 20913, "mode": 420}, "admin/publication-projects.php": {"bytes": 6087, "mode": 420}, "index.php": {"bytes": 29760, "mode": 420}, "public-presentation.css": {"bytes": 5793, "mode": 420}, "public-presentation.js": {"bytes": 7746, "mode": 420}, "sw.js": {"bytes": 5239, "mode": 420}}')
GIT_SHAS = json.loads('{"admin/publication-designer.php": "0d768e40bf1294f2eb4ee8db406a0305af44e319", "admin/publication-media.php": "8610de8eef17ee596150e5ae81b06fb52a864ba5", "admin/publication-projects.php": "5aa61e6e23da4ec7a327d8345f8f0067c1c5140b", "assets/visuals/kcmc-bridge-logo-composite.png": "b789dd80629facf4877bdbc738952cc7434828ac", "assets/visuals/kcmc-bridge-logo.jpg": "c9879869137c1ff45363266268b584973bd0c246", "assets/visuals/kcmc-bridge-wordmark.png": "1c49662e0f31b7beca2932887879a286073b308d", "assets/visuals/kcmc-church-wordmark.jpg": "38b31ac1e7db8fcd1db77496440831849aaa885b", "assets/visuals/kcmc-congregation-gathering.jpg": "47b1d86c8bae2d946734c441656339e80da20b98", "assets/visuals/kcmc-family-outdoor-event.jpg": "e2518862f928ec05d586c9a076a1a51541b05a62", "assets/visuals/kcmc-kids-game-room.jpg": "e47dad1d5e77feaf07a1a6b1d24cfdb4d3c8ff73", "assets/visuals/kcmc-kids-safari.jpg": "279141e9ffb1bd7f6541b91a1c63d8d7e828a7b0", "assets/visuals/kcmc-kids-summer-group.jpg": "d86f7fb394dab54360a6b76c9d4b3f197318a3ff", "index.php": "781e18b6490c851a619c5b6150ce4d5d1898cae7", "public-presentation.css": "703e1424b39cfc0e6eacb7585cf47ca1b9fdad4b", "public-presentation.js": "a0cbbd2859d2646e254a271b3830f57eb9be9a1e", "sw.js": "b9c74c775e4e0cdb5b7db956e128584a162ee8b6"}')
ALLOWED = set(['index.php', 'public-presentation.js', 'public-presentation.css', 'sw.js',
               'admin/publication-designer.php', 'admin/publication-projects.php',
               'admin/publication-media.php',
               'assets/visuals/kcmc-congregation-gathering.jpg',
               'assets/visuals/kcmc-family-outdoor-event.jpg',
               'assets/visuals/kcmc-bridge-logo.jpg', 'assets/visuals/kcmc-kids-safari.jpg',
               'assets/visuals/kcmc-kids-game-room.jpg', 'assets/visuals/kcmc-kids-summer-group.jpg',
               'assets/visuals/kcmc-church-wordmark.jpg', 'assets/visuals/kcmc-bridge-wordmark.png',
               'assets/visuals/kcmc-bridge-logo-composite.png'])


class Refusal(RuntimeError):
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
    require(FILES and set(FILES).issubset(ALLOWED), 'Empty or out-of-scope inventory')
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


def fetch_bytes(path):
    url = SOURCE_ROOT + urllib.parse.quote(relative(path), safe='/')
    request = urllib.request.Request(url, headers={'User-Agent': 'KCMC-pinned-code-transaction'})
    with urllib.request.urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
        require(response.geturl() == url and response.status == 200, 'Pinned source redirect/status refused')
        data = response.read(FILES[path]['bytes'] + 1)
    require(len(data) == FILES[path]['bytes'] and digest(data) == FILES[path]['sha256'], 'Approved download hash mismatch: ' + path)
    source_hash(path, data)
    return data


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
    print('Staged PHP 8.2 syntax verified; JavaScript syntax ' + ('verified' if node else 'unavailable on host (approved CI source remains hash-pinned)'))


def verify_http():
    checks = [('', ['data-contemporary-feature', 'kcmc-congregation-gathering.jpg', 'kcmc-bridge-wordmark.png',
                    'public-presentation.css', 'public-presentation.js']),
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
    for path, approved in FILES.items():
        if path.endswith('.php'):
            continue
        url = PUBLIC_ROOT + urllib.parse.quote(path, safe='/')
        request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'KCMC-read-only-release-check'})
        with urllib.request.urlopen(request, timeout=45, context=ssl.create_default_context()) as response:
            require(response.status == 200 and response.geturl() == url, 'Static verification redirect/status refused: ' + path)
            body = response.read(approved['bytes'] + 1)
        require(len(body) == approved['bytes'] and digest(body) == approved['sha256'], 'Public static hash mismatch: ' + path)


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


def read_session(session):
    session = Path(session)
    require(session.parent == BACKUP_ROOT and session.name.startswith('release-'), 'Unknown backup session')
    require(session.is_dir(), 'Backup session does not exist')
    data, info = read_private(session / 'manifest.json')
    require(info['mode'] == 0o600 and info['uid'] == os.getuid(), 'Unsafe session manifest')
    value = json.loads(data.decode('utf-8'))
    require(isinstance(value, dict) and set(value) == set(['version', 'app', 'commit', 'phase', 'files', 'protected', 'publisher', 'intent']) and
            value['version'] == 1 and value['phase'] in ('prepared', 'applying', 'applied', 'failed', 'rolling_back', 'rolled_back'),
            'Unknown session journal format')
    require(isinstance(value['files'], dict) and isinstance(value['protected'], dict) and
            value['commit'] == COMMIT and value['app'] == str(APP_ROOT) and
            set(value['files']) == set(FILES), 'Session scope/source mismatch')
    require(value['intent'] is None or value['intent'] in FILES, 'Unknown session installation intent')
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
        require((baseline['sha256'] if baseline else None) == FILES[path]['baseline_sha256'], 'Session baseline changed')
        if path in BASELINE_EXPECTATIONS:
            require(baseline is not None and all(baseline[key] == expected for key, expected in BASELINE_EXPECTATIONS[path].items()),
                    'Session baseline receipt changed')
        for kind in ('candidate', 'installed'):
            if record[kind] is not None:
                valid_metadata(record[kind])
                require(record[kind]['sha256'] == FILES[path]['sha256'] and record[kind]['bytes'] == FILES[path]['bytes'],
                        'Session installation source changed')
    require(set(value['protected']) == set(GUARDS) | set([CONTENT_PATH]), 'Session protected scope changed')
    for record in value['protected'].values():
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


def prepare_unlocked():
    inventory()
    originals = {}
    protected = protected_capture()
    publisher = capture_stores()
    for path, approved in FILES.items():
        data, info = read_file(APP_ROOT / path, missing=True)
        require((info['sha256'] if info else None) == approved['baseline_sha256'], 'Live baseline drift: ' + path)
        if path in BASELINE_EXPECTATIONS:
            require(info is not None and info['bytes'] == BASELINE_EXPECTATIONS[path]['bytes'] and
                    info['mode'] == BASELINE_EXPECTATIONS[path]['mode'], 'Owner receipt size/mode drift: ' + path)
        originals[path] = (data, info)
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
             'files': records, 'protected': protected, 'publisher': publisher, 'intent': None}
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
        elif path in ('public-presentation.css', 'public-presentation.js'):
            rank = 1
        elif path in ('admin/publication-media.php', 'admin/publication-projects.php'):
            rank = 2
        elif path == 'admin/publication-designer.php':
            rank = 3
        else:
            rank = 4
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


def apply(session=None):
    inventory()
    with locked(), publisher_locked():
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
            print('Pinned code applied and read-only public markers verified. Private session: ' + str(session))
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
