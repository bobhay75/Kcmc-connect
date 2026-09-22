<?php
declare(strict_types=1);

/**
 * Normalize and validate one administrator-created public event.
 * Returns a normalized event payload without assigning an ID.
 *
 * @return array{ok:bool,error:string,event:array<string,mixed>}
 */
function kcmc_validate_new_event(array $input): array {
    $title = trim((string)($input['title'] ?? ''));
    $date = trim((string)($input['date'] ?? ''));
    $time = trim((string)($input['time'] ?? ''));
    $endTime = trim((string)($input['end_time'] ?? ''));
    $location = trim((string)($input['location'] ?? ''));
    $description = trim((string)($input['description'] ?? ''));
    $status = (string)($input['status'] ?? 'hidden');
    $expires = trim((string)($input['expires'] ?? ''));
    $priorityRaw = trim((string)($input['priority'] ?? '50'));

    if (kcmc_text_length($title) < 2 || kcmc_text_length($title) > 120) {
        return ['ok' => false, 'error' => 'Event title must be between 2 and 120 characters.', 'event' => []];
    }
    if (!kcmc_valid_event_date($date)) {
        return ['ok' => false, 'error' => 'Enter a valid event date.', 'event' => []];
    }
    if ($time !== '' && kcmc_event_time_minutes($time) === null) {
        return ['ok' => false, 'error' => 'Event start time must use a format such as 4:30 PM.', 'event' => []];
    }
    if ($endTime !== '' && kcmc_event_time_minutes($endTime) === null) {
        return ['ok' => false, 'error' => 'Event end time must use a format such as 6:30 PM.', 'event' => []];
    }
    if ($endTime !== '' && $time === '') {
        return ['ok' => false, 'error' => 'Add a start time before adding an end time.', 'event' => []];
    }
    $startMinutes = $time === '' ? null : kcmc_event_time_minutes($time);
    $endMinutes = $endTime === '' ? null : kcmc_event_time_minutes($endTime);
    if ($startMinutes !== null && $endMinutes !== null && $endMinutes <= $startMinutes) {
        return ['ok' => false, 'error' => 'Event end time must be later than the start time.', 'event' => []];
    }
    if (kcmc_text_length($location) > 180) {
        return ['ok' => false, 'error' => 'Event location must be 180 characters or fewer.', 'event' => []];
    }
    if (kcmc_text_length($description) > 2000) {
        return ['ok' => false, 'error' => 'Event description must be 2,000 characters or fewer.', 'event' => []];
    }
    if (!preg_match('/\A\d{1,3}\z/', $priorityRaw)) {
        return ['ok' => false, 'error' => 'Event priority must be a whole number from 0 to 100.', 'event' => []];
    }
    $priority = (int)$priorityRaw;
    if ($priority < 0 || $priority > 100) {
        return ['ok' => false, 'error' => 'Event priority must be from 0 to 100.', 'event' => []];
    }
    if (!in_array($status, ['published', 'hidden'], true)) {
        return ['ok' => false, 'error' => 'Choose Published or Hidden for event status.', 'event' => []];
    }

    $expiresAt = '';
    if ($expires !== '') {
        if (!kcmc_valid_event_date($expires)) {
            return ['ok' => false, 'error' => 'Enter a valid event expiration date.', 'event' => []];
        }
        if ($expires < $date) {
            return ['ok' => false, 'error' => 'Event expiration cannot be before the event date.', 'event' => []];
        }
        $expiresAt = kcmc_local_datetime_iso($expires, true);
        if ($expiresAt === '') {
            return ['ok' => false, 'error' => 'Event expiration could not be normalized.', 'event' => []];
        }
    }

    return [
        'ok' => true,
        'error' => '',
        'event' => [
            'title' => $title,
            'date' => $date,
            'time' => $time,
            'end_time' => $endTime,
            'location' => $location,
            'description' => $description,
            'priority' => $priority,
            'status' => $status,
            'expires_at' => $expiresAt,
        ],
    ];
}

function kcmc_event_duplicate_exists(array $events, string $title, string $date): bool {
    $needleTitle = function_exists('mb_strtolower') ? mb_strtolower(trim($title), 'UTF-8') : strtolower(trim($title));
    foreach ($events as $event) {
        if (!is_array($event)) continue;
        $candidateTitle = trim((string)($event['title'] ?? ''));
        $candidateTitle = function_exists('mb_strtolower') ? mb_strtolower($candidateTitle, 'UTF-8') : strtolower($candidateTitle);
        if ($candidateTitle === $needleTitle && trim((string)($event['date'] ?? '')) === $date) return true;
    }
    return false;
}
