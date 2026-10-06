<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();

const KCMC_PUBLICATION_MEDIA_MAX_BYTES = 5242880;
const KCMC_PUBLICATION_MEDIA_MAX_PIXELS = 40000000;
const KCMC_PUBLICATION_MEDIA_MAX_SIDE = 8000;
const KCMC_PUBLICATION_MEDIA_MAX_FILES = 500;
const KCMC_PUBLICATION_MEDIA_TOTAL_BYTES = 524288000;

$mediaDir = KCMC_PRIVATE_DATA . '/publication-media';
$mediaStore = KCMC_PRIVATE_DATA . '/publication-media.json';
$defaultStore = ['version' => 1, 'media' => []];

function publication_media_fail(string $message, int $status = 400): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => $message], JSON_UNESCAPED_SLASHES);
    exit;
}

function publication_media_label(string $name): string {
    $base = pathinfo($name, PATHINFO_FILENAME);
    $base = trim(preg_replace('/[^\pL\pN ._()-]+/u', ' ', $base) ?? '');
    if ($base === '') $base = 'Church photo';
    if (kcmc_text_length($base) > 80) {
        $base = function_exists('mb_substr') ? mb_substr($base, 0, 80, 'UTF-8') : substr($base, 0, 80);
    }
    return $base;
}

function publication_media_index(array $store, string $id): ?array {
    foreach (($store['media'] ?? []) as $item) {
        if (is_array($item) && ($item['id'] ?? '') === $id) return $item;
    }
    return null;
}

function publication_media_url(string $id): string {
    return kcmc_url('admin/publication-media.php?id=' . rawurlencode($id));
}

$method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));

if ($method === 'GET') {
    $store = kcmc_read_json_store($mediaStore, $defaultStore);
    $id = trim((string)($_GET['id'] ?? ''));
    if ($id !== '') {
        if (!preg_match('/\Apubmedia_[a-f0-9]{24}\z/', $id)) publication_media_fail('Invalid media id.', 404);
        $item = publication_media_index($store, $id);
        if ($item === null) publication_media_fail('Media not found.', 404);
        $path = $mediaDir . '/' . (string)($item['file'] ?? '');
        if (!is_file($path) || !is_readable($path)) publication_media_fail('Media file is unavailable.', 404);
        $mime = (string)($item['mime'] ?? 'application/octet-stream');
        if (!in_array($mime, ['image/jpeg', 'image/png', 'image/webp'], true)) publication_media_fail('Media type is unavailable.', 404);
        header('Content-Type: ' . $mime);
        header('Content-Length: ' . (string)filesize($path));
        header('Content-Disposition: inline; filename="kcmc-publication-image"');
        header('X-Content-Type-Options: nosniff');
        readfile($path);
        exit;
    }

    $items = array_values(array_filter($store['media'] ?? [], 'is_array'));
    usort($items, static fn(array $a, array $b): int => strcmp((string)($b['created_at'] ?? ''), (string)($a['created_at'] ?? '')));
    $safe = array_map(static function(array $item): array {
        return [
            'id' => (string)($item['id'] ?? ''),
            'label' => (string)($item['label'] ?? 'Church photo'),
            'mime' => (string)($item['mime'] ?? ''),
            'bytes' => (int)($item['bytes'] ?? 0),
            'width' => (int)($item['width'] ?? 0),
            'height' => (int)($item['height'] ?? 0),
            'created_at' => (string)($item['created_at'] ?? ''),
            'url' => publication_media_url((string)($item['id'] ?? '')),
        ];
    }, $items);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => true, 'media' => $safe], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

if ($method !== 'POST') publication_media_fail('Method not allowed.', 405);
if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) publication_media_fail('Invalid session token.', 403);
if (!isset($_FILES['photo']) || !is_array($_FILES['photo'])) publication_media_fail('Choose a photo to upload.');

