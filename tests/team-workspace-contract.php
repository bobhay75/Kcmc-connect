<?php
declare(strict_types=1);
/** Isolated state, authorization, and real multi-process concurrency checks. */
$worker = ($argv[1] ?? '') === '--worker';
$private = $worker ? (string)$argv[2] : sys_get_temp_dir() . '/kcmc-team-contract-' . bin2hex(random_bytes(6));
if (!$worker && !mkdir($private, 0700)) throw new RuntimeException('Could not make fixture.');
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
putenv('KCMC_OPERATIONS_OWNER_USER_ID=owner');
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/team-workspace.php';

if ($worker) {
    $case = json_decode((string)file_get_contents($argv[3]), true, 512, JSON_THROW_ON_ERROR);
    file_put_contents($argv[4], 'ready');
    $deadline = microtime(true) + 10;
    while (!is_file($argv[5])) {
        if (microtime(true) > $deadline) throw new RuntimeException('Fixture concurrency barrier timed out.');
        usleep(1000);
    }
    try {
        $result = kcmc_team_mutate($case['user'], $case['action'], $case['input'], $case['now']);
        echo json_encode(['status' => 200, 'result' => $result], JSON_THROW_ON_ERROR);
    } catch (KcmcTeamError $error) {
        echo json_encode(['status' => $error->status, 'code' => $error->errorCode], JSON_THROW_ON_ERROR);
    }
    exit;
}

$checks = 0;
$now = 1792065600;
$owner = ['id' => 'owner', 'active' => true, 'role' => 'recovery_admin', 'display_name' => 'Synthetic Owner'];
$pastor = ['id' => 'pastor', 'active' => true, 'role' => 'pastor_admin', 'display_name' => 'Synthetic Pastor'];
$alice = ['id' => 'alice', 'active' => true, 'role' => 'member', 'display_name' => 'Synthetic Alice'];
$bob = ['id' => 'bob', 'active' => true, 'role' => 'member', 'display_name' => 'Synthetic Bob'];
$prayer = ['id' => 'prayer', 'active' => true, 'role' => 'prayer_team', 'display_name' => 'Synthetic Prayer'];
$inactive = ['id' => 'inactive', 'active' => false, 'role' => 'member', 'display_name' => 'Synthetic Inactive'];
$users = [$owner, $pastor, $alice, $bob, $prayer, $inactive];
$path = $private . '/team-workspace.json';
$prefs = ['view' => 'board', 'sort' => 'due', 'statusfilter' => 'open'];

