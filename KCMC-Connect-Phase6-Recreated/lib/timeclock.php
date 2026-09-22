<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

define('KCMC_TIMECLOCK', KCMC_PRIVATE_DATA . '/timeclock.json');

function kcmc_timeclock_default_store(): array {
    return ['version' => 1, 'entries' => [], 'periods' => [], 'correction_requests' => []];
}

function kcmc_timeclock_categories(): array {
    return ['Office / Administration','Maintenance / Facilities','Media / Worship','KCMC Connect / IT','Events / Outreach','Other'];
}

function kcmc_timeclock_period_start_day(): int {
    $cfg = kcmc_config();
    return max(1, min(28, (int)($cfg['timeclock_period_start_day'] ?? 23)));
}

function kcmc_timeclock_now(): string {
    return gmdate('c');
}

function kcmc_timeclock_store(): array {
    return kcmc_read_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store());
}

function kcmc_timeclock_local_date(string $iso): string {
    $d = new DateTimeImmutable($iso);
    return $d->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('Y-m-d');
}

function kcmc_timeclock_local_input_to_iso(string $value): string {
    $value = trim($value);
    $tz = new DateTimeZone(KCMC_LOCAL_TIMEZONE);
    $d = DateTimeImmutable::createFromFormat('!Y-m-d\TH:i', $value, $tz);
    if ($d === false || $d->format('Y-m-d\TH:i') !== $value) return '';
    return $d->setTimezone(new DateTimeZone('UTC'))->format(DateTimeInterface::ATOM);
}

function kcmc_timeclock_minutes(string $start, string $end): int {
    $a = strtotime($start);
    $b = strtotime($end);
    return ($a === false || $b === false) ? 0 : max(0, (int)floor(($b - $a) / 60));
}

function kcmc_timeclock_break_minutes(array $entry): int {
    if (array_key_exists('corrected_break_minutes', $entry)) {
        return max(0, (int)$entry['corrected_break_minutes']);
    }
    $minutes = 0;
    foreach (($entry['breaks'] ?? []) as $break) {
        if (is_array($break) && !empty($break['start_at']) && !empty($break['end_at'])) {
            $minutes += kcmc_timeclock_minutes((string)$break['start_at'], (string)$break['end_at']);
        }
    }
    return $minutes;
}

function kcmc_timeclock_net_minutes(array $entry): int {
    if (empty($entry['clock_out_at'])) return 0;
    $gross = kcmc_timeclock_minutes((string)$entry['clock_in_at'], (string)$entry['clock_out_at']);
    return max(0, $gross - kcmc_timeclock_break_minutes($entry));
}

function kcmc_timeclock_period(?DateTimeImmutable $date = null): array {
    $tz = new DateTimeZone(KCMC_LOCAL_TIMEZONE);
    $d = ($date ?? new DateTimeImmutable('now', $tz))->setTimezone($tz);
    $startDay = kcmc_timeclock_period_start_day();
    $day = (int)$d->format('j');
    if ($day >= $startDay) {
        $start = $d->setDate((int)$d->format('Y'), (int)$d->format('n'), $startDay);
    } else {
        $previous = $d->modify('-1 month');
        $start = $previous->setDate((int)$previous->format('Y'), (int)$previous->format('n'), $startDay);
    }
    $end = $start->modify('+1 month -1 day');
    return [$start->format('Y-m-d'), $end->format('Y-m-d')];
}

function kcmc_timeclock_entries_for(string $userId): array {
    return array_values(array_filter(
        kcmc_timeclock_store()['entries'] ?? [],
        fn($entry) => is_array($entry) && ($entry['user_id'] ?? '') === $userId
    ));
}

function kcmc_timeclock_open_entry(string $userId): ?array {
    foreach (array_reverse(kcmc_timeclock_entries_for($userId)) as $entry) {
        if (($entry['status'] ?? '') === 'open') return $entry;
    }
    return null;
}

function kcmc_timeclock_period_entries(string $userId, string $start, string $end): array {
    return array_values(array_filter(
        kcmc_timeclock_entries_for($userId),
        fn($entry) => ($entry['work_date'] ?? '') >= $start && ($entry['work_date'] ?? '') <= $end
    ));
}

