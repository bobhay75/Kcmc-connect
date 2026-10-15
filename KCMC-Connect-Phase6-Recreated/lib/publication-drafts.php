<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

final class KcmcPublicationConflict extends RuntimeException {}

function kcmc_publication_store_path(): string { return KCMC_PRIVATE_DATA . '/publications.json'; }
function kcmc_publication_revision(array $project): int {
    $revision = $project['revision'] ?? 0; // Existing drafts start at revision zero without a migration write.
    if (!is_int($revision) || $revision < 0) throw new RuntimeException('Publication storage needs administrator review.');
    return $revision;
}
function kcmc_publication_validate_store(array $state): void {
    if (!in_array($state['version'] ?? null, [1, 2], true) || !is_array($state['projects'] ?? null)) {
        throw new RuntimeException('Publication storage needs administrator review.');
    }
    $ids = [];
    foreach ($state['projects'] as $project) {
        if (!is_array($project) || !is_string($project['id'] ?? null) || !preg_match('/\Apub_[a-f0-9]{24}\z/', $project['id'])
            || isset($ids[$project['id']]) || !is_string($project['name'] ?? null) || !is_string($project['updated'] ?? null)
            || (!is_array($project['pages'] ?? null) && !is_array($project['items'] ?? null))) {
            throw new RuntimeException('Publication storage needs administrator review.');
        }
        kcmc_publication_revision($project);
        $ids[$project['id']] = true;
    }
}
/** Fixed store/lock/backup paths must remain single regular files. */
function kcmc_publication_check_file(string $path): void {
    clearstatcache(true, $path);
    $stat = @lstat($path);
    if ($stat !== false && (($stat['mode'] & 0170000) !== 0100000 || $stat['nlink'] !== 1)) throw new RuntimeException('Publication storage needs administrator review.');
}
function kcmc_publication_read_store(): array {
    $path = kcmc_publication_store_path();
    kcmc_publication_check_file($path);
    if (!file_exists($path)) return ['version'=>2, 'projects'=>[]];
    if (!is_file($path)) throw new RuntimeException('Publication storage needs administrator review.');
    $raw = @file_get_contents($path);
    $state = is_string($raw) ? json_decode($raw, true) : null;
    if (!is_array($state)) throw new RuntimeException('Publication storage needs administrator review.');
    kcmc_publication_validate_store($state);
    return $state;
}

/** Compare the submitted revision while holding the actual publication-store lock. */
function kcmc_publication_save_draft(array $project, ?string $existingId, int $expectedRevision, string $actorId): array {
    if ($expectedRevision < 0 || $actorId === '') throw new InvalidArgumentException('Invalid publication save.');
    kcmc_ensure_private_storage();
    $path = kcmc_publication_store_path();
    kcmc_publication_check_file($path . '.lock');
    $lock = @fopen($path . '.lock', 'c+');
    if ($lock === false || !flock($lock, LOCK_EX)) throw new RuntimeException('Publication storage is busy. Try again.');
    $lockStat = fstat($lock);
    if (!is_array($lockStat) || ($lockStat['mode'] & 0170000) !== 0100000 || $lockStat['nlink'] !== 1) { flock($lock, LOCK_UN); fclose($lock); throw new RuntimeException('Publication storage needs administrator review.'); }
    @chmod($path . '.lock', 0600);
    $tmp = null;
    try {
        $state = kcmc_publication_read_store();
        $projects = $state['projects'];
        $index = null;
        if ($existingId !== null) foreach ($projects as $i => $stored) if ($stored['id'] === $existingId) { $index = $i; break; }
        if ($existingId !== null && ($index === null || kcmc_publication_revision($projects[$index]) !== $expectedRevision)) {
            throw new KcmcPublicationConflict('This publication changed. Your edits are still here. Save a copy or load the latest version.');
        }
        if ($existingId === null && $expectedRevision !== 0) throw new KcmcPublicationConflict('Save this draft as a new copy.');
        $project['id'] = $existingId ?? kcmc_random_id('pub');
        $project['revision'] = $index === null ? 1 : kcmc_publication_revision($projects[$index]) + 1;
        $project['updated'] = gmdate('c');
        $project['updated_by'] = $actorId;
        if ($index === null) array_unshift($projects, $project); else $projects[$index] = $project;
        usort($projects, static fn(array $a, array $b): int => strcmp($b['updated'], $a['updated']) ?: strcmp($a['id'], $b['id']));
        $state['version'] = 2; $state['projects'] = $projects;
        kcmc_publication_validate_store($state);
        $json = json_encode($state, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
        if (is_file($path)) {
            kcmc_publication_check_file($path . '.previous.json');
            if (!@copy($path, $path . '.previous.json')) throw new RuntimeException('Could not back up publications. Nothing was saved.');
            @chmod($path . '.previous.json', 0600);
        }
        $tmp = $path . '.tmp-' . bin2hex(random_bytes(8));
        if (@file_put_contents($tmp, $json, LOCK_EX) !== strlen($json)) throw new RuntimeException('Could not save the publication.');
        @chmod($tmp, 0600);
        if (!rename($tmp, $path)) throw new RuntimeException('Could not save the publication.');
        $tmp = null;
        return $project;
    } finally {
        if ($tmp !== null && is_file($tmp)) @unlink($tmp);
        flock($lock, LOCK_UN); fclose($lock);
    }
}