function ok(bool $condition, string $message): void {
    global $checks;
    if (!$condition) throw new RuntimeException($message);
    $checks++;
    echo 'PASS: ' . $message . "\n";
}
function deny(callable $operation, array $statuses, string $message): void {
    try { $operation(); }
    catch (KcmcTeamError $error) { ok(in_array($error->status, $statuses, true), $message . ' (HTTP ' . $error->status . ')'); return; }
    throw new RuntimeException('Expected refusal: ' . $message);
}
function same_bytes(callable $operation, array $statuses, string $message): void {
    global $path;
    $before = is_file($path) ? file_get_contents($path) : null;
    deny($operation, $statuses, $message);
    ok((is_file($path) ? file_get_contents($path) : null) === $before, $message . ' preserves exact store');
}
function task_input(array $changes = []): array {
    return array_replace(['title' => 'Synthetic task', 'body' => 'Synthetic task details', 'assigned_to' => 'alice',
        'start_date' => '', 'due_date' => '', 'priority' => 'normal', 'status' => 'open', 'blocked' => false,
        'publication_id' => ''], $changes);
}
function create_task(array $changes = [], ?array $actor = null): array {
    global $owner, $now;
    return kcmc_team_mutate($actor ?? $owner, 'create', ['task' => task_input($changes)], $now)['task'];
}
function mutate(array $actor, string $action, array $input): array {
    global $now;
    return kcmc_team_mutate($actor, $action, $input, $now);
}
function comment_input(array $task, string $nonce, string $body = 'Synthetic comment', string $parent = ''): array {
    return ['context' => ['kind' => 'task', 'id' => $task['id']], 'body' => $body, 'parent_id' => $parent, 'nonce' => $nonce];
}
function parallel(array $cases): array {
    global $private, $now;
    $prefix = $private . '/race-' . bin2hex(random_bytes(4));
    $go = $prefix . '-go'; $processes = []; $results = [];
    foreach ($cases as $index => $case) {
        $casePath = $prefix . '-case-' . $index;
        file_put_contents($casePath, json_encode($case + ['now' => $now], JSON_THROW_ON_ERROR));
        $ready = $prefix . '-ready-' . $index;
        $command = [PHP_BINARY, __FILE__, '--worker', $private, $casePath, $ready, $go];
        $process = proc_open($command, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
        if (!is_resource($process)) throw new RuntimeException('Could not start concurrency fixture.');
        fclose($pipes[0]);
        $processes[] = [$process, $pipes, $ready];
    }
    $deadline = microtime(true) + 10;
    foreach ($processes as [, , $ready]) {
        while (!is_file($ready)) {
            if (microtime(true) > $deadline) throw new RuntimeException('Concurrency worker did not become ready.');
            usleep(1000);
        }
    }
    file_put_contents($go, 'go');
    foreach ($processes as [$process, $pipes]) {
        $output = stream_get_contents($pipes[1]); $error = stream_get_contents($pipes[2]);
        fclose($pipes[1]); fclose($pipes[2]);
        if (proc_close($process) !== 0 || $error !== '') throw new RuntimeException('Concurrency worker failed: ' . $error . $output);
        $results[] = json_decode($output, true, 512, JSON_THROW_ON_ERROR);
    }
    foreach (glob($prefix . '*') ?: [] as $file) unlink($file);
    return $results;
}
function clear_fixture(string $directory): void {
    foreach (scandir($directory) ?: [] as $name) {
        if ($name === '.' || $name === '..') continue;
        $entry = $directory . '/' . $name;
        if (is_dir($entry) && !is_link($entry)) clear_fixture($entry); else unlink($entry);
    }
    rmdir($directory);
}

try {
    file_put_contents($private . '/users.json', json_encode(['version' => 1, 'users' => $users], JSON_THROW_ON_ERROR));
    file_put_contents($private . '/publications.json', json_encode(['version' => 2, 'projects' => [
        ['id' => 'pub_aaaaaaaaaaaaaaaaaaaaaaaa', 'name' => 'Synthetic draft title', 'pages' => [['items' => [['text' => 'PRIVATE DRAFT SENTINEL']]]]],
    ]], JSON_THROW_ON_ERROR));
    $untouched = [];
    foreach (['users.json', 'publications.json'] as $name) $untouched[$name] = file_get_contents($private . '/' . $name);
    foreach (['prayers.json', 'timeclock.json', 'invites.json'] as $name) {
        $untouched[$name] = 'UNRELATED PRIVATE SENTINEL ' . $name;
        file_put_contents($private . '/' . $name, $untouched[$name]);
    }

    ok(kcmc_team_read() === kcmc_team_empty(), 'A missing workspace reads as empty');
    ok(!is_file($path), 'A read does not create the workspace store');
    ok(!kcmc_team_has_assigned_tasks($alice), 'Missing-store navigation has no assigned task link');
    ok(!is_file($path), 'Missing-store navigation does not initialize private data');
    $empty = kcmc_team_list($alice, '2026-10-15');
    ok($empty['tasks'] === [] && $empty['users'] === [] && $empty['publications'] === [], 'Ordinary empty view has no task or account directory');
    deny(fn() => kcmc_team_list($inactive), [401, 403], 'Inactive accounts are denied');
    same_bytes(fn() => create_task([], $alice), [403], 'Ordinary accounts cannot create tasks');

    $first = create_task(['title' => '<script>synthetic plain text</script>', 'publication_id' => 'pub_aaaaaaaaaaaaaaaaaaaaaaaa']);
    $second = create_task(['title' => 'Bob task', 'assigned_to' => 'bob']);
    $unassigned = create_task(['title' => 'Unassigned task', 'assigned_to' => '']);
    ok((bool)preg_match('/\Ateamtask_[a-f0-9]{24}\z/', $first['id']), 'Task IDs are generated by the server');
    ok(kcmc_team_read()['tasks'][$first['id']]['created_by'] === 'owner' && $first['created_at'] === $now, 'Task actor and timestamp come from the authenticated request');
    ok($first['title'] === '<script>synthetic plain text</script>', 'Task text is stored literally, without HTML interpretation');
    $memberList = kcmc_team_list($alice, '2026-10-15');
    ok(array_column($memberList['tasks'], 'id') === [$first['id']], 'A member sees only explicitly assigned tasks');
    ok(!array_key_exists('publication_id', $memberList['tasks'][0]) && $memberList['publications'] === [] && $memberList['users'] === [], 'Assignment does not reveal publication links or account directory');
    ok(count(kcmc_team_list($pastor)['tasks']) === 3 && kcmc_team_list($owner)['can_manage'], 'Existing publishers and designated owner can manage the workspace');
    ok(kcmc_team_list($prayer)['tasks'] === [], 'Prayer-team membership grants no shared workspace access');
    same_bytes(fn() => kcmc_team_thread($bob, 'task', $first['id']), [403, 404], 'Another member cannot open the assigned task thread');
    same_bytes(fn() => kcmc_team_thread($alice, 'publication', 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'), [403, 404], 'Task assignment grants no publication thread access');
    same_bytes(fn() => mutate($alice, 'update', ['task_id' => $first['id'], 'revision' => $first['revision'], 'task' => task_input()]), [403], 'An assignee cannot edit task management fields');
    same_bytes(fn() => mutate($bob, 'status', ['task_id' => $first['id'], 'revision' => $first['revision'], 'status' => 'done']), [403, 404], 'A member cannot change another assignee task');

    $updated = mutate($alice, 'status', ['task_id' => $first['id'], 'revision' => $first['revision'], 'status' => 'in_progress',
        'actor_id' => 'owner', 'updated_by' => 'owner', 'updated_at' => 1])['task'];
    ok($updated['status'] === 'in_progress' && kcmc_team_read()['tasks'][$first['id']]['updated_by'] === 'alice' && $updated['updated_at'] === $now, 'Assignee status changes ignore forged actor and time');
    same_bytes(fn() => mutate($alice, 'status', ['task_id' => $first['id'], 'revision' => $first['revision'], 'status' => 'done']), [409], 'A stale task revision fails closed');
    mutate($bob, 'preferences', ['revision' => 0, 'preferences' => $prefs]);
    $changedAgain = mutate($alice, 'status', ['task_id' => $first['id'], 'revision' => $updated['revision'], 'status' => 'done'])['task'];
    ok($changedAgain['status'] === 'done', 'An unrelated preference write does not invalidate the task revision');

    mutate($alice, 'preferences', ['revision' => 0, 'preferences' => $prefs, 'user_id' => 'bob']);
    $alicePrefs = kcmc_team_list($alice)['preferences'];
    $bobPrefs = kcmc_team_list($bob)['preferences'];
    ok($alicePrefs['view'] === 'board' && $bobPrefs['revision'] === 1, 'Preference updates use only the authenticated user key');
    same_bytes(fn() => mutate($alice, 'preferences', ['revision' => 0, 'preferences' => $prefs]), [409], 'A stale preference revision is rejected');
    same_bytes(fn() => mutate($alice, 'preferences', ['revision' => $alicePrefs['revision'], 'preferences' => $prefs + ['role' => 'recovery_admin']]), [422], 'Preferences cannot grant account authority');
    mutate($alice, 'preferences', ['revision' => $alicePrefs['revision'], 'preferences' => ['view' => 'timeline', 'sort' => 'priority', 'statusfilter' => 'all']]);
    ok(kcmc_team_list($bob)['preferences'] === $bobPrefs, 'Another user preferences remain unchanged');

    $comment = mutate($alice, 'comment', comment_input($first, 'synthetic_comment_nonce_01', 'First synthetic comment'))['comment'];
    $raw = file_get_contents($path);
    $duplicate = mutate($alice, 'comment', comment_input($first, 'synthetic_comment_nonce_01', 'First synthetic comment'));
    ok($duplicate['duplicate'] === true && $duplicate['comment']['id'] === $comment['id'], 'An identical actor-scoped nonce returns the prior comment');
    ok(file_get_contents($path) === $raw, 'A retried comment preserves exact store bytes');
    same_bytes(fn() => mutate($alice, 'comment', comment_input($first, 'synthetic_comment_nonce_01', 'Different retry words')), [409], 'Reusing a comment nonce with changed content is rejected');
    $reply = mutate($owner, 'comment', comment_input($first, 'synthetic_comment_nonce_02', 'A contextual reply', $comment['id']))['comment'];
    ok($reply['parent_id'] === $comment['id'], 'A reply can reference a parent in its authorized task context');
    same_bytes(fn() => mutate($bob, 'comment', comment_input($second, 'synthetic_comment_nonce_03', 'Wrong context parent', $comment['id'])), [403, 404, 422], 'A parent from another task is refused');
    $publicationComment = mutate($owner, 'comment', ['context' => ['kind' => 'publication', 'id' => 'pub_aaaaaaaaaaaaaaaaaaaaaaaa'],
        'body' => 'Publication-only thread', 'parent_id' => '', 'nonce' => 'synthetic_publication_nonce'])['comment'];
    same_bytes(fn() => mutate($alice, 'comment', comment_input($first, 'synthetic_comment_nonce_04', 'Wrong publication parent', $publicationComment['id'])), [403, 404, 422], 'A publication parent cannot bridge into an assigned task');
    $thread = kcmc_team_thread($alice, 'task', $first['id']);
    ok(count($thread['comments']) === 2 && !str_contains(json_encode($thread, JSON_THROW_ON_ERROR), 'Publication-only thread'), 'An assigned task thread excludes unrelated publication comments');
    $sameNonceOtherActor = mutate($owner, 'comment', comment_input($first, 'synthetic_comment_nonce_01', 'First synthetic comment'));
    ok($sameNonceOtherActor['duplicate'] === false && $sameNonceOtherActor['comment']['id'] !== $comment['id'], 'The same nonce from another authorized actor creates that actor own comment');
    ok($sameNonceOtherActor['comment']['author_id'] === 'owner', 'Cross-actor nonce use does not return another author identity');
    same_bytes(fn() => kcmc_team_thread($owner, 'publication', 'pub_' . str_repeat('b', 24)), [404], 'A nonexistent publication thread is not available');
    same_bytes(fn() => mutate($owner, 'comment', ['context' => ['kind' => 'publication', 'id' => 'pub_' . str_repeat('b', 24)],
        'body' => 'Unavailable discussion', 'parent_id' => '', 'nonce' => 'missing_publication_nonce']), [404], 'A publisher cannot append to a nonexistent publication');

    foreach ([['title' => ''], ['title' => str_repeat('x', 161)], ['body' => str_repeat('x', 4001)],
        ['assigned_to' => 'inactive'], ['assigned_to' => 'missing'], ['due_date' => '2026-02-30'],
        ['start_date' => '2026-10-20', 'due_date' => '2026-10-19'], ['priority' => 'urgent'],
        ['status' => 'approved'], ['blocked' => 'yes'], ['publication_id' => 'pub_missing']] as $bad) {
        same_bytes(fn() => create_task($bad), [422, 404], 'Invalid task field ' . implode(',', array_keys($bad)) . ' is rejected');
    }
    foreach ([['body' => ''], ['body' => str_repeat('x', 2001)], ['nonce' => 'tiny'], ['nonce' => str_repeat('x', 97)], ['nonce' => 'invalid nonce with space']] as $bad) {
        same_bytes(fn() => mutate($alice, 'comment', array_replace(comment_input($first, 'valid_unused_nonce_01'), $bad)), [422], 'Comment bounds ' . implode(',', array_keys($bad)) . ' are enforced');
    }

    $current = kcmc_team_read()['tasks'][$first['id']];
    $reassigned = mutate($owner, 'update', ['task_id' => $first['id'], 'revision' => $current['revision'],
        'task' => task_input(['assigned_to' => 'bob'])])['task'];
    ok(!in_array($first['id'], array_column(kcmc_team_list($alice)['tasks'], 'id'), true), 'Assignment removal immediately removes task visibility');
    same_bytes(fn() => mutate($alice, 'status', ['task_id' => $first['id'], 'revision' => $reassigned['revision'], 'status' => 'done']), [403, 404], 'A previous assignee cannot retain write access');
    same_bytes(fn() => mutate($alice, 'comment', comment_input($first, 'removed_assignment_nonce')), [403, 404], 'A previous assignee cannot append comments');
    same_bytes(fn() => mutate($alice, 'comment', comment_input($first, 'synthetic_comment_nonce_01', 'First synthetic comment')), [403, 404], 'A cached retry cannot bypass revoked assignment access');

    $deactivatedUsers = $users;
    foreach ($deactivatedUsers as &$account) if ($account['id'] === 'alice') $account['active'] = false;
    unset($account);
    file_put_contents($private . '/users.json', json_encode(['version' => 1, 'users' => $deactivatedUsers], JSON_THROW_ON_ERROR));
    same_bytes(fn() => create_task(), [422], 'An account deactivated after the page loaded cannot receive a new assignment');
    ok(!in_array('alice', array_column(kcmc_team_list($owner)['users'], 'id'), true), 'A deactivated account is absent from current assignment choices');
    file_put_contents($private . '/users.json', $untouched['users.json']);

    $raceTask = create_task(['title' => 'Competing task edits']);
    $raceCases = [];
    foreach (['in_progress', 'done'] as $status) $raceCases[] = ['user' => $alice, 'action' => 'status',
        'input' => ['task_id' => $raceTask['id'], 'revision' => $raceTask['revision'], 'status' => $status]];
    $results = parallel($raceCases); $statuses = array_column($results, 'status'); sort($statuses);
    ok($statuses === [200, 409], 'Two simultaneous writes to one task revision yield one winner and one conflict');
    $winner = array_values(array_filter($results, fn($result) => $result['status'] === 200))[0]['result']['task'];
    ok(kcmc_team_read()['tasks'][$raceTask['id']]['status'] === $winner['status'], 'The concurrent winning edit remains stored');

    $raceA = create_task(['title' => 'Distinct task A']); $raceB = create_task(['title' => 'Distinct task B', 'assigned_to' => 'bob']);
    $results = parallel([
        ['user' => $alice, 'action' => 'status', 'input' => ['task_id' => $raceA['id'], 'revision' => $raceA['revision'], 'status' => 'done']],
        ['user' => $bob, 'action' => 'status', 'input' => ['task_id' => $raceB['id'], 'revision' => $raceB['revision'], 'status' => 'in_progress']],
    ]);
    ok(array_column($results, 'status') === [200, 200], 'Concurrent independent task revisions do not conflict');
    $after = kcmc_team_read();
    ok($after['tasks'][$raceA['id']]['status'] === 'done' && $after['tasks'][$raceB['id']]['status'] === 'in_progress', 'Concurrent changes on distinct tasks both survive');

    $results = parallel([
        ['user' => $alice, 'action' => 'preferences', 'input' => ['revision' => kcmc_team_list($alice)['preferences']['revision'], 'preferences' => ['view' => 'list', 'sort' => 'due', 'statusfilter' => 'done']]],
        ['user' => $bob, 'action' => 'preferences', 'input' => ['revision' => kcmc_team_list($bob)['preferences']['revision'], 'preferences' => ['view' => 'timeline', 'sort' => 'smart', 'statusfilter' => 'all']]],
    ]);
    ok(array_column($results, 'status') === [200, 200], 'Concurrent distinct-user preferences both commit');
    ok(kcmc_team_list($alice)['preferences']['view'] === 'list' && kcmc_team_list($bob)['preferences']['view'] === 'timeline', 'Per-user preference changes do not overwrite one another');

    $nonceCase = ['user' => $alice, 'action' => 'comment', 'input' => comment_input($raceA, 'concurrent_identical_nonce', 'Exactly one concurrent comment')];
    $beforeComments = count(kcmc_team_read()['comments']);
    $results = parallel([$nonceCase, $nonceCase]);
    ok(array_column($results, 'status') === [200, 200], 'Concurrent retry requests both receive a successful result');
    ok(count(kcmc_team_read()['comments']) === $beforeComments + 1, 'Actor nonce deduplication runs under the write lock');
    $duplicates = array_column(array_column($results, 'result'), 'duplicate'); sort($duplicates);
    ok($duplicates === [false, true], 'Exactly one concurrent comment request is recorded as a duplicate');

    $ties = [];
    foreach (['teamtask_' . str_repeat('a', 24), 'teamtask_' . str_repeat('b', 24)] as $id) $ties[] = array_replace($raceA, ['id' => $id]);
    foreach (['smart', 'due', 'priority'] as $sort) {
        $forward = array_column(kcmc_team_sort_tasks($ties, $sort, '2026-10-15'), 'id');
        $reverse = array_column(kcmc_team_sort_tasks(array_reverse($ties), $sort, '2026-10-15'), 'id');
        ok($forward === $reverse && count($forward) === 2, 'Sort ' . $sort . ' has deterministic ID tie breaking');
    }

    $taskForSort = static function(string $letter, array $changes = []) use ($raceA): array {
        return array_replace($raceA, ['id' => 'teamtask_' . str_repeat($letter, 24), 'status' => 'open',
            'blocked' => false, 'priority' => 'normal', 'due_date' => '', 'created_at' => 100], $changes);
    };
    $sortIds = static fn(array $tasks, string $sort): array => array_column(kcmc_team_sort_tasks($tasks, $sort, '2026-10-15'), 'id');
    $ordered = [$taskForSort('a', ['blocked' => true, 'due_date' => '2026-10-14']),
        $taskForSort('b', ['blocked' => true, 'due_date' => '2026-10-15']),
        $taskForSort('c', ['blocked' => true, 'due_date' => '2026-10-16']),
        $taskForSort('d', ['blocked' => true]),
        $taskForSort('e', ['due_date' => '2026-10-13', 'priority' => 'high']),
        $taskForSort('f', ['status' => 'done', 'blocked' => true, 'due_date' => '2026-10-12'])];
    ok($sortIds(array_reverse($ordered), 'smart') === array_column($ordered, 'id'), 'Smart sort places open work first, then blocked work and overdue/today/future/undated buckets');
    $priorityBucket = [$taskForSort('a', ['due_date' => '2026-10-14', 'priority' => 'high']),
        $taskForSort('b', ['due_date' => '2026-10-13', 'priority' => 'normal']),
        $taskForSort('c', ['due_date' => '2026-10-12', 'priority' => 'low'])];
    ok($sortIds(array_reverse($priorityBucket), 'smart') === array_column($priorityBucket, 'id'), 'Smart sort prioritizes urgency inside the same due-date bucket');
    $dates = [$taskForSort('a', ['due_date' => '2026-10-13']), $taskForSort('b', ['due_date' => '2026-10-14'])];
    ok($sortIds(array_reverse($dates), 'smart') === array_column($dates, 'id'), 'Smart equal-priority bucket sorts by actual due date');
    $created = [$taskForSort('b', ['created_at' => 100]), $taskForSort('a', ['created_at' => 200])];
    ok($sortIds(array_reverse($created), 'smart') === array_column($created, 'id'), 'Smart equal due dates and priorities sort by creation time before ID');
    $dueFirst = [$taskForSort('a', ['due_date' => '2026-10-14', 'priority' => 'low']),
        $taskForSort('b', ['due_date' => '2026-10-15', 'priority' => 'high', 'blocked' => true]),
        $taskForSort('c', ['due_date' => '2026-10-16']), $taskForSort('d'),
        $taskForSort('e', ['status' => 'done', 'due_date' => '2026-10-12'])];
    ok($sortIds(array_reverse($dueFirst), 'due') === array_column($dueFirst, 'id'), 'Due sort prioritizes dated open work over blocked or high-priority later work');
    $priorityFirst = [$taskForSort('a', ['priority' => 'high']),
        $taskForSort('b', ['priority' => 'normal', 'blocked' => true, 'due_date' => '2026-10-13']),
        $taskForSort('c', ['priority' => 'low', 'due_date' => '2026-10-12']),
        $taskForSort('d', ['status' => 'done', 'priority' => 'high'])];
    ok($sortIds(array_reverse($priorityFirst), 'priority') === array_column($priorityFirst, 'id'), 'Priority sort puts high urgency open work first and completed tasks last');

    $healthy = file_get_contents($path);
    $invalidNested = json_decode($healthy, true, 512, JSON_THROW_ON_ERROR);
    $invalidNested['tasks'][$raceA['id']]['revision'] = 'not-an-integer';
    $invalidDate = json_decode($healthy, true, 512, JSON_THROW_ON_ERROR);
    $invalidDate['tasks'][$raceA['id']]['due_date'] = '2026-02-30';
    $invalidParent = json_decode($healthy, true, 512, JSON_THROW_ON_ERROR);
    $invalidParent['comments'][$reply['id']]['parent_id'] = $publicationComment['id'];
    $invalidPreference = json_decode($healthy, true, 512, JSON_THROW_ON_ERROR);
    $invalidPreference['preferences']['alice']['view'] = 'administrator';
    foreach (['{broken', 'null', '{"version":1,"revision":0,"tasks":"wrong","comments":[],"preferences":[],"nonces":[]}',
        json_encode($invalidNested, JSON_THROW_ON_ERROR), json_encode($invalidDate, JSON_THROW_ON_ERROR),
        json_encode($invalidParent, JSON_THROW_ON_ERROR), json_encode($invalidPreference, JSON_THROW_ON_ERROR)] as $corrupt) {
        file_put_contents($path, $corrupt);
        same_bytes(fn() => kcmc_team_read(), [503], 'Corrupt JSON or schema refuses reads');
        same_bytes(fn() => mutate($owner, 'create', ['task' => task_input()]), [503], 'Corrupt JSON or schema refuses writes');
        file_put_contents($path, $healthy);
    }
    $target = $private . '/protected-target';
    file_put_contents($target, 'SYMLINK TARGET MUST BE PRESERVED'); chmod($target, 0640);
    unlink($path); symlink($target, $path);
    same_bytes(fn() => kcmc_team_read(), [503], 'Symlink storage is rejected');
    same_bytes(fn() => create_task(), [503], 'A write cannot replace symlink storage');
    ok(is_link($path) && file_get_contents($target) === 'SYMLINK TARGET MUST BE PRESERVED', 'Symlink refusal preserves link and target bytes');
    unlink($path); file_put_contents($path, $healthy); chmod($path, 0640);
    $alias = $private . '/hardlink-alias'; link($path, $alias);
    same_bytes(fn() => kcmc_team_read(), [503], 'Multiply linked workspace storage is rejected');
    same_bytes(fn() => create_task(), [503], 'A write cannot replace multiply linked storage');
    ok(file_get_contents($alias) === $healthy, 'Hardlink refusal preserves target bytes');
    unlink($alias);
    chmod($path, 0644);
    same_bytes(fn() => kcmc_team_read(), [503], 'World-readable workspace storage is rejected');
    same_bytes(fn() => create_task(), [503], 'Unsafe file mode does not get silently repaired by a write');
    chmod($path, 0640);

    // Inject a native temporary-file failure after authorization and validation,
    // without replacing or editing runtime functions. The old JSON must survive.
    if (!function_exists('posix_geteuid') || posix_geteuid() !== 0) {
        try {
            same_bytes(static fn() => kcmc_team_transaction(static function(array &$state) use ($private, $raceA): array {
                $state['tasks'][$raceA['id']]['title'] = 'This failed write must never be stored';
                chmod($private, 0500);
                return [];
            }), [503], 'Native temporary-file write failure refuses the update');
        } finally { chmod($private, 0700); }
        ok(glob($path . '.tmp-*') === [], 'Failed temporary writes leave no staged payload behind');
    }
    foreach ($untouched as $name => $original) ok(file_get_contents($private . '/' . $name) === $original, 'Unrelated ' . $name . ' bytes remain unchanged');
    echo $checks . " team workspace contract checks passed.\n";
} finally {
    clear_fixture($private);
}
