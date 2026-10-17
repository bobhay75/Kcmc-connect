<?php
declare(strict_types=1);

const KCMC_CONNECTION_INTAKE = KCMC_PRIVATE_DATA . '/connection-intake.json';
const KCMC_CONNECTION_RATE = KCMC_PRIVATE_DATA . '/connection-intake-rate.json';
const KCMC_CONNECTION_RATE_WINDOW = 600;
const KCMC_CONNECTION_RATE_LIMIT = 15;
const KCMC_CONNECTION_DUPLICATE_WINDOW = 1800;

function kcmc_connection_allowed_kinds(): array {
    return ['visit', 'serve', 'groups'];
}

function kcmc_connection_clean_text(mixed $value, int $max): string {
    $text = trim((string)$value);
    return kcmc_text_length($text) <= $max ? $text : '';
}

/** @return array{ok:bool,error:string,value:array<string,string>} */
function kcmc_connection_validate(string $kind, array $input): array {
    if (!in_array($kind, kcmc_connection_allowed_kinds(), true)) {
        return ['ok' => false, 'error' => 'That connection form is not available.', 'value' => []];
    }

    $email = kcmc_normalize_email((string)($input['email'] ?? ''));
    if (!kcmc_valid_email($email) || kcmc_text_length($email) > 254) {
        return ['ok' => false, 'error' => 'Enter a valid email address.', 'value' => []];
    }
    $message = trim((string)($input['message'] ?? ''));
    if (kcmc_text_length($message) > 1500) {
        return ['ok' => false, 'error' => 'Keep your note to 1,500 characters or fewer.', 'value' => []];
    }

    $value = [
        'kind' => $kind,
        'name' => '',
        'email' => $email,
        'phone' => '',
        'service' => '',
        'interest' => '',
        'message' => $message,
    ];

    if ($kind === 'visit') {
        $first = trim((string)($input['firstName'] ?? ''));
        $last = trim((string)($input['lastName'] ?? ''));
        if (kcmc_text_length($first) < 1 || kcmc_text_length($first) > 80 || kcmc_text_length($last) < 1 || kcmc_text_length($last) > 80) {
            return ['ok' => false, 'error' => 'Enter your first and last name.', 'value' => []];
        }
        $phone = trim((string)($input['phone'] ?? ''));
        if (kcmc_text_length($phone) > 40 || ($phone !== '' && !preg_match('/\A[0-9+(). xX#-]{7,40}\z/', $phone))) {
            return ['ok' => false, 'error' => 'Enter a valid phone number or leave it blank.', 'value' => []];
        }
        $services = [
            '8:00 AM — Front Porch Gospel',
            '9:15 AM — Traditional Worship',
            '10:30 AM — Contemporary Worship',
        ];
        $service = trim((string)($input['service'] ?? ''));
        if (!in_array($service, $services, true)) {
            return ['ok' => false, 'error' => 'Choose a Sunday service.', 'value' => []];
        }
        $value['name'] = $first . ' ' . $last;
        $value['phone'] = $phone;
        $value['service'] = $service;
    } else {
        $name = trim((string)($input['name'] ?? ''));
        if (kcmc_text_length($name) < 2 || kcmc_text_length($name) > 100) {
            return ['ok' => false, 'error' => 'Enter your name.', 'value' => []];
        }
        $serveInterests = [
            'Not sure — help me find a fit', 'Kids / Youth', 'Worship / Music',
            'Hospitality / Welcome', 'Care / Prayer', 'Community Outreach', 'Facilities / Practical Help',
        ];
        $groupInterests = [
            'Small group / Bible study', 'Kids / family connection', 'Youth', 'Care / support',
            'Men’s ministry', 'Women’s ministry', 'I’m new and not sure yet',
        ];
        $interest = trim((string)($input['interest'] ?? ''));
        $allowed = $kind === 'serve' ? $serveInterests : $groupInterests;
        if (!in_array($interest, $allowed, true)) {
            return ['ok' => false, 'error' => 'Choose one of the available connection options.', 'value' => []];
        }
        $value['name'] = $name;
        $value['interest'] = $interest;
    }

    return ['ok' => true, 'error' => '', 'value' => $value];
}

