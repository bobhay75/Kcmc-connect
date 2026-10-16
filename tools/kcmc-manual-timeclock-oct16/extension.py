"""Explicit reviewed optional-preimage and dependency transaction policy.

Executed only in a verified frozen-engine namespace. The fixture-only factory
and the fixed production derivation supply separate manifests. Existing parents
are required. This module never creates app directories.
"""
import base64

PARENT_KEYS = ('dev', 'ino', 'mode', 'uid', 'gid')


def inventory():
    require(tuple(FILES) == PATHS and bool(PATHS), 'Fixture inventory mismatch')
    require(APP.is_absolute() and BACKUPS.is_absolute() and APP != BACKUPS and 'public_html' not in BACKUPS.parts,
            'Invalid fixed repair roots')
    require(os.link in os.supports_dir_fd and os.link in os.supports_follow_symlinks and
            os.unlink in os.supports_dir_fd, 'No-clobber link/unlink primitives unavailable; no backup made')
    for path in PATHS:
        require(isinstance(path, str) and not path.startswith('/') and '\\' not in path and
                all(part not in ('', '.', '..') for part in path.split('/')), 'Unsafe fixed code path')
        item = FILES[path]
        expected = set(['before_sha256', 'before_bytes', 'after_sha256', 'after_bytes', 'replacements'])
        absent = item.get('before_sha256') is None
        if absent: expected.add('after_base64')
        require(set(item) == expected, 'Invalid embedded inventory fields')
        require(re.match(r'\A[0-9a-f]{64}\Z', item['after_sha256']) and
                type(item['after_bytes']) is int and 0 < item['after_bytes'] <= MAX_BYTES, 'Invalid target bytes')
        if absent:
            require(item['before_bytes'] == 0 and item['replacements'] == [] and isinstance(item['after_base64'], str),
                    'Absent preimage must be exact')
            content = base64.b64decode(item['after_base64'].encode('ascii'), validate=True)
            require(digest(content) == item['after_sha256'] and len(content) == item['after_bytes'], 'New source payload changed')
        else:
            require(isinstance(item['before_sha256'], str) and re.match(r'\A[0-9a-f]{64}\Z', item['before_sha256']) and
                    type(item['before_bytes']) is int and 0 < item['before_bytes'] <= MAX_BYTES and
                    isinstance(item['replacements'], list) and item['replacements'] and
                    all(isinstance(pair, list) and len(pair) == 2 and all(isinstance(value, str) for value in pair) and pair[0]
                        for pair in item['replacements']), 'Invalid existing code preimage')
    require(isinstance(DEPENDENCIES, dict) and set(DEPENDENCIES).issubset(set(PATHS)), 'Unknown dependency consumer')
    for consumer, providers in DEPENDENCIES.items():
        require(isinstance(providers, tuple) and len(set(providers)) == len(providers) and
                all(provider in PATHS and PATHS.index(provider) < PATHS.index(consumer) for provider in providers),
                'Providers must precede consumers in the exact inventory')


def parent_metadata(info):
    return {'dev': info.st_dev, 'ino': info.st_ino, 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}


def parent_lease(path):
    with Parent((APP / path).parent) as parent:
        return parent_metadata(os.fstat(parent.fd))


def verify_parent(path, expected):
    require(parent_lease(path) == expected, 'Target parent lease changed: ' + path)


def absent_at(parent, name):
    try:
        os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        parent.check()
        return
    raise Refusal('Expected absent code appeared: ' + name)


def optional_live(path):
    with Parent((APP / path).parent) as parent:
        lease = parent_metadata(os.fstat(parent.fd))
        try:
            content, info = read_at(parent, Path(path).name)
        except FileNotFoundError:
            absent_at(parent, Path(path).name)
            return None, None, lease
        require(info['mode'] in (0o644, 0o664), 'Code mode must already be 0644 or 0664: ' + path)
        return content, info, lease


def verify_lease(path, expected):
    if expected is None:
        with Parent((APP / path).parent) as parent:
            absent_at(parent, Path(path).name)
        return None
    _, actual = live(path)
    require(same(actual, expected), 'Code lease changed: ' + path)
    return actual


def inspect():
    caller(); inventory()
    found, kinds = {}, []
    for path in PATHS:
        content, info, parent = optional_live(path); item = FILES[path]
        if info is None:
            require(item['before_sha256'] is None, 'Required existing code is absent: ' + path)
            kind = 'before'
        else:
            matches = [kind for kind in ('before', 'after') if info['sha256'] == item[kind + '_sha256'] and
                       info['bytes'] == item[kind + '_bytes']]
            require(len(matches) == 1, 'Unknown code bytes: ' + path); kind = matches[0]
        found[path] = (content, info, parent); kinds.append(kind)
    require(len(set(kinds)) == 1, 'Mixed before/after code bundle refused; no repair made')
    for path in PATHS:
        verify_parent(path, found[path][2]); verify_lease(path, found[path][1])
    return kinds[0], found


