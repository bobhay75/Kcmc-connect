<?php
declare(strict_types=1);
require_once __DIR__ . '/../tools/plan-event-reconciliation.php';

$checks = 0;
function ep_check(bool $ok, string $message): void {
    global $checks;
    if (!$ok) throw new RuntimeException($message);
    $checks++;
    echo "ok $checks - $message\n";
}
function ep_reject(callable $operation, string $message): void {
    $rejected = false;
    try { $operation(); } catch (Throwable $e) { $rejected = true; }
    ep_check($rejected, $message);
}
function ep_event(string $id, array $changes = []): stdClass {
    return (object)array_merge([
        'id' => $id, 'title' => 'Breakfast', 'date' => '2026-10-03', 'time' => '8:30 AM',
        'location' => 'Church', 'status' => 'published', 'expires_at' => '2026-10-04T00:00:00-05:00',
    ], $changes);
}
function ep_doc(array $events, array $extra = []): stdClass { return (object)array_merge($extra, ['events' => $events]); }
$now = kcmc_plan_timestamp('2026-09-30T04:00:00-05:00');
$empty = ep_doc([]);
$baseline = ep_doc([ep_event('existing')]);
$addition = ep_event('new-breakfast', ['title' => 'New breakfast']);
$source = ep_doc([ep_event('existing'), $addition]);