$file = $_FILES['photo'];
$error = (int)($file['error'] ?? UPLOAD_ERR_NO_FILE);
if ($error !== UPLOAD_ERR_OK) {
    if ($error === UPLOAD_ERR_INI_SIZE || $error === UPLOAD_ERR_FORM_SIZE) publication_media_fail('Photo is too large.');
    publication_media_fail('Photo upload failed.');
}
$tmp = (string)($file['tmp_name'] ?? '');
$bytes = (int)($file['size'] ?? 0);
if ($tmp === '' || !is_uploaded_file($tmp)) publication_media_fail('Upload could not be verified.');
if ($bytes < 1 || $bytes > KCMC_PUBLICATION_MEDIA_MAX_BYTES) publication_media_fail('Photo must be 5 MB or smaller.');

if (!function_exists('finfo_open')) publication_media_fail('Image verification is unavailable.', 500);
$finfo = finfo_open(FILEINFO_MIME_TYPE);
if ($finfo === false) publication_media_fail('Image verification is unavailable.', 500);
$mime = (string)finfo_file($finfo, $tmp);
finfo_close($finfo);
$extensions = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp'];
if (!isset($extensions[$mime])) publication_media_fail('Upload a JPEG, PNG, or WEBP image.');

$info = @getimagesize($tmp);
if (!is_array($info)) publication_media_fail('The uploaded file is not a readable image.');
$width = (int)($info[0] ?? 0);
$height = (int)($info[1] ?? 0);
$detectedMime = (string)($info['mime'] ?? '');
if ($detectedMime !== $mime) publication_media_fail('Image type verification failed.');
if ($width < 1 || $height < 1 || $width > KCMC_PUBLICATION_MEDIA_MAX_SIDE || $height > KCMC_PUBLICATION_MEDIA_MAX_SIDE) {
    publication_media_fail('Image dimensions are too large.');
}
if (($width * $height) > KCMC_PUBLICATION_MEDIA_MAX_PIXELS) publication_media_fail('Image has too many pixels.');

kcmc_ensure_private_storage();
if (!is_dir($mediaDir) && !mkdir($mediaDir, 0750, true) && !is_dir($mediaDir)) publication_media_fail('Media storage is unavailable.', 500);
@chmod($mediaDir, 0750);

$id = kcmc_random_id('pubmedia');
$storedName = $id . '.' . $extensions[$mime];
$destination = $mediaDir . '/' . $storedName;
if (!move_uploaded_file($tmp, $destination)) publication_media_fail('Could not store the uploaded photo.', 500);
@chmod($destination, 0640);

$item = [
    'id' => $id,
    'label' => publication_media_label((string)($file['name'] ?? '')),
    'file' => $storedName,
    'mime' => $mime,
    'bytes' => $bytes,
    'width' => $width,
    'height' => $height,
    'sha256' => hash_file('sha256', $destination) ?: '',
    'created_at' => gmdate('c'),
    'created_by' => (string)($user['id'] ?? ''),
];

try {
    kcmc_update_json_store($mediaStore, $defaultStore, function (array &$state) use ($item): void {
        $items = array_values(array_filter($state['media'] ?? [], 'is_array'));
        $totalBytes = 0;
        foreach ($items as $existing) $totalBytes += (int)($existing['bytes'] ?? 0);
        if (count($items) >= KCMC_PUBLICATION_MEDIA_MAX_FILES || ($totalBytes + (int)$item['bytes']) > KCMC_PUBLICATION_MEDIA_TOTAL_BYTES) {
            throw new RuntimeException('publication_media_capacity');
        }
        array_unshift($items, $item);
        $state['version'] = 1;
        $state['media'] = $items;
    });
} catch (Throwable $e) {
    @unlink($destination);
    if ($e->getMessage() === 'publication_media_capacity') publication_media_fail('Shared photo library is full. Remove unused photos before uploading more.', 409);
    publication_media_fail('Could not record the uploaded photo.', 500);
}

kcmc_audit('publication_media_uploaded', [
    'media_id' => $id,
    'mime' => $mime,
    'bytes' => $bytes,
    'width' => $width,
    'height' => $height,
]);
header('Content-Type: application/json; charset=utf-8');
echo json_encode([
    'ok' => true,
    'media' => [
        'id' => $id,
        'label' => $item['label'],
        'mime' => $mime,
        'bytes' => $bytes,
        'width' => $width,
        'height' => $height,
        'created_at' => $item['created_at'],
        'url' => publication_media_url($id),
    ],
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
