<?php
declare(strict_types=1);

/** Return the next weekly occurrence without changing the stored series. */
function kcmc_next_weekly_occurrence(array $event, ?DateTimeImmutable $today = null): ?array {
    if (($event['repeat'] ?? '') !== 'weekly') return $event;
    $zone = new DateTimeZone('America/Chicago');
    $today = ($today ?? new DateTimeImmutable('now', $zone))->setTimezone($zone)->setTime(0, 0);
    $date = (string)($event['date'] ?? '');
    if (!kcmc_valid_event_date($date)) return null;
    $next = new DateTimeImmutable($date, $zone);
    if ($next < $today) {
        $days = (int)$next->diff($today)->days;
        $next = $next->modify('+' . (int)(ceil($days / 7) * 7) . ' days');
    }
    $until = (string)($event['repeat_until'] ?? '');
    if ($until !== '' && (!kcmc_valid_event_date($until) || $next->format('Y-m-d') > $until)) return null;
    $event['date'] = $next->format('Y-m-d');
    $event['label'] = 'Weekly' . (empty($event['label']) ? '' : ' • ' . $event['label']);
    return $event;
}

/** Pure mutation: caller owns authorization, CSRF, backup and persistence. */
function kcmc_change_post(array $data, string $section, string $id, string $action, array $input = []): array {
    if (!in_array($section, ['events', 'announcements'], true) || $id === '') throw new InvalidArgumentException('Choose a valid post.');
    $matches = [];
    foreach (($data[$section] ?? []) as $i => $item) if (is_array($item) && (string)($item['id'] ?? '') === $id) $matches[] = $i;
    if (count($matches) !== 1) throw new InvalidArgumentException('This post is missing or ambiguous. Reload the page.');
    $i = $matches[0];
    $post = $data[$section][$i];
    if ($action === 'delete') {
        if (!empty($post['deleted_at'])) throw new InvalidArgumentException('This post is already in Trash.');
        $post['trash_status'] = (string)($post['status'] ?? 'published');
        $post['deleted_at'] = gmdate('c');
        $post['status'] = 'hidden';
    } elseif ($action === 'restore') {
        if (empty($post['deleted_at'])) throw new InvalidArgumentException('This post is not in Trash.');
        // Restore hidden so an old or unconfirmed post cannot republish accidentally.
        unset($post['deleted_at'], $post['trash_status']);
        $post['status'] = 'hidden';
    } elseif ($action === 'publish' && empty($post['deleted_at']) && ($post['status'] ?? '') === 'hidden') {
        $post['status'] = 'published';
    } elseif ($action === 'repeat' && $section === 'events' && empty($post['deleted_at'])) {
        $repeat = (string)($input['repeat'] ?? '');
        $until = trim((string)($input['repeat_until'] ?? ''));
        if (!in_array($repeat, ['', 'weekly'], true)) throw new InvalidArgumentException('Choose Once or Weekly.');
        if (!kcmc_valid_event_date((string)($post['date'] ?? ''))) throw new InvalidArgumentException('Set a valid event date first.');
        if ($repeat === 'weekly' && $until !== '' && (!kcmc_valid_event_date($until) || $until < $post['date'])) throw new InvalidArgumentException('The last weekly date cannot precede the first date.');
        if ($repeat === 'weekly') {
            if (($post['repeat'] ?? '') !== 'weekly') $post['one_time_expires_at'] = (string)($post['expires_at'] ?? '');
            $post['repeat'] = 'weekly';
            $post['repeat_until'] = $until;
            $post['expires_at'] = $until === '' ? '' : kcmc_local_datetime_iso($until, true);
        } else {
            if (($post['repeat'] ?? '') === 'weekly') $post['expires_at'] = (string)($post['one_time_expires_at'] ?? '');
            unset($post['repeat'], $post['repeat_until'], $post['one_time_expires_at']);
        }
    } else throw new InvalidArgumentException('Choose a valid post action.');
    $data[$section][$i] = $post;
    return $data;
}
