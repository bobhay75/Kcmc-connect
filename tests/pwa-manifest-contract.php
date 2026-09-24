<?php
$root = dirname(__DIR__);
$app = $root . '/KCMC-Connect-Phase6-Recreated';
$manifestPath = $app . '/manifest.webmanifest';

$raw = file_get_contents($manifestPath);
if ($raw === false) {
    fwrite(STDERR, "Could not read manifest.webmanifest\n");
    exit(1);
}

$manifest = json_decode($raw, true);
if (!is_array($manifest)) {
    fwrite(STDERR, "Manifest is not valid JSON\n");
    exit(1);
}

if (($manifest['name'] ?? null) !== 'KCMC Connect') {
    fwrite(STDERR, "Unexpected app name\n");
    exit(1);
}

$icons = $manifest['icons'] ?? [];
if (!is_array($icons) || count($icons) < 4) {
    fwrite(STDERR, "Manifest must expose any and maskable icons at 192 and 512 sizes\n");
    exit(1);
}

$seen = [];
foreach ($icons as $icon) {
    $src = (string)($icon['src'] ?? '');
    $size = (string)($icon['sizes'] ?? '');
    $purpose = (string)($icon['purpose'] ?? '');
    if ($src === '' || $size === '' || $purpose === '') {
        fwrite(STDERR, "Manifest icon entry is incomplete\n");
        exit(1);
    }
    if (!str_contains($src, '?v=3.0.2')) {
        fwrite(STDERR, "Manifest icon cache key must be v=3.0.2\n");
        exit(1);
    }
    $path = $app . '/' . explode('?', $src, 2)[0];
    if (!is_file($path)) {
        fwrite(STDERR, "Referenced icon file does not exist: {$path}\n");
        exit(1);
    }
    $info = @getimagesize($path);
    if ($info === false || ($info['mime'] ?? '') !== 'image/png') {
        fwrite(STDERR, "Referenced icon is not a readable PNG: {$path}\n");
        exit(1);
    }
    [$expectedW, $expectedH] = array_map('intval', explode('x', $size));
    if (($info[0] ?? 0) !== $expectedW || ($info[1] ?? 0) !== $expectedH) {
        fwrite(STDERR, "PNG dimensions do not match manifest declaration for {$src}\n");
        exit(1);
    }
    $seen[$size . ':' . $purpose] = true;
}

foreach (['192x192:any', '192x192:maskable', '512x512:any', '512x512:maskable'] as $required) {
    if (empty($seen[$required])) {
        fwrite(STDERR, "Missing required icon declaration: {$required}\n");
        exit(1);
    }
}

echo "PWA manifest icon contract passed\n";