def repair(path, content):
    item = FILES[path]
    if item['before_sha256'] is None:
        require(content is None, 'New source requires an absent preimage')
        content = base64.b64decode(item['after_base64'].encode('ascii'), validate=True)
    else:
        require(digest(content) == item['before_sha256'] and len(content) == item['before_bytes'], 'Repair preimage changed')
        for old, new in item['replacements']:
            old, new = old.encode('utf-8'), new.encode('utf-8')
            require(content.count(old) == 1, 'Repair anchor is not unique: ' + path)
            content = content.replace(old, new, 1)
    require(digest(content) == item['after_sha256'] and len(content) == item['after_bytes'], 'Repair output hash mismatch')
    return content


def load(session):
    require(Path(session).parent == BACKUPS, 'Session escaped fixed backup root')
    session_name(Path(session).name); private_dir(BACKUPS); private_dir(session)
    content, meta = read(Path(session) / 'journal.json'); require(meta['mode'] == 0o600, 'Unsafe journal permissions')
    value = json.loads(content.decode('ascii'))
    require(isinstance(value, dict) and set(value) == set(['release', 'app', 'phase', 'intent', 'uncertain', 'files']) and
            value['release'] == RELEASE and value['app'] == str(APP) and isinstance(value['files'], dict) and
            set(value['files']) == set(PATHS) and
            value['phase'] in ('prepared', 'applying', 'applied', 'rolling_back', 'rolled_back', 'manual_review') and
            (value['intent'] is None or value['intent'] in PATHS) and isinstance(value['uncertain'], list) and
            all(isinstance(path, str) and path in PATHS for path in value['uncertain']) and
            len(set(value['uncertain'])) == len(value['uncertain']), 'Journal scope/phase refused')
    for path in PATHS:
        record = value['files'][path]
        require(isinstance(record, dict) and set(record) == set(['original', 'candidate', 'installed', 'parent']), 'Invalid file record')
        parent = record['parent']
        require(isinstance(parent, dict) and set(parent) == set(PARENT_KEYS) and
                all(type(parent[key]) is int and parent[key] >= 0 for key in PARENT_KEYS) and
                parent['uid'] == UID and parent['gid'] == GID and not (parent['mode'] & 0o7002), 'Invalid parent lease')
        for kind in ('original', 'candidate', 'installed'):
            info = record[kind]
            if info is None:
                require(kind != 'original' or FILES[path]['before_sha256'] is None, 'Missing existing preimage lease')
                continue
            require(isinstance(info, dict) and set(info) == set(LEASE_KEYS) and
                    isinstance(info['sha256'], str) and re.match(r'\A[0-9a-f]{64}\Z', info['sha256']) and
                    all(type(info[key]) is int and info[key] >= 0 for key in LEASE_KEYS if key != 'sha256') and
                    info['mode'] in (0o644, 0o664) and info['uid'] == UID and info['gid'] == GID and info['nlink'] == 1,
                    'Invalid journal lease')
            source = 'before' if kind == 'original' else 'after'
            require(info['sha256'] == FILES[path][source + '_sha256'] and info['bytes'] == FILES[path][source + '_bytes'],
                    'Journal code source mismatch')
    return value


def lint(session):
    version = subprocess.check_output([PHP, '-n', '-v'], stderr=subprocess.STDOUT, timeout=15)
    require(re.match(br'\APHP 8\.2\.[0-9]+\b', version) is not None, 'Fixed PHP8.2 CLI required')
    for index, path in enumerate(PATHS):
        staged = Path(session) / ('stage-' + str(index) + '.code'); content, info = read(staged)
        require(info['mode'] == 0o600 and info['sha256'] == FILES[path]['after_sha256'] and
                info['bytes'] == FILES[path]['after_bytes'], 'Pinned stage bytes changed')
        if path.endswith('.php'):
            subprocess.check_output([PHP, '-n', '-l', str(staged)], stderr=subprocess.STDOUT, timeout=15)


def bundle_lease(value, check_lock):
    check_lock()
    for path in PATHS:
        record = value['files'][path]; verify_parent(path, record['parent'])
        verify_lease(path, record['installed'] if record['installed'] is not None else record['original'])


def no_clobber_link(source, target, **kwargs):
    os.link(source, target, follow_symlinks=False, **kwargs)


