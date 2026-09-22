<?php
declare(strict_types=1);

function kcmc_create_event_candidate(array $input, array $existingEvents = []): array {
    $title = trim((string)($input['title'] ?? ''));
    $date = trim((string)($input['date'] ?? ''));
    $time = trim((string)($input['time'] ?? ''));
    $endTime = trim((string)($input['end_time'] ?? ''));
    $location = trim((string)($input['location'] ?? 'KCMC'));
    $description = trim((string)($input['description'] ?? ''));
    $status = (string)($input['status'] ?? 'published');
    $expires = trim((string)($input['expires'] ?? ''));
    $priorityRaw = trim((string)($input['priority'] ?? '50'));

    if (kcmc_text_length($title) < 2 || kcmc_text_length($title) > 160) {
        return ['ok' => false, 'error' => 'Event title must be between 2 and 160 characters.', 'event' => null];
    }
    if (!kcmc_valid_event_date($date)) {
        return ['ok' => false, 'error' => 'Enter a valid event date.', 'event' => null];
    }
    if ($time !== '' && kcmc_event_time_minutes($time) === null) {
        return ['ok' => false, 'error' => 'Start time must use a format such as 4:30 PM.', 'event' => null];
    }
    if ($endTime !== '' && kcmc_event_time_minutes($endTime) === null) {
        return ['ok' => false, 'error' => 'End time must use a format such as 6:30 PM.', 'event' => null];
    }
    if ($endTime !== '' && $time === '') {
        return ['ok' => false, 'error' => 'Enter a start time when an end time is provided.', 'event' => null];
    }
    if ($time !== '' && $endTime !== '' && kcmc_event_time_minutes($endTime) <= kcmc_event_time_minutes($time)) {
        return ['ok' => false, 'error' => 'Event end time must be later than the start time.', 'event' => null];
    }
    if (kcmc_text_length($location) > 240) {
        return ['ok' => false, 'error' => 'Event location is too long.', 'event' => null];
    }
    if (kcmc_text_length($description) > 2000) {
        return ['ok' => false, 'error' => 'Event description is too long.', 'event' => null];
    }
    if (!in_array($status, ['published', 'hidden'], true)) {
        return ['ok' => false, 'error' => 'Choose a valid event status.', 'event' => null];
    }
    if (!preg_match('/\A\d{1,3}\z/', $priorityRaw)) {
        return ['ok' => false, 'error' => 'Priority must be a whole number from 0 to 100.', 'event' => null];
    }
    $priority = (int)$priorityRaw;
    if ($priority < 0 || $priority > 100) {
        return ['ok' => false, 'error' => 'Priority must be a whole number from 0 to 100.', 'event' => null];
    }
    if ($expires !== '' && !kcmc_valid_event_date($expires)) {
        return ['ok' => false, 'error' => 'Enter a valid expiry date or leave it blank.', 'event' => null];
    }

    $duplicateTitle = strtolower($title);
    foreach ($existingEvents as $existing) {
        if (!is_array($existing)) continue;
        if (strtolower(trim((string)($existing['title'] ?? ''))) === $duplicateTitle && trim((string)($existing['date'] ?? '')) === $date) {
            return ['ok' => false, 'error' => 'An event with this title and date already exists.', 'event' => null];
        }
    }

    $event = [
        'id' => kcmc_random_id('event'),
        'title' => $title,
        'date' => $date,
        'time' => $time,
        'end_time' => $endTime,
        'location' => $location === '' ? 'KCMC' : $location,
        'description' => $description,
        'label' => 'Church event',
        'rsvp' => false,
        'priority' => $priority,
        'status' => $status,
        'expires_at' => $expires === '' ? '' : kcmc_local_datetime_iso($expires, true),
    ];

    return ['ok' => true, 'error' => '', 'event' => $event];
}