function kcmc_timeclock_period_record(string $userId, string $start, string $end): ?array {
    foreach (kcmc_timeclock_store()['periods'] ?? [] as $period) {
        if (is_array($period) && ($period['user_id'] ?? '') === $userId && ($period['start'] ?? '') === $start && ($period['end'] ?? '') === $end) {
            return $period;
        }
    }
    return null;
}

function kcmc_timeclock_period_total(string $userId, string $start, string $end): int {
    return array_sum(array_map(
        fn($entry) => (int)($entry['net_minutes'] ?? 0),
        kcmc_timeclock_period_entries($userId, $start, $end)
    ));
}

function kcmc_timeclock_entry_correction_count(array $entry): int {
    return count(array_filter($entry['corrections'] ?? [], 'is_array'));
}

function kcmc_timeclock_mutate(string $userId, string $action, array $input = []): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($userId, $action, $input): array {
        $state['entries'] = is_array($state['entries'] ?? null) ? $state['entries'] : [];
        $state['periods'] = is_array($state['periods'] ?? null) ? $state['periods'] : [];
        $now = kcmc_timeclock_now();
        $today = kcmc_timeclock_local_date($now);
        [$periodStart, $periodEnd] = kcmc_timeclock_period(new DateTimeImmutable($now));

        foreach ($state['periods'] as $period) {
            if (is_array($period) && ($period['user_id'] ?? '') === $userId && ($period['start'] ?? '') === $periodStart && ($period['end'] ?? '') === $periodEnd && in_array((string)($period['status'] ?? ''), ['submitted','approved'], true)) {
                throw new RuntimeException('This pay period is locked while it is awaiting review or approved.');
            }
        }

        $entryIndex = null;
        foreach ($state['entries'] as $index => $entry) {
            if (is_array($entry) && ($entry['user_id'] ?? '') === $userId && ($entry['status'] ?? '') === 'open') $entryIndex = $index;
        }

        if ($action === 'clock_in') {
            if ($entryIndex !== null) throw new RuntimeException('You are already clocked in.');
            $entry = [
                'id' => kcmc_random_id('time'),
                'user_id' => $userId,
                'work_date' => $today,
                'clock_in_at' => $now,
                'clock_out_at' => null,
                'breaks' => [],
                'category' => '',
                'description' => '',
                'status' => 'open',
                'created_at' => $now,
                'updated_at' => $now,
                'net_minutes' => 0,
                'corrections' => [],
            ];
            $state['entries'][] = $entry;
            return $entry;
        }

        if ($entryIndex === null) throw new RuntimeException('No open shift.');
        $entry =& $state['entries'][$entryIndex];
        $openBreakIndex = null;
        foreach (($entry['breaks'] ?? []) as $index => $break) {
            if (is_array($break) && empty($break['end_at'])) $openBreakIndex = $index;
        }

        if ($action === 'break_start') {
            if ($openBreakIndex !== null) throw new RuntimeException('A break is already open.');
            $entry['breaks'][] = ['start_at' => $now, 'end_at' => null];
        } elseif ($action === 'break_end') {
            if ($openBreakIndex === null) throw new RuntimeException('No open break.');
            $entry['breaks'][$openBreakIndex]['end_at'] = $now;
        } elseif ($action === 'clock_out') {
            if ($openBreakIndex !== null) throw new RuntimeException('End the break before clocking out.');
            $category = trim((string)($input['category'] ?? ''));
            $description = trim((string)($input['description'] ?? ''));
            if (!in_array($category, kcmc_timeclock_categories(), true)) throw new RuntimeException('Choose a valid work category.');
            if ($description === '' || kcmc_text_length($description) > 1000) throw new RuntimeException('Enter a work description up to 1000 characters.');
            $entry['clock_out_at'] = $now;
            $entry['category'] = $category;
            $entry['description'] = $description;
            $entry['status'] = 'completed';
            $entry['net_minutes'] = kcmc_timeclock_net_minutes($entry);
        } else {
            throw new RuntimeException('Unsupported time-clock action.');
        }
        $entry['updated_at'] = $now;
        return $entry;
    });
}

