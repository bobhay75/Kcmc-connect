<?php
declare(strict_types=1);

const KCMC_CONTENT_BACKUP_KEEP = 250;

function kcmc_content_backup_paths(string $directory): array {
    if (!is_dir($directory) || !is_readable($directory)) return [];
    $paths = glob(rtrim($directory, '/') . '/content-*.json') ?: [];
    $safe = [];
    foreach ($paths as $path) {
        if (!is_file($path)) continue;
        $name = basename($path);
        if (!preg_match('/\Acontent-\d{8}-\d{6}-[A-Fa-f0-9]{6}\.json\z/', $name)) continue;
        $safe[] = $path;
    }
    usort($safe, static function (string $a, string $b): int {
        $am = (int)@filemtime($a);
        $bm = (int)@filemtime($b);
        return $am === $bm ? strcmp(basename($b), basename($a)) : ($bm <=> $am);
    });
    return $safe;
}

function kcmc_prune_content_backups(string $directory, int $keep = KCMC_CONTENT_BACKUP_KEEP): array {
    $keep = max(1, min(1000, $keep));
    $paths = kcmc_content_backup_paths($directory);
    $removed = 0;
    $failed = 0;
    foreach (array_slice($paths, $keep) as $path) {
        if (@unlink($path)) $removed++;
        else $failed++;
    }
    return [
        'found' => count($paths),
        'kept' => min(count($paths), $keep),
        'removed' => $removed,
        'failed' => $failed,
    ];
}
