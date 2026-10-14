<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

/** Read-only public week projection. Publication gates always use the real reference day. */
function kcmc_event_calendar(array $items, mixed $requested = null, ?DateTimeImmutable $now = null): array {
    $zone = new DateTimeZone('America/Chicago');
    $now = ($now ?? new DateTimeImmutable('now', $zone))->setTimezone($zone);
    $start = $now->setTime(0, 0)->modify('+' . (7 - (int)$now->format('w')) . ' days');
    $end = $start->modify('+7 days');
    $view = $requested === 'next-week' ? 'next-week' : 'upcoming';
    $events = $view === 'upcoming' ? kcmc_active_items($items) : [];
    if ($view === 'next-week') {
        foreach ($items as $item) {
            if (!is_array($item) || !empty($item['deleted_at']) || ($item['status'] ?? 'published') !== 'published') continue;
            if (in_array((string)($item['id'] ?? ''), KCMC_RETIRED_CONTENT_IDS, true)) continue;
            // Do not reveal embargoed or expired posts just because a visitor looks ahead.
            if (!empty($item['starts_at']) && strtotime((string)$item['starts_at']) > $now->getTimestamp()) continue;
            if (!empty($item['expires_at']) && strtotime((string)$item['expires_at']) <= $now->getTimestamp()) continue;
            $event = kcmc_next_weekly_occurrence($item, $start);
            if ($event === null || !kcmc_valid_event_date((string)($event['date'] ?? ''))) continue;
            $date = new DateTimeImmutable($event['date'], $zone);
            if ($date < $start || $date >= $end) continue;
            if (!empty($event['expires_at']) && strtotime((string)$event['expires_at']) < $date->getTimestamp()) continue;
            $events[] = $event;
        }
    }
    $events = kcmc_calendar_without_legacy_griefshare_duplicate($events);
    usort($events, 'kcmc_compare_event_start');
    return ['view' => $view, 'events' => $events, 'range' => $start->format('M j') . '–' . $end->modify('-1 day')->format('M j, Y')];
}

/** Suppress only the known legacy weekly duplicate in the public calendar.
 * Both records must already be visible and describe the same occurrence.
 * Stored content, one-time events and unrelated series are never changed.
 */
function kcmc_calendar_without_legacy_griefshare_duplicate(array $events): array {
    $current = null;
    foreach ($events as $event) {
        if (($event['id'] ?? '') === 'griefshare-20261014' && ($event['repeat'] ?? '') === 'weekly') {
            $current = $event;
            break;
        }
    }
    if ($current === null) return $events;
    return array_values(array_filter($events, static function (array $event) use ($current): bool {
        if (($event['id'] ?? '') !== 'griefshare-0902' || ($event['repeat'] ?? '') !== 'weekly') return true;
        foreach (['date', 'time', 'end_time', 'location'] as $field) {
            if (trim((string)($event[$field] ?? '')) !== trim((string)($current[$field] ?? ''))) return true;
        }
        return false;
    }));
}