def unlink_name(name, **kwargs):
    os.unlink(name, **kwargs)


def linked_stage(source, target, held_fd, expected):
    before = os.fstat(held_fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 2 and
            all(metadata(before, b'')[key] == expected[key] for key in LEASE_KEYS if key not in ('sha256', 'bytes', 'ctime_ns', 'nlink')) and
            before.st_size == expected['bytes'], 'Linked stage identity changed')
    os.lseek(held_fd, 0, os.SEEK_SET); chunks, size = [], 0
    while True:
        part = os.read(held_fd, 65536)
        if not part: break
        chunks.append(part); size += len(part); require(size <= MAX_BYTES, 'Oversized linked stage')
    content = b''.join(chunks); after = os.fstat(held_fd)
    require(same(metadata(before, content), metadata(after, content)) and digest(content) == expected['sha256'] and
            len(content) == expected['bytes'], 'Linked stage bytes changed')
    for parent, name in ((source[0], source[1]), (target[0], target[1])):
        visible = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        require(stat.S_ISREG(visible.st_mode) and same(metadata(visible, content), metadata(after, content)),
                'Linked stage namespace changed')
        parent.check()


def create_code(source, path, staged_expected, check_lock):
    target = APP / path
    with Parent(source.parent) as src, Parent(target.parent) as dst:
        _, staged = read_at(src, source.name); require(same(staged, staged_expected), 'Stage lease changed')
        require(staged['dev'] == os.fstat(dst.fd).st_dev, 'Stage/target filesystem differs')
        absent_at(dst, target.name)
        fd = os.open(source.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=src.fd)
        try:
            check_lock(); src.check(); dst.check()
            held, visible = os.fstat(fd), os.stat(source.name, dir_fd=src.fd, follow_symlinks=False)
            require(all(metadata(item, b'')[key] == staged_expected[key]
                        for item in (held, visible) for key in LEASE_KEYS if key not in ('sha256', 'bytes')) and
                    held.st_size == staged_expected['bytes'], 'Final stage identity changed')
            absent_at(dst, target.name)
            no_clobber_link(source.name, target.name, src_dir_fd=src.fd, dst_dir_fd=dst.fd)
            os.fsync(dst.fd)
            linked_stage((src, source.name), (dst, target.name), fd, staged_expected)
            check_lock(); src.check(); dst.check()
            unlink_name(source.name, dir_fd=src.fd)
            os.fsync(src.fd); check_lock(); src.check(); dst.check()
            _, installed = read_at(dst, target.name)
            require(all(installed[key] == staged_expected[key] for key in LEASE_KEYS if key != 'ctime_ns'),
                    'Created code identity changed')
            return installed
        finally: os.close(fd)


def move_code(source, path, expected, staged_expected, check_lock):
    if expected is None: return create_code(source, path, staged_expected, check_lock)
    return frozen_move_code(source, path, expected, staged_expected, check_lock)


def delete_created_code(path, expected, check_lock):
    target = APP / path
    with Parent(target.parent) as parent:
        _, actual = read_at(parent, target.name); require(same(actual, expected), 'Created file lease changed before deletion')
        fd = os.open(target.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent.fd)
        try:
            check_lock(); parent.check()
            held, visible = os.fstat(fd), os.stat(target.name, dir_fd=parent.fd, follow_symlinks=False)
            require(all(metadata(item, b'')[key] == expected[key]
                        for item in (held, visible) for key in LEASE_KEYS if key not in ('sha256', 'bytes')) and
                    held.st_size == expected['bytes'], 'Final created-file descriptor/path lease changed')
            unlink_name(target.name, dir_fd=parent.fd)
            os.fsync(parent.fd); check_lock(); parent.check(); absent_at(parent, target.name)
        finally: os.close(fd)


def provider_needed(path, value, uncertain, conflicts):
    providers = set(provider for nodes in DEPENDENCIES.values() for provider in nodes)
    if path not in providers: return False
    # Conflicting/unknown consumer bytes may depend on any approved provider.
    if uncertain or conflicts: return True
    def uses(node, provider):
        return provider in DEPENDENCIES.get(node, ()) or any(uses(parent, provider) for parent in DEPENDENCIES.get(node, ()))
    for node in PATHS:
        if node == path or not uses(node, path): continue
        record = value['files'][node]
        # A completed consumer restore/deletion is a lease, not a lasting fact.
        # A concurrent writer may recreate it after its completion journal.
        try:
            verify_parent(node, record['parent'])
            verify_lease(node, record['installed'] if record['installed'] is not None else record['original'])
        except BaseException:
            if node not in uncertain: uncertain.append(node)
            return True
        if record['installed'] is not None: return True
    return False


