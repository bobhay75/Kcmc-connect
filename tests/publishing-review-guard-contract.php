<?php
declare(strict_types=1);

$root = dirname(__DIR__);
$save = file_get_contents($root . '/KCMC-Connect-Phase6-Recreated/admin/save.php');

function publish_guard_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: $message\n");
        exit(1);
    }
    fwrite(STDOUT, "PASS: $message\n");
}

publish_guard_check(is_string($save), 'Publishing Desk save endpoint is readable');
$csrfPos = strpos($save, 'kcmc_verify_csrf');
$confirmPos = strpos($save, 'confirm_publish');
$writePos = strpos($save, 'kcmc_write_content');
publish_guard_check($csrfPos !== false, 'CSRF validation remains present');
publish_guard_check($confirmPos !== false, 'explicit publish confirmation is enforced server-side');
publish_guard_check($writePos !== false, 'content writer remains present');
publish_guard_check($csrfPos < $confirmPos, 'CSRF validation happens before publish confirmation');
publish_guard_check($confirmPos < $writePos, 'publish confirmation happens before any content write');
publish_guard_check(str_contains($save, 'http_response_code(422)'), 'missing confirmation is rejected as an unprocessable request');
$confirmationNeedle = '($_POST[\'confirm_publish\'] ?? \'\') !== \'1\'';
publish_guard_check(str_contains($save, $confirmationNeedle), 'only the explicit confirmation value is accepted');
publish_guard_check(str_contains($save, 'kcmc_prune_content_backups'), 'automatic backup retention remains in the publish path');
publish_guard_check(str_contains($save, "kcmc_audit('content.published'"), 'successful publishing remains audited');

fwrite(STDOUT, "Publishing review PHP contract passed.\n");
