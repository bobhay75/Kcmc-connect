<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
header('Content-Type: application/json; charset=utf-8');

$storePath = KCMC_PRIVATE_DATA . '/publications.json';
$defaultStore = ['version' => 2, 'projects' => []];

function pub_fail(string $message, int $status = 400): never {
    http_response_code($status);
    echo json_encode(['ok' => false, 'error' => $message], JSON_UNESCAPED_SLASHES);
    exit;
}

function pub_number(mixed $value, float $min, float $max): float {
    if (!is_numeric($value)) pub_fail('Invalid numeric design value.');
    $n = (float)$value;
    if (!is_finite($n) || $n < $min || $n > $max) pub_fail('Design value is out of range.');
    return round($n, 2);
}

function pub_text(mixed $value, int $max): string {
    $text = is_string($value) ? trim($value) : '';
    if (kcmc_text_length($text) > $max) pub_fail('Publication text is too long.');
    return $text;
}

function pub_color(mixed $value, string $fallback): string {
    $v = is_string($value) ? strtolower(trim($value)) : '';
    return preg_match('/\A#[0-9a-f]{6}\z/', $v) ? $v : $fallback;
}

function pub_media_exists(string $id): bool {
    static $index = null;
    if ($index === null) {
        $index = [];
        $store = kcmc_read_json_store(KCMC_PRIVATE_DATA . '/publication-media.json', ['version' => 1, 'media' => []]);
        foreach (($store['media'] ?? []) as $media) {
            if (!is_array($media)) continue;
            $mediaId = (string)($media['id'] ?? '');
            $file = (string)($media['file'] ?? '');
            if ($mediaId !== '' && $file !== '') $index[$mediaId] = $file;
        }
    }
    if (!isset($index[$id])) return false;
    return is_file(KCMC_PRIVATE_DATA . '/publication-media/' . $index[$id]);
}

function pub_item(array $item): array {
    $type = (string)($item['type'] ?? '');
    if (!in_array($type, ['text', 'shape', 'image'], true)) pub_fail('Unsupported publication item.');
    $out = [
        'type' => $type,
        'x' => pub_number($item['x'] ?? null, 0, 1600),
        'y' => pub_number($item['y'] ?? null, 0, 2000),
        'w' => pub_number($item['w'] ?? null, 20, 1600),
        'h' => pub_number($item['h'] ?? null, 20, 2000),
        'fontFamily' => in_array((string)($item['fontFamily'] ?? ''), ['Arial', 'Arial Narrow', 'Georgia', 'Times New Roman', 'Verdana'], true) ? (string)$item['fontFamily'] : 'Arial',
        'fontSize' => pub_number($item['fontSize'] ?? 24, 8, 120),
        'fontWeight' => ((string)($item['fontWeight'] ?? '400') === '700') ? '700' : '400',
        'fontStyle' => ((string)($item['fontStyle'] ?? 'normal') === 'italic') ? 'italic' : 'normal',
        'textAlign' => in_array((string)($item['textAlign'] ?? ''), ['left', 'center', 'right'], true) ? (string)$item['textAlign'] : 'left',
        'color' => pub_color($item['color'] ?? '', '#17324c'),
        'fill' => pub_color($item['fill'] ?? '', '#ffffff'),
        'borderColor' => pub_color($item['borderColor'] ?? '', '#17324c'),
        'borderWidth' => pub_number($item['borderWidth'] ?? 0, 0, 12),
        'opacity' => pub_number($item['opacity'] ?? 1, 0.1, 1),
    ];
    if ($type === 'text') {
        $out['text'] = pub_text($item['text'] ?? '', 12000);
    } elseif ($type === 'image') {
        $mediaId = pub_text($item['mediaId'] ?? '', 40);
        if ($mediaId !== '') {
            if (!preg_match('/\Apubmedia_[a-f0-9]{24}\z/', $mediaId) || !pub_media_exists($mediaId)) {
                pub_fail('Shared publication photo is unavailable.');
            }
            $out['mediaId'] = $mediaId;
        } else {
            $src = pub_text($item['src'] ?? '', 300);
            $allowed = [
                'kcmc-building-2024.webp',
                'kcmc-worship-2017.webp',
                'kcmc-ministry-group.jpg',
                'kcmc-stage-2014.webp',
                'trunk-or-treat-2026.webp',
            ];
            $path = (string)(parse_url($src, PHP_URL_PATH) ?? '');
            $base = basename($path);
            if (!str_contains($path, '/assets/visuals/') || !in_array($base, $allowed, true)) {
                pub_fail('Only approved KCMC library or shared photos can be stored in projects.');
            }
            $out['src'] = kcmc_url('assets/visuals/' . $base);
        }
        $out['alt'] = pub_text($item['alt'] ?? '', 180);
    }
    return $out;
}

