<?php
declare(strict_types=1);

// Real service and JSON-store primitive, using synthetic private data only.
$library = $argv[1] ?? dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated/lib/timeclock.php';
$selected = $argv[2] ?? 'all';
$private = sys_get_temp_dir() . '/kcmc-timeclock-review-' . bin2hex(random_bytes(8));
putenv('KCMC_PRIVATE_DATA_DIR=' . $private);
require $library;

function tc_assert(bool $ok, string $message): void {
    if (!$ok) throw new RuntimeException($message);
}

function tc_seed(string $subject): array {
    return [
        'version' => 1,
        'entries' => [
            ['id'=>'target-shift','user_id'=>$subject,'work_date'=>'2026-09-30','status'=>'submitted',
             'clock_in_at'=>'2026-09-30T13:00:00+00:00','clock_out_at'=>'2026-09-30T15:00:00+00:00',
             'net_minutes'=>120,'description'=>'Synthetic completed work','category'=>'Other',
             'corrections'=>[['id'=>'historic-correction','reason'=>'Preserve original evidence',
                              'before'=>['net_minutes'=>100],'after'=>['net_minutes'=>120]]]],
            ['id'=>'outside-period','user_id'=>$subject,'work_date'=>'2026-08-30','status'=>'completed',
             'net_minutes'=>90,'description'=>'Earlier period evidence'],
            ['id'=>'other-employee','user_id'=>'different-employee','work_date'=>'2026-09-30',
             'status'=>'submitted','net_minutes'=>45,'description'=>'Unrelated employee evidence'],
        ],
        'periods' => [
            ['user_id'=>$subject,'start'=>'2026-09-23','end'=>'2026-10-22','status'=>'submitted',
             'submitted_at'=>'2026-10-13T12:00:00+00:00','approved_at'=>null,'approved_by'=>null,
             'returned_at'=>null,'return_reason'=>null,'legacy_metadata'=>['keep'=>'historic period']],
            ['user_id'=>'different-employee','start'=>'2026-09-23','end'=>'2026-10-22',
             'status'=>'submitted','legacy_metadata'=>['keep'=>'unrelated period']],
        ],
        'adjustments' => [['id'=>'historic-adjustment','entry_id'=>'target-shift',
                          'previous_net_minutes'=>100,'new_net_minutes'=>120,'reason'=>'Historic adjustment']],
        'correction_requests' => [['id'=>'historic-request','entry_id'=>'target-shift',
                                  'user_id'=>$subject,'status'=>'applied','reason'=>'Historic request']],
        'legacy_store_field' => ['keep'=>'unmodified store evidence'],
    ];
}

function tc_write_seed(array $seed): string {
    if (!is_dir(KCMC_PRIVATE_DATA)) mkdir(KCMC_PRIVATE_DATA, 0700, true);
    if (is_file(KCMC_TIMECLOCK . '.lock')) unlink(KCMC_TIMECLOCK . '.lock');
    $raw = "\n  " . json_encode($seed, JSON_UNESCAPED_SLASHES) . "\n\n";
    file_put_contents(KCMC_TIMECLOCK, $raw);
    return $raw;
}

function tc_self_denied(string $action): void {
    try {
        kcmc_timeclock_review_period('synthetic-owner', '2026-09-23', '2026-10-22',
                                    'synthetic-owner', $action, 'Please correct these recorded hours.');
    } catch (RuntimeException $error) {
        tc_assert($error->getMessage() === 'A reviewer cannot approve or return their own time card.',
                  'Self-' . $action . ' did not fail at the service identity boundary.');
        return;
    }
    throw new RuntimeException('Self-' . $action . ' was accepted by the service.');
}

function tc_run_self(string $action): void {
    $seed = tc_seed('synthetic-owner');
    $raw = tc_write_seed($seed);
    clearstatcache(true, KCMC_TIMECLOCK);
    $before = stat(KCMC_TIMECLOCK);
    tc_self_denied($action);
    clearstatcache(true, KCMC_TIMECLOCK);
    $after = stat(KCMC_TIMECLOCK);
    tc_assert(file_get_contents(KCMC_TIMECLOCK) === $raw, 'Denied self-review rewrote stored bytes/history.');
    tc_assert($before['ino'] === $after['ino'] && $before['mtime'] === $after['mtime'],
              'Denied self-review replaced or modified the stored file.');
    tc_assert(!file_exists(KCMC_TIMECLOCK . '.lock'), 'Denied self-review touched the store lock.');
    // The identity check must precede even lock creation or private-directory setup.
    unlink(KCMC_TIMECLOCK);
    rmdir(KCMC_PRIVATE_DATA);
    tc_self_denied($action);
    tc_assert(!file_exists(KCMC_PRIVATE_DATA), 'Denied self-review created private storage.');
}

