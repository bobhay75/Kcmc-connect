<?php
declare(strict_types=1);

function health_follow_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$page = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/health.php');
health_follow_check(is_string($page), 'Release Health page is readable');
health_follow_check(str_contains((string)$page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), 'Release Health remains administrator-only');
health_follow_check(str_contains((string)$page, 'kcmc_private_headers()'), 'Release Health remains private/no-store');
health_follow_check(str_contains((string)$page, "require_once __DIR__ . '/../lib/inbox-follow-up.php'"), 'Release Health reuses canonical inbox status semantics');
health_follow_check(str_contains((string)$page, 'kcmc_inbox_status_counts(kcmc_connection_recent(300))'), 'Release Health counts connection follow-up states from bounded private rows');
health_follow_check(str_contains((string)$page, 'kcmc_inbox_status_counts(kcmc_event_rsvp_recent(200))'), 'Release Health counts RSVP follow-up states from bounded private rows');
health_follow_check(str_contains((string)$page, "['new']??0"), 'Release Health displays New-state counts');
health_follow_check(str_contains((string)$page, 'admin/rsvps.php?status=new'), 'New RSVP count links to filtered private inbox');
health_follow_check(str_contains((string)$page, 'admin/connections.php?status=new'), 'New connection count links to filtered private inbox');
health_follow_check(str_contains((string)$page, 'Counts only are shown here.'), 'Release Health explains privacy boundary for follow-up counts');
health_follow_check(!str_contains((string)$page, "['email']") && !str_contains((string)$page, "['phone']") && !str_contains((string)$page, "['message']"), 'Release Health follow-up section does not render submitted contact fields');
health_follow_check(str_contains((string)$page, 'admin/operations.php'), 'Release Health returns to Operations hub');
echo "Release Health follow-up count contract checks passed.\n";