def restore_owned(session, value, check_lock):
    uncertain = list(value['uncertain'])
    if value['intent'] is not None and value['intent'] not in uncertain: uncertain.append(value['intent'])
    value['uncertain'] = uncertain; conflicts = []; value['phase'] = 'rolling_back'
    try: journal(session, value)
    except BaseException: pass
    for index in reversed(range(len(PATHS))):
        path = PATHS[index]; record = value['files'][path]
        if record['installed'] is None or path in uncertain: continue
        if provider_needed(path, value, uncertain, conflicts): conflicts.append(path); continue
        try:
            def recovery_check():
                check_lock()
                require(not provider_needed(path, value, uncertain, conflicts),
                        'Dependent consumer lease changed; provider retained: ' + path)
            recovery_check(); verify_parent(path, record['parent']); verify_lease(path, record['installed'])
            if record['original'] is None:
                value['intent'] = path; journal(session, value)
                delete_created_code(path, record['installed'], recovery_check)
            else:
                content, original_meta = read(Path(session) / ('original-' + str(index) + '.code'))
                require(original_meta['mode'] == 0o600 and digest(content) == record['original']['sha256'], 'Original backup changed')
                staged = Path(session) / ('restore-' + uuid.uuid4().hex + '.code'); write_private(staged, content)
                candidate = set_stage_mode(staged, record['original']['mode']); verify_lease(path, record['installed'])
                value['intent'] = path; journal(session, value)
                record['original'] = move_code(staged, path, record['installed'], candidate, recovery_check)
            record['installed'] = None; record['candidate'] = None
            value['intent'] = uncertain[-1] if uncertain else None; journal(session, value)
        except BaseException:
            conflicts.append(path)
            if value['intent'] == path and path not in uncertain: uncertain.append(path)
    value['intent'] = uncertain[-1] if uncertain else None
    value['phase'] = 'manual_review' if uncertain or conflicts else 'rolled_back'
    try: journal(session, value)
    except BaseException: value['phase'] = 'manual_review'
    return value['phase'] == 'rolled_back'


def apply():
    state, originals = inspect(); unfinished()
    if state == 'after': return None
    with locked() as check_lock:
        unfinished(); state, originals = inspect()
        if state == 'after': return None
        device = backup_device()
        require(all(originals[path][2]['dev'] == device and
                    (originals[path][1] is None or originals[path][1]['dev'] == device) for path in PATHS),
                'Backup staging and target parents must use the same filesystem; no replacement made')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        session = session_name('repair-' + stamp + '-' + uuid.uuid4().hex); private_dir(session, create=True)
        value = {'release': RELEASE, 'app': str(APP), 'phase': 'prepared', 'intent': None, 'uncertain': [],
                 'files': {path: {'original': originals[path][1], 'parent': originals[path][2], 'candidate': None, 'installed': None} for path in PATHS}}
        journal(session, value)
        for index, path in enumerate(PATHS):
            if originals[path][1] is not None: write_private(session / ('original-' + str(index) + '.code'), originals[path][0])
            write_private(session / ('stage-' + str(index) + '.code'), repair(path, originals[path][0]))
        try: lint(session)
        except BaseException:
            value['phase'] = 'rolled_back'; journal(session, value)
            raise Refusal('Staged PHP8.2 syntax verification failed; no live replacement. Private session: ' + str(session))
        bundle_lease(value, check_lock); value['phase'] = 'applying'; journal(session, value)
        previous = signal.getsignal(signal.SIGTERM)
        def interrupted(signum, frame): raise Refusal('Repair interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        try:
            for index, path in enumerate(PATHS):
                bundle_lease(value, check_lock); record = value['files'][path]
                staged = session / ('stage-' + str(index) + '.code')
                candidate = set_stage_mode(staged, record['original']['mode'] if record['original'] else 0o644)
                require(candidate['sha256'] == FILES[path]['after_sha256'], 'Stage bytes changed')
                record['candidate'] = candidate; value['intent'] = path; journal(session, value)
                bundle_lease(value, check_lock)
                record['installed'] = move_code(staged, path, record['original'], candidate, check_lock)
                value['intent'] = None; journal(session, value)
            bundle_lease(value, check_lock); value['phase'] = 'applied'; journal(session, value)
        except BaseException:
            signal.signal(signal.SIGTERM, signal.SIG_IGN); complete = restore_owned(session, value, check_lock)
            raise Refusal(('Repair failed; verified owned code restored.' if complete else
                           'Repair stopped; uncertain or concurrent changes require manual review.') + ' Private session: ' + str(session))
        finally: signal.signal(signal.SIGTERM, previous)
        return session
