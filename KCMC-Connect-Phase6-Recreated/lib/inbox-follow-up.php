<?php
declare(strict_types=1);

const KCMC_INBOX_STATUSES = ['new', 'contacted', 'closed'];

function kcmc_inbox_status(mixed $value): string {
    $status = strtolower(trim((string)$value));
    return in_array($status, KCMC_INBOX_STATUSES, true) ? $status : 'new';
}

function kcmc_inbox_status_label(string $status): string {
    return match (kcmc_inbox_status($status)) {
        'contacted' => 'Contacted',
        'closed' => 'Closed',
        default => 'New',
    };
}

/** @return array{new:int,contacted:int,closed:int,total:int} */
function kcmc_inbox_status_counts(array $rows): array {
    $counts = ['new' => 0, 'contacted' => 0, 'closed' => 0, 'total' => 0];
    foreach ($rows as $row) {
        if (!is_array($row)) continue;
        $status = kcmc_inbox_status($row['status'] ?? null);
        $counts[$status]++;
        $counts['total']++;
    }
    return $counts;
}

/**
 * Atomically update one row's follow-up state without changing its private contact data.
 *
 * @return array{updated:bool,previous:string,current:string}
 */
function kcmc_inbox_update_status(
    string $path,
    string $collectionKey,
    string $id,
    string $requestedStatus,
    ?int $now = null
): array {
    $id = trim($id);
    $status = strtolower(trim($requestedStatus));
    if ($id === '' || !in_array($status, KCMC_INBOX_STATUSES, true)) {
        return ['updated' => false, 'previous' => 'new', 'current' => 'new'];
    }
    $now ??= time();

    return kcmc_update_json_store($path, ['version' => 1, $collectionKey => []], function (array &$state) use ($collectionKey, $id, $status, $now): array {
        if (!isset($state[$collectionKey]) || !is_array($state[$collectionKey])) {
            return ['updated' => false, 'previous' => 'new', 'current' => 'new'];
        }
        foreach ($state[$collectionKey] as &$row) {
            if (!is_array($row) || !hash_equals((string)($row['id'] ?? ''), $id)) continue;
            $previous = kcmc_inbox_status($row['status'] ?? null);
            if ($previous === $status) {
                unset($row);
                return ['updated' => false, 'previous' => $previous, 'current' => $status];
            }
            $row['status'] = $status;
            $row['status_updated_at'] = gmdate('c', $now);
            unset($row);
            return ['updated' => true, 'previous' => $previous, 'current' => $status];
        }
        unset($row);
        return ['updated' => false, 'previous' => 'new', 'current' => 'new'];
    });
}

function kcmc_connection_update_follow_up(string $id, string $status, ?int $now = null): array {
    if (!defined('KCMC_CONNECTION_INTAKE')) throw new RuntimeException('Connection intake storage is unavailable.');
    return kcmc_inbox_update_status(KCMC_CONNECTION_INTAKE, 'submissions', $id, $status, $now);
}

function kcmc_event_rsvp_update_follow_up(string $id, string $status, ?int $now = null): array {
    if (!defined('KCMC_EVENT_RSVPS')) throw new RuntimeException('RSVP storage is unavailable.');
    return kcmc_inbox_update_status(KCMC_EVENT_RSVPS, 'rsvps', $id, $status, $now);
}