function kcmc_timeclock_submit_period(string $userId, string $start, string $end): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($userId, $start, $end): array {
        $entryIndexes = [];
        foreach (($state['entries'] ?? []) as $index => &$entry) {
            if (!is_array($entry) || ($entry['user_id'] ?? '') !== $userId || ($entry['work_date'] ?? '') < $start || ($entry['work_date'] ?? '') > $end) continue;
            if (($entry['status'] ?? '') === 'open') throw new RuntimeException('Clock out before submitting this period.');
            if (trim((string)($entry['description'] ?? '')) === '' || !in_array((string)($entry['category'] ?? ''), kcmc_timeclock_categories(), true)) throw new RuntimeException('Every completed shift needs a category and description.');
            $entryIndexes[] = $index;
        }
        unset($entry);
        if (!$entryIndexes) throw new RuntimeException('There are no completed shifts in this pay period.');

        $now = kcmc_timeclock_now();
        $periodIndex = null;
        foreach (($state['periods'] ?? []) as $index => $period) {
            if (is_array($period) && ($period['user_id'] ?? '') === $userId && ($period['start'] ?? '') === $start && ($period['end'] ?? '') === $end) $periodIndex = $index;
        }
        if ($periodIndex !== null && in_array((string)($state['periods'][$periodIndex]['status'] ?? ''), ['submitted','approved'], true)) throw new RuntimeException('This pay period is already submitted or approved.');

        $record = [
            'user_id' => $userId,
            'start' => $start,
            'end' => $end,
            'status' => 'submitted',
            'submitted_at' => $now,
            'approved_at' => null,
            'approved_by' => null,
            'returned_at' => null,
            'return_reason' => null,
        ];
        if ($periodIndex === null) $state['periods'][] = $record;
        else $state['periods'][$periodIndex] = array_replace($state['periods'][$periodIndex], $record);
        foreach ($entryIndexes as $index) $state['entries'][$index]['status'] = 'submitted';
        return $record;
    });
}

function kcmc_timeclock_review_period(string $userId, string $start, string $end, string $reviewerId, string $action, string $reason = ''): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($userId, $start, $end, $reviewerId, $action, $reason): array {
        $periodIndex = null;
        foreach (($state['periods'] ?? []) as $index => $period) {
            if (is_array($period) && ($period['user_id'] ?? '') === $userId && ($period['start'] ?? '') === $start && ($period['end'] ?? '') === $end) $periodIndex = $index;
        }
        if ($periodIndex === null || ($state['periods'][$periodIndex]['status'] ?? '') !== 'submitted') throw new RuntimeException('That pay period is not awaiting review.');

        $now = kcmc_timeclock_now();
        if ($action === 'approve') {
            $state['periods'][$periodIndex]['status'] = 'approved';
            $state['periods'][$periodIndex]['approved_at'] = $now;
            $state['periods'][$periodIndex]['approved_by'] = $reviewerId;
        } elseif ($action === 'return') {
            $reason = trim($reason);
            if ($reason === '' || kcmc_text_length($reason) > 500) throw new RuntimeException('Enter a return reason up to 500 characters.');
            $state['periods'][$periodIndex]['status'] = 'returned';
            $state['periods'][$periodIndex]['returned_at'] = $now;
            $state['periods'][$periodIndex]['return_reason'] = $reason;
        } else {
            throw new RuntimeException('Unsupported review action.');
        }

        foreach (($state['entries'] ?? []) as &$entry) {
            if (is_array($entry) && ($entry['user_id'] ?? '') === $userId && ($entry['work_date'] ?? '') >= $start && ($entry['work_date'] ?? '') <= $end) {
                $entry['status'] = $state['periods'][$periodIndex]['status'] === 'approved' ? 'approved' : 'completed';
            }
        }
        unset($entry);
        return $state['periods'][$periodIndex];
    });
}