try {
    $plan = kcmc_event_reconciliation_plan($baseline, $source, $baseline, $now);
    ep_check(count($plan['proposed_additions']) === 1 && $plan['proposed_additions'][0]->id === 'new-breakfast', 'proposes only genuinely new repository IDs');
    ep_check($plan['write_enabled'] === false && $plan['requires_editorial_approval'] === true, 'proposal always remains read-only and approval-gated');

    $host = ep_doc([ep_event('existing', ['title' => 'Church edited title']), ep_event('host-only')], ['private_marker' => 'DO_NOT_OUTPUT']);
    $before = kcmc_plan_canonical($host);
    $plan = kcmc_event_reconciliation_plan($baseline, $source, $host, $now);
    ep_check($before === kcmc_plan_canonical($host), 'does not mutate input or host edits');
    ep_check($plan['preserved_host_only_ids'] === ['host-only'], 'preserves host-only event IDs');
    ep_check(strpos(json_encode($plan), 'DO_NOT_OUTPUT') === false, 'does not output unrelated host content');
    ep_check(count($plan['conflicts']) === 0, 'does not treat host edits to unchanged baseline rows as repository replacements');

    $plan = kcmc_event_reconciliation_plan($baseline, $source, $empty, $now);
    ep_check($plan['preserved_missing_baseline_ids'] === ['existing'] && count($plan['proposed_additions']) === 1, 'never resurrects deleted baseline events');
    $changedSource = ep_doc([ep_event('existing', ['time' => '9:00 AM'])]);
    $plan = kcmc_event_reconciliation_plan($baseline, $changedSource, $baseline, $now);
    ep_check($plan['status'] === 'conflict_review_required' && $plan['conflicts'][0]['reason'] === 'repository_changed_existing_event', 'flags repository modifications instead of overwriting old rows');

    $host = ep_doc([ep_event('new-breakfast', ['title' => 'Church correction'])]);
    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([$addition]), $host, $now);
    ep_check(count($plan['proposed_additions']) === 0 && $plan['conflicts'][0]['reason'] === 'same_id_different_content', 'blocks same-ID conflicts');
    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([$addition]), ep_doc([$addition]), $now);
    ep_check($plan['already_present'] === ['new-breakfast'] && count($plan['proposed_additions']) === 0, 'is idempotent when additions already exist');
    $reordered = (object)array_reverse(get_object_vars($addition), true);
    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([$addition]), ep_doc([$reordered]), $now);
    ep_check(count($plan['conflicts']) === 0 && count($plan['already_present']) === 1, 'ignores JSON object key order');

    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([$addition]), ep_doc([ep_event('different-id', ['title' => ' New   breakfast '])]), $now);
    ep_check($plan['conflicts'][0]['reason'] === 'possible_duplicate_event' && count($plan['proposed_additions']) === 0, 'flags same-title/date host events with different IDs');
    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([ep_event('a'), ep_event('b')]), $empty, $now);
    ep_check($plan['status'] === 'conflict_review_required', 'flags duplicate-looking source additions');

    $cases = [
        'hidden' => [['status' => 'hidden'], 'not_published'],
        'expired' => [['expires_at' => '2026-09-30T09:00:00Z'], 'expired'],
        'past' => [['date' => '2026-09-29'], 'past_date'],
        'invalid-date' => [['date' => '2026-02-30'], 'invalid_date'],
        'invalid-time' => [['time' => '25:00 PM'], 'invalid_time'],
        'invalid-expiry' => [['expires_at' => 'tomorrow'], 'invalid_timestamp'],
        'not-started' => [['starts_at' => '2026-10-01T00:00:00-05:00'], 'not_yet_published'],
        'missing-field' => [['location' => ''], 'incomplete_event'],
    ];
    foreach ($cases as $id => [$changes, $expected]) {
        $plan = kcmc_event_reconciliation_plan($empty, ep_doc([ep_event($id, $changes)]), $empty, $now);
        ep_check(count($plan['proposed_additions']) === 0 && $plan['skipped'][0]['reason'] === $expected, 'excludes ' . $id . ' candidate');
    }
    $nearMidnight = kcmc_plan_timestamp('2026-09-30T00:30:00Z');
    $plan = kcmc_event_reconciliation_plan($empty, ep_doc([ep_event('local-date', ['date' => '2026-09-29'])]), $empty, $nearMidnight);
    ep_check(count($plan['proposed_additions']) === 1, 'uses America/Chicago date rather than UTC date');
    ep_reject(fn() => kcmc_plan_timestamp('2026-09-30T04:00:00'), 'rejects ambiguous as-of time without timezone');
    ep_reject(fn() => kcmc_plan_timestamp('2026-02-30T04:00:00-05:00'), 'rejects impossible as-of calendar date');
    ep_reject(fn() => kcmc_plan_events(ep_doc([ep_event('dup'), ep_event('dup')])), 'rejects duplicate IDs');
    ep_reject(fn() => kcmc_plan_events((object)['events' => (object)[]]), 'rejects object instead of events list');
    ep_reject(fn() => kcmc_plan_events((object)[]), 'rejects absent events instead of assuming empty host');
    ep_reject(fn() => kcmc_plan_events(ep_doc([(object)['id' => '../invalid']])), 'rejects malformed IDs');
    ep_reject(fn() => kcmc_plan_read_snapshot('https://example.invalid/content.json'), 'rejects remote inputs and wrappers');

    $directory = sys_get_temp_dir() . '/kcmc-event-plan-test-' . bin2hex(random_bytes(8));
    if (!mkdir($directory, 0700)) throw new RuntimeException('Fixture directory could not be created.');
    try {
        foreach (['baseline' => $baseline, 'source' => $source, 'live' => $host] as $label => $document) {
            file_put_contents($directory . '/' . $label . '.json', json_encode($document, JSON_THROW_ON_ERROR));
        }
        $inputPaths = glob($directory . '/*.json');
        $hashes = array_map(static fn(string $path): string => hash_file('sha256', $path), $inputPaths);
        $read = kcmc_plan_read_snapshot($directory . '/source.json');
        ep_check($read['sha256'] === hash_file('sha256', $directory . '/source.json'), 'hashes exact snapshot bytes for future concurrency checks');
        ob_start();
        $code = kcmc_plan_main([
            '--baseline=' . $directory . '/baseline.json', '--source=' . $directory . '/source.json',
            '--live=' . $directory . '/live.json', '--as-of=2026-09-30T04:00:00-05:00',
        ]);
        $output = (string)ob_get_clean();
        $decoded = json_decode($output, true, 128, JSON_THROW_ON_ERROR);
        ep_check($code === 2 && $decoded['status'] === 'conflict_review_required', 'CLI emits JSON and a nonzero code for conflicts');
        ep_check($decoded['input_sha256']['live'] === hash_file('sha256', $directory . '/live.json'), 'CLI fingerprints unfiltered host snapshot');
        ep_check($hashes === array_map(static fn(string $path): string => hash_file('sha256', $path), $inputPaths), 'CLI never rewrites its inputs');
        ep_check(count(glob($directory . '/*')) === 3, 'CLI creates no files or replacement content');
        ob_start();
        $code = kcmc_plan_main(['--apply=yes']);
        ob_end_clean();
        ep_check($code === 1, 'rejects write/apply option');
        file_put_contents($directory . '/invalid.json', '{');
        ep_reject(fn() => kcmc_plan_read_snapshot($directory . '/invalid.json'), 'rejects corrupt JSON');
        symlink($directory . '/live.json', $directory . '/alias.json');
        ep_reject(fn() => kcmc_plan_read_snapshot($directory . '/alias.json'), 'rejects direct symlink inputs');
    } finally {
        foreach (glob($directory . '/*') as $path) unlink($path);
        rmdir($directory);
    }
    echo "PASS: $checks event reconciliation planner checks\n";
} catch (Throwable $e) {
    fwrite(STDERR, 'FAIL: ' . $e->getMessage() . "\n");
    exit(1);
}
