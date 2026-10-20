<?php
declare(strict_types=1);
require_once __DIR__ . '/event-calendar.php';

/** Only direct Facebook video URLs, never a shared page disguised as a service link. */
function kcmc_service_stream_url(mixed $value): string {
    if (!is_string($value) || strlen($value) > 500) return '';
    $url = trim($value);
    $parts = parse_url($url);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https'
        || !in_array(strtolower($parts['host'] ?? ''), ['www.facebook.com', 'facebook.com'], true)
        || isset($parts['user']) || isset($parts['pass']) || isset($parts['port']) || isset($parts['fragment'])
        || preg_match('/[\x00-\x20\x7f]/', $url)) return '';
    $path = $parts['path'] ?? '';
    if (preg_match('#\A/(?:[A-Za-z0-9._-]+/)?videos/([0-9]+)/?\z#', $path, $match)) {
        return 'https://www.facebook.com/watch/?v=' . $match[1];
    }
    if (!in_array($path, ['/watch/', '/watch'], true)) return '';
    parse_str($parts['query'] ?? '', $query);
    return is_string($query['v'] ?? null) && preg_match('/\A[0-9]+\z/', $query['v'])
        ? 'https://www.facebook.com/watch/?v=' . $query['v'] : '';
}

function kcmc_worship_services(array $content): array {
    $services = [
        ['id'=>'front-porch', 'time'=>'8:00 AM', 'name'=>'Front Porch Gospel',
         'image'=>'assets/visuals/kcmc-front-porch-official.jpg', 'alt'=>'Front Porch Gospel worship photograph from the KCMC church website',
         'description'=>'Old-time country and bluegrass Gospel music with a Bible-based message.'],
        ['id'=>'traditional', 'time'=>'9:15 AM', 'name'=>'Traditional Worship',
         'image'=>'assets/visuals/kcmc-traditional-sanctuary-20261018.jpg', 'alt'=>'The KCMC congregation worshipping in the traditional sanctuary',
         'description'=>'Hymns, piano, organ and choir in a traditional worship setting.'],
        ['id'=>'contemporary', 'time'=>'10:30 AM', 'name'=>'Contemporary Worship',
         'image'=>'assets/visuals/kcmc-contemporary-gathering-20261018.jpg', 'alt'=>'KCMC members gathered around tables for contemporary worship',
         'description'=>'A relaxed coffee-shop setting with fellowship, refreshments and Launch Kids.'],
    ];
    // Verified on the church's public Facebook video pages, October 20, 2026.
    // These are October 18 recordings, not promises of a currently live stream.
    $verified = [
        'front-porch'=>'https://www.facebook.com/KimberlingCityMethodistChurch/videos/1653016829754297/',
        'traditional'=>'https://www.facebook.com/KimberlingCityMethodistChurch/videos/1756125088830337/',
        'contemporary'=>'https://www.facebook.com/KimberlingCityMethodistChurch/videos/3164538033744471',
    ];
    $configured=is_array($content['worship_streams']??null)?$content['worship_streams']:[];
    $urls = [];
    foreach ($services as &$service) {
        $raw = array_key_exists($service['id'],$configured) ? $configured[$service['id']] : $verified[$service['id']];
        $url = kcmc_service_stream_url($raw);
        $service['recording_label'] = $url !== '' && $url === kcmc_service_stream_url($verified[$service['id']]) ? 'October 18, 2026 recording' : '';
        $service['stream_url'] = $url;
        if ($url !== '') $urls[$url] = ($urls[$url] ?? 0) + 1;
    }
    unset($service);
    // Existing content cannot expose the same recording under two different services.
    foreach ($services as &$service) {
        if (($urls[$service['stream_url']] ?? 0) > 1) $service['stream_url'] = '';
    }
    unset($service);
    return $services;
}

/** Public event highlights are deliberately separate from routine calendar entries. */
function kcmc_public_event_calendar(array $items, mixed $view = null, mixed $scope = null, ?DateTimeImmutable $now = null): array {
    $scope = $scope === 'calendar' ? 'calendar' : 'events';
    $items = array_values(array_filter($items, static function ($event) use ($scope): bool {
        if (!is_array($event)) return false;
        if (in_array($event['public_event'] ?? null, [false, '0', 0], true)) return false;
        if (preg_match('/staff[ -]?meeting|preschool/i', (string)($event['title'] ?? ''))) return false;
        return $scope === 'calendar' || ($event['public_event'] ?? false) === true
            || in_array((string)($event['id'] ?? ''), ['trunk-or-treat-2026', 'richard-french-lasagna-20261114'], true);
    }));
    $zone = new DateTimeZone('America/Chicago');
    $now = ($now ?? new DateTimeImmutable('now', $zone))->setTimezone($zone);
    $calendar = kcmc_event_calendar([], $view, $now);
    $start = $now->setTime(0,0)->modify('+' . (7-(int)$now->format('w')) . ' days');
    $end = $start->modify('+7 days');
    $events=[];
    foreach ($items as $item) {
        if (!empty($item['deleted_at']) || ($item['status']??'published')!=='published'
            || in_array((string)($item['id']??''),KCMC_RETIRED_CONTENT_IDS,true)) continue;
        if (!empty($item['starts_at']) && strtotime((string)$item['starts_at'])>$now->getTimestamp()) continue;
        if (!empty($item['expires_at']) && strtotime((string)$item['expires_at'])<=$now->getTimestamp()) continue;
        $event=kcmc_next_weekly_occurrence($item,$calendar['view']==='next-week'?$start:$now);
        if ($event===null || !kcmc_valid_event_date((string)($event['date']??''))) continue;
        $date=new DateTimeImmutable($event['date'],$zone);
        if ($date<$now->setTime(0,0)) continue;
        if ($calendar['view']==='next-week' && ($date<$start || $date>=$end)) continue;
        if (!empty($event['expires_at']) && strtotime((string)$event['expires_at'])<$date->getTimestamp()) continue;
        $events[]=$event;
    }
    usort($events,'kcmc_compare_event_start');
    return array_replace($calendar,['events'=>$events,'scope'=>$scope]);
}

/** Never make an undated or old issue look like this week's verified bulletin. */
function kcmc_bulletin_is_current(array $bulletin, ?DateTimeImmutable $now = null): bool {
    $zone = new DateTimeZone('America/Chicago');
    $now = ($now ?? new DateTimeImmutable('now', $zone))->setTimezone($zone);
    $date = (string)($bulletin['date'] ?? '');
    $issued = DateTimeImmutable::createFromFormat('!Y-m-d', $date, $zone);
    if (!$issued || $issued->format('Y-m-d') !== $date) return false;
    // Allow a prepublished Sunday issue; require a fresh staff update every week.
    $nextSunday = $now->setTime(23,59,59)->modify('+' . ((7-(int)$now->format('w'))%7) . ' days');
    return $issued <= $nextSunday && $now < $issued->modify('+7 days');
}
