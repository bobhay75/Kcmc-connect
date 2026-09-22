<?php
declare(strict_types=1);

function ops_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$hub = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/operations.php');
$desk = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/index.php');
ops_check(is_string($hub), 'operations hub is readable');
ops_check(str_contains((string)$hub, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'operations hub is administrator-only');
ops_check(str_contains((string)$hub, 'kcmc_private_headers()'), 'operations hub is private/no-store');
foreach (['admin/health.php','admin/audit.php','admin/push.php','admin/backup.php','admin/restore.php'] as $path) {
    ops_check(str_contains((string)$hub, $path), "operations hub links $path");
}
ops_check(str_contains((string)$hub, '@media(max-width:720px)'), 'operations hub has a phone layout');
ops_check(str_contains((string)$hub, ':focus-visible'), 'operations hub retains visible keyboard focus');
ops_check(!str_contains((string)$hub, 'push_vapid_private') && !str_contains((string)$hub, 'token_hash'), 'operations hub does not render secret configuration material');
ops_check(is_string($desk) && str_contains($desk, "admin/operations.php"), 'Publishing Desk exposes the Operations hub');
ops_check(str_contains((string)$desk, '>Operations</a>'), 'Publishing Desk labels the Operations link clearly');
echo "Operations hub contract checks passed.\n";
