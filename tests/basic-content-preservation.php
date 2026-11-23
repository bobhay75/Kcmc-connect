<?php
declare(strict_types=1);

// Run against a generated Core package; all writes use a temporary fixture.
// Usage: php tests/basic-content-preservation.php /absolute/path/to/core
$source = realpath($argv[1] ?? '');
if ($source === false || !is_dir($source)) {
    fwrite(STDERR, "Provide a generated Core package directory.\n");
    exit(2);
}
$required = ['lib/bootstrap.php', 'lib/post-controls.php', 'lib/content-restore.php', 'lib/backup-retention.php'];
foreach ($required as $relative) {
    if (!is_file($source . '/' . $relative)) {
        fwrite(STDERR, "Missing Core dependency: {$relative}\n");
        exit(2);
    }
}

$temporary = sys_get_temp_dir() . '/kcmc-core-content-' . bin2hex(random_bytes(8));
$checks = 0;
$status = 0;
function content_check(bool $condition, string $message): void {
    global $checks;
    if (!$condition) throw new RuntimeException($message);
    ++$checks;
    echo "PASS: {$message}\n";
}
function content_json(array $data): string {
    return json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . "\n";
}
function editorial_values(array $data): array {
    unset($data['meta']);
    return $data;
}

try {
    mkdir($temporary . '/lib', 0700, true);
    mkdir($temporary . '/data/releases', 0700, true);
    foreach ($required as $relative) copy($source . '/' . $relative, $temporary . '/' . $relative);
    file_put_contents($temporary . '/data/releases/3.0.0.json', content_json([
        'version' => '3.0.0',
        'announcements' => [['id' => 'bundled-announcement', 'body' => 'Must not replace the church record.']],
        'events' => [['id' => 'bundled-event', 'title' => 'Must not replace the church record.']],
        'news' => [['id' => 'bundled-news', 'body' => 'Must not replace the church record.']],
    ]));
    require $temporary . '/lib/bootstrap.php';
    require $temporary . '/lib/content-restore.php';

    $fixture = [
        'meta' => ['version' => '2.9.0', 'custom' => 'Retain unrelated metadata.'],
        'contact' => ['email' => 'office@example.test', 'phone' => 'Synthetic original', 'office_hours' => ''],
        'announcements' => [
            ['id' => 'church-announcement', 'body' => "Keep these blanks: ___\nAnd this line.", 'status' => 'published'],
            ['id' => 'removed-announcement', 'body' => 'Retain the tombstone.', 'deleted_at' => '2026-01-01T12:00:00Z'],
        ],
        'events' => [
            ['id' => 'trunk-or-treat-2026', 'title' => 'Operator record', 'image' => 'custom-art.webp', 'image_alt' => 'Operator wording', 'status' => 'hidden'],
            ['id' => 'church-event', 'title' => 'Operator event', 'date' => '2030-01-01', 'repeat' => 'weekly', 'repeat_until' => '2030-02-01'],
            ['id' => 'removed-event', 'title' => 'Retain the tombstone.', 'deleted_at' => '2026-01-01T12:00:00Z'],
        ],
        'news' => [['id' => 'church-news', 'body' => 'Stored news must survive unrelated publishing.']],
        'bulletin' => ['title' => 'Saved bulletin', 'date' => '2000-01-01', 'notes' => ['Preserve ____ exactly.']],
        'custom_section' => ['verbatim' => 'Retain fields the editor does not own.'],
    ];
    $cases = ['missing release marker' => $fixture];
    foreach (['2.9.0', '3.0.0', '4.0.0'] as $release) {
        $case = $fixture;
        $case['meta']['content_release'] = $release;
        $case['contact']['office_hours'] = 'Closed for an operator-approved holiday.';
        $cases['release marker ' . $release] = $case;
    }
    $empty = $fixture;
    $empty['announcements'] = $empty['events'] = $empty['news'] = [];
    $cases['intentionally empty sections'] = $empty;
    $absent = $fixture;
    unset($absent['meta'], $absent['contact']['office_hours']);
    $cases['absent optional metadata and hours'] = $absent;

    foreach ($cases as $name => $expected) {
        $raw = content_json($expected);
        file_put_contents(KCMC_DATA, $raw);
        $hash = hash_file('sha256', KCMC_DATA);
        $loaded = kcmc_content();
        content_check($loaded === $expected, "{$name}: read returns the exact stored document");
        content_check(hash_file('sha256', KCMC_DATA) === $hash, "{$name}: read leaves stored bytes unchanged");
        $hookInput = $expected;
        content_check(kcmc_apply_required_public_content($hookInput) === false && $hookInput === $expected, "{$name}: restore hook adds and rewrites nothing");

        $loaded['contact']['phone'] = 'Synthetic intentional phone edit';
        $savedHash = kcmc_write_content($loaded, 'synthetic-editor', $hash, true);
        $saved = json_decode((string)file_get_contents(KCMC_DATA), true, 512, JSON_THROW_ON_ERROR);
        content_check(editorial_values($saved) === editorial_values($loaded), "{$name}: unrelated publish preserves every other editorial field");
        content_check(($saved['meta']['content_release'] ?? null) === ($expected['meta']['content_release'] ?? null), "{$name}: publish preserves the release marker");
        content_check($savedHash === hash_file('sha256', KCMC_DATA), "{$name}: writer returns the stored hash");
        $backups = glob(KCMC_BACKUPS . '/content-*.json') ?: [];
        content_check(count(array_filter($backups, static fn(string $path): bool => file_get_contents($path) === $raw)) > 0, "{$name}: backup preserves the original bytes");
        $staleRefused = false;
        try { kcmc_write_content($expected, 'synthetic-stale-editor', $hash, true); }
        catch (RuntimeException) { $staleRefused = true; }
        content_check($staleRefused && hash_file('sha256', KCMC_DATA) === $savedHash, "{$name}: stale publish still fails without changing content");

        $restored = kcmc_restore_public_content($raw, 'synthetic-restorer');
        $restoredDisk = json_decode((string)file_get_contents(KCMC_DATA), true, 512, JSON_THROW_ON_ERROR);
        content_check(!empty($restored['ok']) && $restored['data'] === $expected, "{$name}: restore returns the exact accepted backup document");
        content_check(editorial_values($restoredDisk) === editorial_values($expected), "{$name}: restore preserves content, artwork, dates and empty fields");
    }

    foreach (['{broken', '', 'null'] as $invalid) {
        file_put_contents(KCMC_DATA, $invalid);
        content_check(kcmc_content() === [] && file_get_contents(KCMC_DATA) === $invalid, 'invalid or empty input retains the existing empty fallback without overwriting bytes');
    }
    unlink(KCMC_DATA);
    content_check(kcmc_content() === [] && !file_exists(KCMC_DATA), 'missing content does not silently install bundled fixtures');
    echo "Core editorial preservation: {$checks} checks passed.\n";
} catch (Throwable $error) {
    fwrite(STDERR, 'FAIL: ' . $error->getMessage() . "\n");
    $status = 1;
} finally {
    if (is_dir($temporary)) {
        $items = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($temporary, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($items as $item) {
            if ($item->isDir() && !$item->isLink()) rmdir($item->getPathname());
            else unlink($item->getPathname());
        }
        rmdir($temporary);
    }
}
exit($status);