function kcmc_timeclock_request_correction(string $userId, string $entryId, string $reason): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($userId, $entryId, $reason): array {
        $reason = trim($reason);
        if (kcmc_text_length($reason) < 5 || kcmc_text_length($reason) > 500) throw new RuntimeException('Enter a correction reason between 5 and 500 characters.');

        $entry = null;
        foreach (($state['entries'] ?? []) as $stored) {
            if (is_array($stored) && ($stored['id'] ?? '') === $entryId && ($stored['user_id'] ?? '') === $userId) {
                $entry = $stored;
                break;
            }
        }
        if ($entry === null || ($entry['status'] ?? '') === 'open' || empty($entry['clock_out_at'])) throw new RuntimeException('That completed shift could not be found.');

        $state['correction_requests'] = is_array($state['correction_requests'] ?? null) ? $state['correction_requests'] : [];
        foreach ($state['correction_requests'] as $request) {
            if (is_array($request) && ($request['entry_id'] ?? '') === $entryId && ($request['user_id'] ?? '') === $userId && ($request['status'] ?? '') === 'pending') {
                throw new RuntimeException('A correction request for this shift is already pending.');
            }
        }

        $request = [
            'id' => kcmc_random_id('timefix'),
            'entry_id' => $entryId,
            'user_id' => $userId,
            'status' => 'pending',
            'reason' => $reason,
            'requested_at' => kcmc_timeclock_now(),
            'resolved_at' => null,
            'resolved_by' => null,
            'resolution_reason' => null,
        ];
        $state['correction_requests'][] = $request;
        return $request;
    });
}

function kcmc_timeclock_correction_requests_for(string $userId): array {
    $requests = array_values(array_filter(
        kcmc_timeclock_store()['correction_requests'] ?? [],
        fn($request) => is_array($request) && ($request['user_id'] ?? '') === $userId
    ));
    usort($requests, fn($a, $b) => strcmp((string)($b['requested_at'] ?? ''), (string)($a['requested_at'] ?? '')));
    return $requests;
}

function kcmc_timeclock_pending_corrections(): array {
    $requests = array_values(array_filter(
        kcmc_timeclock_store()['correction_requests'] ?? [],
        fn($request) => is_array($request) && ($request['status'] ?? '') === 'pending'
    ));
    usort($requests, fn($a, $b) => strcmp((string)($a['requested_at'] ?? ''), (string)($b['requested_at'] ?? '')));
    return $requests;
}

