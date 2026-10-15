<?php
declare(strict_types=1);
/** Store-bound period-end queue. HTTP execution never loads the application. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require_once dirname(__DIR__) . '/lib/payroll.php';
try {
    $arguments=array_slice($argv,1);
    if($arguments===['--diagnose']){
        fwrite(STDOUT,json_encode(kcmc_payroll_store_identity(),JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)."\n");
        exit(0);
    }
    if(count($arguments)!==3||$arguments[0]!=='--run'||$arguments[1]!=='--expect-store')throw new RuntimeException('Use --diagnose, or --run --expect-store followed by the owner-reviewed fingerprint.');
    $expected=$arguments[2];kcmc_payroll_expect_store($expected);
    $count=kcmc_timeclock_close_due_periods();
    if($count>0)kcmc_audit('timeclock.periods_queued',['action'=>'period_end','count'=>$count]);
    kcmc_payroll_expect_store($expected);$handoff=kcmc_payroll_handoff($expected);kcmc_payroll_expect_store($expected);
    kcmc_update_json_store(KCMC_PRIVATE_DATA.'/payroll-run-status.json',[],function(array &$receipt)use($expected,$count,$handoff):void{
        $receipt=['version'=>1,'finished_at'=>gmdate(DATE_ATOM),'store_fingerprint'=>$expected,'periods_updated'=>$count,'channel'=>$handoff['channel'],'mail_accepted'=>$handoff['accepted'],'mail_failed'=>$handoff['failed'],'mail_pending_review'=>$handoff['pending_review']];
    });
    fwrite(STDOUT,'PAY_PERIOD_QUEUE updated='.$count.' channel='.$handoff['channel'].' mail_accepted='.$handoff['accepted'].' mail_failed='.$handoff['failed'].' pending_review='.$handoff['pending_review']."; no payment or payroll-provider submission.\n");
}catch(Throwable $error){
    // Metadata-only operator guidance: no private totals, addresses, or raw transport errors.
    $reason=$error instanceof RuntimeException?$error->getMessage():'Payroll runner stopped; review the private settings and receipt.';
    fwrite(STDERR,'PAY_PERIOD_QUEUE refused: '.$reason."\n");exit(1);
}
