<?php
declare(strict_types=1);

const KCMC_EVENT_RSVPS = KCMC_PRIVATE_DATA . '/event-rsvps.json';
const KCMC_EVENT_RSVP_RATE = KCMC_PRIVATE_DATA . '/event-rsvp-rate.json';
const KCMC_EVENT_RSVP_RATE_WINDOW = 600;
const KCMC_EVENT_RSVP_RATE_LIMIT = 8;
const KCMC_EVENT_RSVP_DUPLICATE_WINDOW = 3600;

/** @return array{ok:bool,error:string,value:array<string,string>} */
function kcmc_event_rsvp_validate_input(array $input): array {
    $event = trim((string)($input['event'] ?? ''));
    $eventDate = trim((string)($input['event_date'] ?? ''));
    $name = trim((string)($input['name'] ?? ''));
    $email = kcmc_normalize_email((string)($input['email'] ?? ''));
    $note = trim((string)($input['message'] ?? ''));

    if (kcmc_text_length($event) < 2 || kcmc_text_length($event) > 120) {
        return ['ok' => false, 'error' => 'Choose an event before sending your RSVP.', 'value' => []];
    }
    if (!kcmc_valid_event_date($eventDate)) {
        return ['ok' => false, 'error' => 'Choose a current event before sending your RSVP.', 'value' => []];
    }
    if (kcmc_text_length($name) < 2 || kcmc_text_length($name) > 100) {
        return ['ok' => false, 'error' => 'Enter your name.', 'value' => []];
    }
    if (!kcmc_valid_email($email) || kcmc_text_length($email) > 254) {
        return ['ok' => false, 'error' => 'Enter a valid email address.', 'value' => []];
    }
    if (kcmc_text_length($note) > 1000) {
        return ['ok' => false, 'error' => 'Keep the RSVP note to 1,000 characters or fewer.', 'value' => []];
    }

    return [
        'ok' => true,
        'error' => '',
        'value' => [
            'event' => $event,
            'event_date' => $eventDate,
            'name' => $name,
            'email' => $email,
            'message' => $note,
        ],
    ];
}

function kcmc_event_rsvp_event_is_open(array $events, string $title, string $date): bool {
    $needle = function_exists('mb_strtolower') ? mb_strtolower(trim($title), 'UTF-8') : strtolower(trim($title));
    foreach (kcmc_active_items($events) as $event) {
        if (!is_array($event)) continue;
        if (array_key_exists('rsvp', $event) && $event['rsvp'] === false) continue;
        $candidate = trim((string)($event['title'] ?? ''));
        $candidate = function_exists('mb_strtolower') ? mb_strtolower($candidate, 'UTF-8') : strtolower($candidate);
        if ($candidate === $needle && trim((string)($event['date'] ?? '')) === $date) return true;
    }
    return false;
}

function kcmc_event_rsvp_client_hash(string $remoteAddress): string {
    $remoteAddress = trim($remoteAddress) ?: 'unknown';
    return hash('sha256', 'kcmc-event-rsvp|' . $remoteAddress);
}

/** @return array{allowed:bool,retry_after:int,count:int} */
function kcmc_event_rsvp_consume_rate(string $clientHash, ?int $now = null): array {
    $now ??= time();
    return kcmc_update_json_store(KCMC_EVENT_RSVP_RATE, ['version' => 1, 'clients' => []], function (array &$state) use ($clientHash, $now): array {
        if (!isset($state['clients']) || !is_array($state['clients'])) $state['clients'] = [];
        $cutoff = $now - KCMC_EVENT_RSVP_RATE_WINDOW;
        foreach ($state['clients'] as $hash => $timestamps) {
            if (!is_array($timestamps)) { unset($state['clients'][$hash]); continue; }
            $timestamps = array_values(array_filter($timestamps, static fn($stamp): bool => is_int($stamp) && $stamp > $cutoff));
            if ($timestamps) $state['clients'][$hash] = $timestamps;
            else unset($state['clients'][$hash]);
        }
        $current = is_array($state['clients'][$clientHash] ?? null) ? $state['clients'][$clientHash] : [];
        if (count($current) >= KCMC_EVENT_RSVP_RATE_LIMIT) {
            $oldest = min($current);
            return [
                'allowed' => false,
                'retry_after' => max(1, KCMC_EVENT_RSVP_RATE_WINDOW - ($now - $oldest)),
                'count' => count($current),
            ];
        }
        $current[] = $now;
        $state['clients'][$clientHash] = $current;
        return ['allowed' => true, 'retry_after' => 0, 'count' => count($current)];
    });
}

/**
 * @return array{stored:bool,duplicate:bool,id:string}
 */
function kcmc_event_rsvp_store(array $value, ?int $now = null): array {
    $now ??= time();
    return kcmc_update_json_store(KCMC_EVENT_RSVPS, ['version' => 1, 'rsvps' => []], function (array &$state) use ($value, $now): array {
        if (!isset($state['rsvps']) || !is_array($state['rsvps'])) $state['rsvps'] = [];
        $cutoff = $now - KCMC_EVENT_RSVP_DUPLICATE_WINDOW;
        foreach ($state['rsvps'] as $stored) {
            if (!is_array($stored)) continue;
            $submitted = strtotime((string)($stored['submitted_at'] ?? ''));
            if ($submitted === false || $submitted < $cutoff) continue;
            if (
                hash_equals((string)($stored['email'] ?? ''), (string)$value['email']) &&
                (string)($stored['event_date'] ?? '') === (string)$value['event_date'] &&
                strcasecmp(trim((string)($stored['event'] ?? '')), trim((string)$value['event'])) === 0
            ) {
                return ['stored' => false, 'duplicate' => true, 'id' => (string)($stored['id'] ?? '')];
            }
        }

        $id = kcmc_random_id('rsvp');
        $state['rsvps'][] = [
            'id' => $id,
            'event' => (string)$value['event'],
            'event_date' => (string)$value['event_date'],
            'name' => (string)$value['name'],
            'email' => (string)$value['email'],
            'message' => (string)$value['message'],
            'submitted_at' => gmdate('c', $now),
        ];
        if (count($state['rsvps']) > 5000) $state['rsvps'] = array_slice($state['rsvps'], -5000);
        return ['stored' => true, 'duplicate' => false, 'id' => $id];
    });
}

function kcmc_event_rsvp_recent(int $limit = 200): array {
    $limit = max(1, min(500, $limit));
    $state = kcmc_read_json_store(KCMC_EVENT_RSVPS, ['version' => 1, 'rsvps' => []]);
    $rows = array_values(array_filter($state['rsvps'] ?? [], 'is_array'));
    usort($rows, static fn(array $a, array $b): int => strcmp((string)($b['submitted_at'] ?? ''), (string)($a['submitted_at'] ?? '')));
    return array_slice($rows, 0, $limit);
}
