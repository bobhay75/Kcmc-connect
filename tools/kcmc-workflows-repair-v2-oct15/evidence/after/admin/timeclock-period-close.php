<?php
declare(strict_types=1);
/** Idempotent private payroll review queue. No email, payment, or invented punches. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require_once dirname(__DIR__) . '/lib/timeclock.php';
try {
    $count = kcmc_timeclock_close_due_periods();
    if ($count > 0) kcmc_audit('timeclock.periods_queued', ['action'=>'period_end', 'count'=>$count]);
    fwrite(STDOUT, 'PAY_PERIOD_QUEUE updated=' . $count . "; no email or payment sent.\n");
} catch (Throwable $error) {
    fwrite(STDERR, "PAY_PERIOD_QUEUE failed; existing punches require private administrator review.\n");
    exit(1);
}
