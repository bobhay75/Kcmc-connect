<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

/** An administrator role alone never grants access to owner operations. */
function kcmc_require_operations_owner(): array {
    $user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
    $ownerId = trim((string)(getenv('KCMC_OPERATIONS_OWNER_USER_ID') ?: ''));
    if ($ownerId === '' || !hash_equals($ownerId, (string)($user['id'] ?? ''))) {
        kcmc_private_headers();
        http_response_code(403);
        exit('Operations access is restricted to the designated owner.');
    }
    return $user;
}