function tc_run_allowed(string $action): void {
    $seed = tc_seed('staff-employee');
    tc_write_seed($seed);
    $record = kcmc_timeclock_review_period('staff-employee', '2026-09-23', '2026-10-22',
                                          'synthetic-owner', $action, '  Please correct these recorded hours.  ');
    $stored = json_decode((string)file_get_contents(KCMC_TIMECLOCK), true, 512, JSON_THROW_ON_ERROR);
    $status = $action === 'approve' ? 'approved' : 'returned';
    tc_assert($record['status'] === $status && $stored['periods'][0]['status'] === $status,
              'A distinct reviewer could not ' . $action . ' the submitted period.');
    tc_assert($stored['entries'][0]['status'] === ($action === 'approve' ? 'approved' : 'completed'),
              'The reviewed shift did not receive the intended status.');
    if ($action === 'approve') {
        tc_assert($record['approved_by'] === 'synthetic-owner' && is_string($record['approved_at']) &&
                  $record['approved_at'] !== '', 'Approval attribution or time is missing.');
    } else {
        tc_assert($record['return_reason'] === 'Please correct these recorded hours.' &&
                  is_string($record['returned_at']) && $record['returned_at'] !== '',
                  'Return reason or timestamp is missing.');
        tc_assert($record['approved_by'] === $seed['periods'][0]['approved_by'] &&
                  $record['approved_at'] === $seed['periods'][0]['approved_at'],
                  'Returning another employee card changed existing approval metadata.');
    }
    $entryBefore = $seed['entries'][0];
    $entryAfter = $stored['entries'][0];
    unset($entryBefore['status'], $entryAfter['status']);
    tc_assert($entryAfter === $entryBefore, 'Review changed shift evidence beyond its status.');
    tc_assert($stored['entries'][1] === $seed['entries'][1] && $stored['entries'][2] === $seed['entries'][2] &&
              $stored['periods'][1] === $seed['periods'][1], 'Unrelated employee or period evidence changed.');
    tc_assert($stored['entries'][0]['corrections'] === $seed['entries'][0]['corrections'] &&
              $stored['entries'][0]['net_minutes'] === $seed['entries'][0]['net_minutes'] &&
              $stored['periods'][0]['legacy_metadata'] === $seed['periods'][0]['legacy_metadata'] &&
              $stored['adjustments'] === $seed['adjustments'] &&
              $stored['correction_requests'] === $seed['correction_requests'] &&
              $stored['legacy_store_field'] === $seed['legacy_store_field'],
              'Review discarded existing correction/history data.');
}

function tc_run_invalid_entries(string $shape): void {
    foreach (['approve','return'] as $action) {
        $seed = tc_seed('staff-employee');
        if ($shape === 'missing') unset($seed['entries']);
        else $seed['entries'] = 'Preserve this malformed original evidence for manual review';
        $raw = tc_write_seed($seed);
        clearstatcache(true, KCMC_TIMECLOCK);
        $before = stat(KCMC_TIMECLOCK);
        $denied = false;
        try {
            kcmc_timeclock_review_period('staff-employee', '2026-09-23', '2026-10-22',
                                        'synthetic-owner', $action, 'Please correct these recorded hours.');
        } catch (RuntimeException $error) {
            tc_assert($error->getMessage() === 'Stored time entries require review.',
                      'Malformed entry storage failed with an unexpected error.');
            $denied = true;
        }
        tc_assert($denied, 'Review accepted ' . $shape . ' entry storage.');
        clearstatcache(true, KCMC_TIMECLOCK);
        $after = stat(KCMC_TIMECLOCK);
        tc_assert(file_get_contents(KCMC_TIMECLOCK) === $raw && $before['ino'] === $after['ino'] &&
                  $before['mtime'] === $after['mtime'],
                  'Refused review discarded or reformatted malformed entry evidence.');
    }
}

try {
    foreach (['self_approve','self_return','other_approve','other_return','missing_entries','malformed_entries'] as $case) {
        if ($selected !== 'all' && $selected !== $case) continue;
        [$subject, $action] = explode('_', $case, 2);
        if ($subject === 'self') tc_run_self($action);
        elseif ($subject === 'other') tc_run_allowed($action);
        else tc_run_invalid_entries($subject);
        echo $case . ": PASS\n";
    }
    tc_assert(in_array($selected, ['all','self_approve','self_return','other_approve','other_return','missing_entries','malformed_entries'], true),
              'Unknown selected test case.');
} finally {
    foreach (glob(KCMC_PRIVATE_DATA . '/*') ?: [] as $path) if (is_file($path)) unlink($path);
    if (is_dir(KCMC_PRIVATE_DATA)) rmdir(KCMC_PRIVATE_DATA);
}
