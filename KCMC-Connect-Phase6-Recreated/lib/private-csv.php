<?php
declare(strict_types=1);

function kcmc_csv_safe_cell(mixed $value): string {
    $text = str_replace(["\r\n", "\r"], "\n", trim((string)$value));
    if ($text !== '' && in_array($text[0], ['=', '+', '-', '@'], true)) {
        $text = "'" . $text;
    }
    return $text;
}

function kcmc_csv_status_filter(mixed $value): string {
    $status = strtolower(trim((string)$value));
    return in_array($status, ['new', 'contacted', 'closed'], true) ? $status : 'all';
}

function kcmc_csv_filter_rows(array $rows, string $status): array {
    if ($status === 'all') return array_values(array_filter($rows, 'is_array'));
    return array_values(array_filter($rows, static function ($row) use ($status): bool {
        return is_array($row) && function_exists('kcmc_inbox_status') && kcmc_inbox_status($row['status'] ?? null) === $status;
    }));
}

/**
 * Emit a private CSV attachment. Rows should already be ordered and bounded.
 *
 * @param list<string> $headers
 * @param list<array<int|string,mixed>> $rows
 */
function kcmc_csv_download(string $filename, array $headers, array $rows): never {
    kcmc_private_headers();
    header('Content-Type: text/csv; charset=UTF-8');
    header('Content-Disposition: attachment; filename="' . preg_replace('/[^A-Za-z0-9._-]/', '-', $filename) . '"');
    header('X-Content-Type-Options: nosniff');

    $out = fopen('php://output', 'wb');
    if ($out === false) {
        http_response_code(500);
        exit('Export unavailable.');
    }
    // UTF-8 BOM improves Excel compatibility without changing cell content.
    fwrite($out, "\xEF\xBB\xBF");
    fputcsv($out, array_map('kcmc_csv_safe_cell', $headers));
    foreach ($rows as $row) {
        fputcsv($out, array_map('kcmc_csv_safe_cell', array_values($row)));
    }
    fclose($out);
    exit;
}