function pub_page(array $page): array {
    $pageSize = in_array((string)($page['pageSize'] ?? ''), ['letter', 'half', 'postcard'], true) ? (string)$page['pageSize'] : 'letter';
    $orientation = in_array((string)($page['orientation'] ?? ''), ['portrait', 'landscape'], true) ? (string)$page['orientation'] : 'portrait';
    $rawItems = $page['items'] ?? [];
    if (!is_array($rawItems) || count($rawItems) > 100) pub_fail('Publication page has too many items.');
    $items = [];
    foreach ($rawItems as $item) {
        if (!is_array($item)) pub_fail('Invalid publication item.');
        $items[] = pub_item($item);
    }
    return [
        'pageSize' => $pageSize,
        'orientation' => $orientation,
        'items' => $items,
    ];
}

function pub_normalize_project(array $project): array {
    if (isset($project['pages']) && is_array($project['pages']) && count($project['pages']) > 0) return $project;
    $project['pages'] = [[
        'pageSize' => in_array((string)($project['pageSize'] ?? ''), ['letter', 'half', 'postcard'], true) ? (string)$project['pageSize'] : 'letter',
        'orientation' => in_array((string)($project['orientation'] ?? ''), ['portrait', 'landscape'], true) ? (string)$project['orientation'] : 'portrait',
        'items' => is_array($project['items'] ?? null) ? array_values(array_filter($project['items'], 'is_array')) : [],
    ]];
    unset($project['pageSize'], $project['orientation'], $project['items']);
    return $project;
}

$method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
if ($method === 'GET') {
    $store = kcmc_read_json_store($storePath, $defaultStore);
    $projects = array_map('pub_normalize_project', array_values(array_filter($store['projects'] ?? [], 'is_array')));
    usort($projects, static fn(array $a, array $b): int => strcmp((string)($b['updated'] ?? ''), (string)($a['updated'] ?? '')));
    echo json_encode(['ok' => true, 'projects' => $projects], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

if ($method !== 'POST') pub_fail('Method not allowed.', 405);
$raw = file_get_contents('php://input');
$body = json_decode($raw ?: '', true);
if (!is_array($body)) pub_fail('Invalid JSON.');
if (!kcmc_verify_csrf($body['csrf'] ?? null)) pub_fail('Invalid session token.', 403);

$name = pub_text($body['name'] ?? '', 120);
if ($name === '') $name = 'Untitled publication';
$id = is_string($body['id'] ?? null) && preg_match('/\Apub_[a-f0-9]{24}\z/', (string)$body['id']) ? (string)$body['id'] : kcmc_random_id('pub');
$rawPages = $body['pages'] ?? null;
if ($rawPages === null) {
    $rawPages = [[
        'pageSize' => $body['pageSize'] ?? 'letter',
        'orientation' => $body['orientation'] ?? 'portrait',
        'items' => $body['items'] ?? [],
    ]];
}
if (!is_array($rawPages) || count($rawPages) < 1 || count($rawPages) > 12) pub_fail('Publication must contain between 1 and 12 pages.');
$pages = [];
$totalItems = 0;
foreach ($rawPages as $rawPage) {
    if (!is_array($rawPage)) pub_fail('Invalid publication page.');
    $validated = pub_page($rawPage);
    $totalItems += count($validated['items']);
    $pages[] = $validated;
}
$now = gmdate('c');
$project = [
    'id' => $id,
    'name' => $name,
    'pages' => $pages,
    'updated' => $now,
    'updated_by' => (string)($user['id'] ?? ''),
];

kcmc_update_json_store($storePath, $defaultStore, function (array &$state) use ($project): void {
    $projects = array_values(array_filter($state['projects'] ?? [], 'is_array'));
    $found = false;
    foreach ($projects as $i => $existing) {
        if (($existing['id'] ?? '') === $project['id']) {
            $projects[$i] = $project;
            $found = true;
            break;
        }
    }
    if (!$found) array_unshift($projects, $project);
    usort($projects, static fn(array $a, array $b): int => strcmp((string)($b['updated'] ?? ''), (string)($a['updated'] ?? '')));
    $state['version'] = 2;
    $state['projects'] = array_slice($projects, 0, 50);
});
kcmc_audit('publication_project_saved', ['publication_id' => $id, 'page_count' => count($pages), 'item_count' => $totalItems]);
echo json_encode(['ok' => true, 'project' => $project], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
