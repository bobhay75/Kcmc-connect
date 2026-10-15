"""Finite existing-only recovery policy for the unchanged three-file A5 group.

The reset route relies on the lifecycle helper's designated-owner authority
check. Completed consumer restoration is revalidated before provider downgrade,
including the frozen mover's final lock callback. Journal schema is unchanged.
"""
DEPENDENCIES = {'admin/password-resets.php': ('lib/password-lifecycle.php',)}


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
            verify_lease(node, record['installed'] if record['installed'] is not None else record['original'])
        except BaseException:
            if node not in uncertain: uncertain.append(node)
            return True
        if record['installed'] is not None: return True
    return False


def restore_owned(session, value, check_lock):
    """Restore only verified installed identities; intent alone never grants ownership."""
    uncertain = list(value['uncertain'])
    if value['intent'] is not None and value['intent'] not in uncertain:
        uncertain.append(value['intent'])
    value['uncertain'] = uncertain
    conflicts = []
    value['phase'] = 'rolling_back'
    try:
        journal(session, value)
    except BaseException:
        pass  # Existing durable intent remains; leases also remain in memory.
    for index in reversed(range(len(PATHS))):
        path = PATHS[index]
        record = value['files'][path]
        if record['installed'] is None or path in uncertain:
            continue
        if provider_needed(path, value, uncertain, conflicts):
            conflicts.append(path)
            continue
        try:
            def recovery_check():
                check_lock()
                require(not provider_needed(path, value, uncertain, conflicts),
                        'Dependent owner consumer lease changed; provider retained: ' + path)
            recovery_check()
            verify_lease(path, record['installed'])
            data, original_meta = read(Path(session) / ('original-' + str(index) + '.code'))
            require(original_meta['mode'] == 0o600 and digest(data) == record['original']['sha256'], 'Original backup changed')
            staged = Path(session) / ('restore-' + uuid.uuid4().hex + '.code')
            write_private(staged, data)
            candidate = set_stage_mode(staged, record['original']['mode'])
            verify_lease(path, record['installed'])
            value['intent'] = path
            journal(session, value)
            restored = move_code(staged, path, record['installed'], candidate, recovery_check)
            record['original'] = restored
            record['installed'] = None
            record['candidate'] = None
            value['intent'] = uncertain[-1] if uncertain else None
            journal(session, value)
        except BaseException:
            conflicts.append(path)
            if value['intent'] == path and path not in uncertain:
                uncertain.append(path)
    value['intent'] = uncertain[-1] if uncertain else None
    value['phase'] = 'manual_review' if uncertain or conflicts else 'rolled_back'
    try:
        journal(session, value)
    except BaseException:
        value['phase'] = 'manual_review'
    return value['phase'] == 'rolled_back'