function kcmc_connection_client_hash(string $remoteAddress): string {
    return hash('sha256', 'kcmc-connection|' . (trim($remoteAddress) ?: 'unknown'));
}

/** @return array{allowed:bool,retry_after:int,count:int} */
function kcmc_connection_consume_rate(string $clientHash, ?int $now = null): array {
    $now ??= time();
    return kcmc_update_json_store(KCMC_CONNECTION_RATE, ['version' => 1, 'clients' => []], function (array &$state) use ($clientHash, $now): array {
        if (!isset($state['clients']) || !is_array($state['clients'])) $state['clients'] = [];
        $cutoff = $now - KCMC_CONNECTION_RATE_WINDOW;
        foreach ($state['clients'] as $hash => $timestamps) {
            if (!is_array($timestamps)) { unset($state['clients'][$hash]); continue; }
            $timestamps = array_values(array_filter($timestamps, static fn($stamp): bool => is_int($stamp) && $stamp > $cutoff));
            if ($timestamps) $state['clients'][$hash] = $timestamps;
            else unset($state['clients'][$hash]);
        }
        $current = is_array($state['clients'][$clientHash] ?? null) ? $state['clients'][$clientHash] : [];
        if (count($current) >= KCMC_CONNECTION_RATE_LIMIT) {
            return [
                'allowed' => false,
                'retry_after' => max(1, KCMC_CONNECTION_RATE_WINDOW - ($now - min($current))),
                'count' => count($current),
            ];
        }
        $current[] = $now;
        $state['clients'][$clientHash] = $current;
        return ['allowed' => true, 'retry_after' => 0, 'count' => count($current)];
    });
}

/** @return array{stored:bool,duplicate:bool,id:string} */
function kcmc_connection_store(array $value, ?int $now = null): array {
    $now ??= time();
    return kcmc_update_json_store(KCMC_CONNECTION_INTAKE, ['version' => 1, 'submissions' => []], function (array &$state) use ($value, $now): array {
        if (!isset($state['submissions']) || !is_array($state['submissions'])) $state['submissions'] = [];
        $cutoff = $now - KCMC_CONNECTION_DUPLICATE_WINDOW;
        foreach ($state['submissions'] as $stored) {
            if (!is_array($stored)) continue;
            $submitted = strtotime((string)($stored['submitted_at'] ?? ''));
            if ($submitted === false || $submitted < $cutoff) continue;
            if (
                (string)($stored['kind'] ?? '') === (string)$value['kind'] &&
                (string)($stored['email'] ?? '') === (string)$value['email']
            ) {
                return ['stored' => false, 'duplicate' => true, 'id' => (string)($stored['id'] ?? '')];
            }
        }
        $id = kcmc_random_id('connection');
        $row = $value;
        $row['id'] = $id;
        $row['submitted_at'] = gmdate('c', $now);
        $state['submissions'][] = $row;
        if (count($state['submissions']) > 5000) $state['submissions'] = array_slice($state['submissions'], -5000);
        return ['stored' => true, 'duplicate' => false, 'id' => $id];
    });
}

function kcmc_connection_recent(int $limit = 300): array {
    $limit = max(1, min(500, $limit));
    $state = kcmc_read_json_store(KCMC_CONNECTION_INTAKE, ['version' => 1, 'submissions' => []]);
    $rows = array_values(array_filter($state['submissions'] ?? [], 'is_array'));
    usort($rows, static fn(array $a, array $b): int => strcmp((string)($b['submitted_at'] ?? ''), (string)($a['submitted_at'] ?? '')));
    return array_slice($rows, 0, $limit);
}