function kcmc_timeclock_apply_correction(string $requestId, string $reviewerId, array $input): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($requestId, $reviewerId, $input): array {
        $requestIndex = null;
        foreach (($state['correction_requests'] ?? []) as $index => $request) {
            if (is_array($request) && ($request['id'] ?? '') === $requestId) $requestIndex = $index;
        }
        if ($requestIndex === null || ($state['correction_requests'][$requestIndex]['status'] ?? '') !== 'pending') throw new RuntimeException('That correction request is no longer pending.');
        $request =& $state['correction_requests'][$requestIndex];

        $entryIndex = null;
        foreach (($state['entries'] ?? []) as $index => $entry) {
            if (is_array($entry) && ($entry['id'] ?? '') === ($request['entry_id'] ?? '') && ($entry['user_id'] ?? '') === ($request['user_id'] ?? '')) $entryIndex = $index;
        }
        if ($entryIndex === null) throw new RuntimeException('The requested time entry could not be found.');
        $entry =& $state['entries'][$entryIndex];
        if (($entry['status'] ?? '') === 'open') throw new RuntimeException('An open shift cannot be corrected through this workflow.');

        $clockIn = kcmc_timeclock_local_input_to_iso((string)($input['clock_in'] ?? ''));
        $clockOut = kcmc_timeclock_local_input_to_iso((string)($input['clock_out'] ?? ''));
        if ($clockIn === '' || $clockOut === '') throw new RuntimeException('Enter valid corrected clock-in and clock-out times.');
        $gross = kcmc_timeclock_minutes($clockIn, $clockOut);
        if ($gross < 1 || $gross > 1440) throw new RuntimeException('Corrected shift length must be between 1 minute and 24 hours.');

        $breakText = trim((string)($input['break_minutes'] ?? '0'));
        if (!preg_match('/\A\d{1,4}\z/', $breakText)) throw new RuntimeException('Corrected break minutes must be a whole number.');
        $breakMinutes = (int)$breakText;
        if ($breakMinutes > $gross) throw new RuntimeException('Corrected break time cannot exceed the shift length.');

        $category = trim((string)($input['category'] ?? ''));
        $description = trim((string)($input['description'] ?? ''));
        $correctionReason = trim((string)($input['correction_reason'] ?? ''));
        if (!in_array($category, kcmc_timeclock_categories(), true)) throw new RuntimeException('Choose a valid work category.');
        if ($description === '' || kcmc_text_length($description) > 1000) throw new RuntimeException('Enter a work description up to 1000 characters.');
        if (kcmc_text_length($correctionReason) < 5 || kcmc_text_length($correctionReason) > 500) throw new RuntimeException('Enter an administrator correction reason between 5 and 500 characters.');

        $before = [
            'work_date' => (string)($entry['work_date'] ?? ''),
            'clock_in_at' => (string)($entry['clock_in_at'] ?? ''),
            'clock_out_at' => (string)($entry['clock_out_at'] ?? ''),
            'break_minutes' => kcmc_timeclock_break_minutes($entry),
            'net_minutes' => (int)($entry['net_minutes'] ?? 0),
            'category' => (string)($entry['category'] ?? ''),
            'description' => (string)($entry['description'] ?? ''),
        ];

        $entry['clock_in_at'] = $clockIn;
        $entry['clock_out_at'] = $clockOut;
        $entry['work_date'] = kcmc_timeclock_local_date($clockIn);
        $entry['corrected_break_minutes'] = $breakMinutes;
        $entry['category'] = $category;
        $entry['description'] = $description;
        $entry['net_minutes'] = max(0, $gross - $breakMinutes);
        $entry['updated_at'] = kcmc_timeclock_now();

        $after = [
            'work_date' => (string)$entry['work_date'],
            'clock_in_at' => $clockIn,
            'clock_out_at' => $clockOut,
            'break_minutes' => $breakMinutes,
            'net_minutes' => (int)$entry['net_minutes'],
            'category' => $category,
            'description' => $description,
        ];
        $entry['corrections'] = is_array($entry['corrections'] ?? null) ? $entry['corrections'] : [];
        $entry['corrections'][] = [
            'id' => kcmc_random_id('correction'),
            'request_id' => $requestId,
            'actor_id' => $reviewerId,
            'reason' => $correctionReason,
            'at' => $entry['updated_at'],
            'before' => $before,
            'after' => $after,
        ];

        $request['status'] = 'applied';
        $request['resolved_at'] = $entry['updated_at'];
        $request['resolved_by'] = $reviewerId;
        $request['resolution_reason'] = $correctionReason;

        foreach (($state['periods'] ?? []) as &$period) {
            if (!is_array($period) || ($period['user_id'] ?? '') !== ($request['user_id'] ?? '')) continue;
            if (($before['work_date'] >= ($period['start'] ?? '') && $before['work_date'] <= ($period['end'] ?? '')) || ($after['work_date'] >= ($period['start'] ?? '') && $after['work_date'] <= ($period['end'] ?? ''))) {
                $period['correction_count'] = (int)($period['correction_count'] ?? 0) + 1;
                $period['corrected_at'] = $entry['updated_at'];
            }
        }
        unset($period);

        return ['request' => $request, 'entry' => $entry, 'before' => $before, 'after' => $after];
    });
}

function kcmc_timeclock_reject_correction(string $requestId, string $reviewerId, string $reason): array {
    return kcmc_update_json_store(KCMC_TIMECLOCK, kcmc_timeclock_default_store(), function (array &$state) use ($requestId, $reviewerId, $reason): array {
        $reason = trim($reason);
        if (kcmc_text_length($reason) < 5 || kcmc_text_length($reason) > 500) throw new RuntimeException('Enter a rejection reason between 5 and 500 characters.');
        foreach (($state['correction_requests'] ?? []) as &$request) {
            if (!is_array($request) || ($request['id'] ?? '') !== $requestId) continue;
            if (($request['status'] ?? '') !== 'pending') throw new RuntimeException('That correction request is no longer pending.');
            $request['status'] = 'rejected';
            $request['resolved_at'] = kcmc_timeclock_now();
            $request['resolved_by'] = $reviewerId;
            $request['resolution_reason'] = $reason;
            $result = $request;
            unset($request);
            return $result;
        }
        unset($request);
        throw new RuntimeException('Correction request not found.');
    });
}
