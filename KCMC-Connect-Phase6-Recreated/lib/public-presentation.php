<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

/** Remove the retired monthly source from public output without changing stored content.
 * The church website, Facebook, and Mary Lou's Friday updates remain valid editorial sources.
 * There is deliberately no keyword-based newsletter filtering or automatic rewriting of notes.
 */
function kcmc_public_content_view(array $data): array {
    unset($data['news']);
    $data['announcements'] = array_values(array_filter(
        is_array($data['announcements'] ?? null) ? $data['announcements'] : [],
        static fn($item): bool => is_array($item) && (string)($item['id'] ?? '') !== 'sep-news-16'
    ));
    return $data;
}

function kcmc_public_content(): array {
    return kcmc_public_content_view(kcmc_content());
}
