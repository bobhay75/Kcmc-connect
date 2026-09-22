<?php
declare(strict_types=1);

function mobile_check(bool $condition, string $message): void {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
    echo "PASS: {$message}\n";
}

$connections = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/connections.php');
$rsvps = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/rsvps.php');
foreach (['connections'=>$connections,'rsvps'=>$rsvps] as $name=>$page) {
    mobile_check(is_string($page) && str_contains($page, "kcmc_require_role(['pastor_admin', 'recovery_admin'])"), "$name remains administrator-only");
    mobile_check(str_contains((string)$page, 'kcmc_private_headers()'), "$name remains private/no-store");
    mobile_check(str_contains((string)$page, '@media(max-width:760px)'), "$name has explicit phone breakpoint");
    mobile_check(str_contains((string)$page, '.row.head{display:none}'), "$name hides desktop table heading on phones");
    mobile_check(str_contains((string)$page, '.row{display:block;min-width:0'), "$name converts wide rows into phone cards");
    mobile_check(str_contains((string)$page, '.row>span::before'), "$name adds labels to mobile card fields");
    mobile_check(str_contains((string)$page, '.table{overflow:visible}'), "$name removes horizontal table scroller on phones");
    mobile_check(str_contains((string)$page, '.status-form{flex-wrap:wrap}'), "$name keeps follow-up controls usable at narrow widths");
    mobile_check(str_contains((string)$page, 'Download this view as CSV'), "$name keeps CSV download visible");
    mobile_check(str_contains((string)$page, ':focus-visible'), "$name retains visible keyboard focus styling");
}
mobile_check(str_contains((string)$connections, "content:'Type'") && str_contains((string)$connections, "content:'Follow-up'"), 'connection mobile cards label first and last fields');
mobile_check(str_contains((string)$rsvps, "content:'Event'") && str_contains((string)$rsvps, "content:'Follow-up'"), 'RSVP mobile cards label first and last fields');
echo "Mobile private inbox contract checks passed.\n";
