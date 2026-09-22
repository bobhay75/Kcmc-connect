<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/backup-retention.php';

function retention_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$dir = sys_get_temp_dir() . '/kcmc-backups-' . bin2hex(random_bytes(5));
if (!mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('Could not create temp backup directory.');

$names = [];
for ($i = 0; $i < 8; $i++) {
    $name = sprintf('content-20260922-12%02d00-%06x.json', $i, $i + 1);
    $path = $dir . '/' . $name;
    file_put_contents($path, "{}\n");
    touch($path, 1700000000 + $i);
    $names[] = $name;
}
file_put_contents($dir . '/content-manual.json', "manual\n");
file_put_contents($dir . '/content-20260922-invalid.json', "invalid-name\n");
file_put_contents($dir . '/notes.txt', "keep\n");

$paths = kcmc_content_backup_paths($dir);
retention_check(count($paths) === 8, 'only KCMC-generated automatic backup names are recognized');
retention_check(basename($paths[0]) === $names[7], 'newest automatic backup sorts first');
retention_check(basename($paths[7]) === $names[0], 'oldest automatic backup sorts last');

$result = kcmc_prune_content_backups($dir, 3);
retention_check(($result['found'] ?? 0) === 8, 'rotation reports pre-prune automatic backup count');
retention_check(($result['kept'] ?? 0) === 3, 'rotation preserves requested newest count');
retention_check(($result['removed'] ?? 0) === 5 && ($result['failed'] ?? 0) === 0, 'rotation removes only backups beyond retention count');

$remaining = array_map('basename', kcmc_content_backup_paths($dir));
retention_check($remaining === [$names[7], $names[6], $names[5]], 'three newest automatic backups remain');
retention_check(is_file($dir . '/content-manual.json') && is_file($dir . '/content-20260922-invalid.json') && is_file($dir . '/notes.txt'), 'unrelated and nonconforming files remain untouched');

$clamped = kcmc_prune_content_backups($dir, 0);
retention_check(($clamped['kept'] ?? 0) === 1 && ($clamped['removed'] ?? 0) === 2, 'retention count is clamped to preserve at least one automatic backup');

$save = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/save.php');
retention_check(is_string($save) && str_contains($save, "require_once __DIR__ . '/../lib/backup-retention.php'"), 'Publishing Desk save path loads backup retention helper');
$saveWrite = strpos((string)$save, 'kcmc_write_content(');
$savePrune = strpos((string)$save, 'kcmc_prune_content_backups(');
retention_check($saveWrite !== false && $savePrune !== false && $saveWrite < $savePrune, 'Publishing Desk rotates only after successful content write');

$restore = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/content-restore.php');
retention_check(is_string($restore) && str_contains($restore, "require_once __DIR__ . '/backup-retention.php'"), 'restore path loads backup retention helper');
$restoreWrite = strpos((string)$restore, 'kcmc_write_content(');
$restorePrune = strpos((string)$restore, 'kcmc_prune_content_backups(');
retention_check($restoreWrite !== false && $restorePrune !== false && $restoreWrite < $restorePrune, 'restore rotates only after successful content write');

retention_check(KCMC_CONTENT_BACKUP_KEEP === 250, 'default automatic backup retention keeps 250 versions');

foreach (glob($dir . '/*') ?: [] as $path) @unlink($path);
@rmdir($dir);
echo "Backup retention contract checks passed.\n";
