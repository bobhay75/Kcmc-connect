<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/timeclock.php';

define('KCMC_PAYROLL_SETTINGS', KCMC_PRIVATE_DATA . '/payroll-settings.json');

function kcmc_payroll_default_settings(): array {
    return ['version'=>1,'channel'=>'off','reviewer_id'=>'','review_url'=>'','email_activation_date'=>''];
}
function kcmc_payroll_settings(): array {
    if (!is_file(KCMC_PAYROLL_SETTINGS)) return kcmc_payroll_default_settings();
    $value = kcmc_read_json_store(KCMC_PAYROLL_SETTINGS, kcmc_payroll_default_settings());
    return array_replace(kcmc_payroll_default_settings(), $value);
}
function kcmc_payroll_recipient(?array $settings=null): ?array {
    $settings ??= kcmc_payroll_settings();
    if (!in_array((string)($settings['channel']??''), ['queue','email'], true)) return null;
    $id = trim((string)($settings['reviewer_id']??''));
    if ($id === '') return null;
    $user = kcmc_find_user_by_id($id);
    return is_array($user) && !empty($user['active']) ? $user : null;
}
/** Delegation grants this payroll screen only; it never changes stored roles. */
function kcmc_can_review_payroll(array $user): bool {
    if (kcmc_is_designated_owner($user)) return true;
    if (empty($user['active']) || empty($user['id'])) return false;
    $recipient = kcmc_payroll_recipient();
    return $recipient !== null && hash_equals((string)$recipient['id'], (string)$user['id']);
}
function kcmc_require_payroll_reviewer(): array {
    $user = kcmc_require_login();
    if (!kcmc_can_review_payroll($user)) {
        kcmc_access_denied('Payroll review access is restricted.');
    }
    return $user;
}
function kcmc_payroll_valid_review_url(string $url): bool {
    $parts = parse_url($url);
    return strlen($url)<=500 && filter_var($url,FILTER_VALIDATE_URL)!==false && is_array($parts)
        && ($parts['scheme']??'')==='https' && !empty($parts['host'])
        && !isset($parts['user']) && !isset($parts['pass'])
        && !isset($parts['query']) && !isset($parts['fragment']) && !preg_match('/[\x00-\x20\x7f]/',$url);
}
function kcmc_payroll_valid_activation_date(string $date): bool {
    if(!preg_match('/\A\d{4}-\d{2}-\d{2}\z/',$date))return false;
    $parsed=DateTimeImmutable::createFromFormat('!Y-m-d',$date,new DateTimeZone(KCMC_LOCAL_TIMEZONE));
    return $parsed!==false && $parsed->format('Y-m-d')===$date;
}
function kcmc_payroll_mail_settings(): array {
    $cfg = kcmc_config();
    $envFrom=getenv('KCMC_PAYROLL_FROM');$envName=getenv('KCMC_PAYROLL_FROM_NAME');
    $from=strtolower(trim((string)($envFrom!==false?$envFrom:($cfg['payroll_from']??''))));
    $name=trim((string)($envName!==false?$envName:($cfg['payroll_from_name']??'KCMC Connect')));
    return ['from'=>$from,'from_name'=>$name,'ready'=>$from!==''&&filter_var($from,FILTER_VALIDATE_EMAIL)!==false&&!preg_match('/[\x00-\x20\x7f]/',$from)&&$name!==''&&strlen($name)<=120&&!preg_match('/[\r\n\x00]/',$name)];
}
function kcmc_payroll_save_settings(array $actor,array $input): array {
    $storedActor=kcmc_find_user_by_id((string)($actor['id']??''));
    if (!$storedActor || !kcmc_is_designated_owner($storedActor)) throw new RuntimeException('Only the designated owner can configure payroll.');
    $channel=(string)($input['channel']??'off');$id=trim((string)($input['reviewer_id']??''));$url=trim((string)($input['review_url']??''));
    if (!in_array($channel,['off','queue','email'],true)) throw new RuntimeException('Choose an available payroll delivery channel.');
    if ($channel!=='off') {
        $recipient=kcmc_find_user_by_id($id);
        if (!$recipient || empty($recipient['active'])) throw new RuntimeException('Select an existing active account for payroll review.');
        if ($channel==='email') {
            $email=strtolower(trim((string)($recipient['email']??'')));
            if (!filter_var($email,FILTER_VALIDATE_EMAIL)||preg_match('/[\x00-\x20\x7f]/',$email)) throw new RuntimeException('The selected account needs a valid email address.');
            if (!kcmc_payroll_valid_review_url($url)) throw new RuntimeException('Enter the HTTPS payroll review address without a query or fragment.');
            if (empty(kcmc_payroll_mail_settings()['ready'])) throw new RuntimeException('Configure the server payroll sender before enabling email.');
        }
    }
    return kcmc_update_json_store(KCMC_PAYROLL_SETTINGS,kcmc_payroll_default_settings(),function(array &$settings)use($storedActor,$channel,$id,$url):array{
        $now=gmdate(DATE_ATOM);$activation='';
        if($channel==='email'){
            $previous=(string)($settings['email_activation_date']??'');
            $sameActiveEmail=($settings['channel']??'')==='email'&&($settings['reviewer_id']??'')===$id&&kcmc_payroll_valid_activation_date($previous);
            $activation=$sameActiveEmail?$previous:kcmc_timeclock_local_date($now);
        }
        $settings=array_replace($settings,['version'=>1,'channel'=>$channel,'reviewer_id'=>$channel==='off'?'':$id,'review_url'=>$channel==='email'?$url:'','email_activation_date'=>$activation,'updated_at'=>$now,'updated_by'=>(string)$storedActor['id']]);
        return $settings;
    });
}
/** Stable identity of the resolved store location, not a hash of payroll contents. */
function kcmc_payroll_store_identity(): array {
    clearstatcache(true);
    if (!str_starts_with(KCMC_PRIVATE_DATA,'/')) throw new RuntimeException('The private-store path must be absolute.');
    $walk='';foreach(explode('/',KCMC_PRIVATE_DATA) as $part){
        if($part===''||$part==='.')continue;
        $walk.='/'.$part;$node=@lstat($walk);
        if($node===false||(($node['mode']&0170000)!==0040000))throw new RuntimeException('The private-store path must use ordinary directories without symlinks.');
    }
    $directory=realpath(KCMC_PRIVATE_DATA);
    if ($directory===false || !is_dir($directory)) throw new RuntimeException('The resolved private-store directory is unavailable.');
    $stat=lstat($directory);
    if ($stat===false || (($stat['mode']&0170000)!==0040000) || ($stat['mode']&0700)!==0700 || ($stat['mode']&0022)!==0 || ($stat['mode']&07000)!==0 || $stat['uid']!==fileowner(__FILE__)) throw new RuntimeException('The resolved private-store directory requires review.');
    $path=$directory.'/timeclock.json';clearstatcache(true,$path);$file=@lstat($path);
    if ($file!==false && (($file['mode']&0170000)!==0100000 || $file['nlink']!==1 || $file['uid']!==$stat['uid'] || ($file['mode']&0600)!==0600 || ($file['mode']&0022)!==0)) throw new RuntimeException('The time-clock store metadata requires review.');
    $parts=['kcmc-payroll-store-v1',$path,(string)$stat['dev'],(string)$stat['ino'],(string)$stat['uid'],(string)$stat['gid'],(string)($stat['mode']&07777)];
    return ['version'=>1,'fingerprint'=>hash('sha256',implode("\0",$parts)),'private_directory'=>$directory,'timeclock_path'=>$path,'store_exists'=>$file!==false,'directory_mode'=>sprintf('%04o',$stat['mode']&07777)];
}
function kcmc_payroll_expect_store(string $expected): array {
    if (!preg_match('/\A[a-f0-9]{64}\z/',$expected)) throw new RuntimeException('A valid expected store fingerprint is required.');
    $identity=kcmc_payroll_store_identity();
    if (!hash_equals($identity['fingerprint'],$expected)) throw new RuntimeException('The CLI private store does not match the owner-reviewed web store.');
    if ($identity['directory_mode']!=='0750') throw new RuntimeException('Capture the store fingerprint from authenticated owner payroll setup before scheduling this runner.');
    return $identity;
}
function kcmc_payroll_shell_quote(string $argument): string {
    if (preg_match('/[\r\n\x00]/',$argument)) throw new RuntimeException('The cron command contains an unsupported path.');
    return "'".str_replace("'","'\"'\"'",$argument)."'";
}
function kcmc_payroll_cli_candidates(): array {
    $candidates=['/opt/alt/php82/usr/bin/php','/opt/cpanel/ea-php82/root/usr/bin/php','/usr/local/bin/php','/usr/bin/php'];
    if (PHP_SAPI==='cli' && basename(PHP_BINARY)==='php') array_unshift($candidates,PHP_BINARY);
    return array_values(array_unique(array_filter($candidates,static fn($path)=>is_file($path)&&is_executable($path))));
}
/** Returns a reviewable line only. It never calls crontab or activates a schedule. */
function kcmc_payroll_cron_line(string $php): string {
    if (!in_array($php,kcmc_payroll_cli_candidates(),true)) throw new RuntimeException('Select an available PHP command.');
    $identity=kcmc_payroll_store_identity();$script=realpath(__DIR__.'/../admin/timeclock-period-close.php');
    if ($script===false) throw new RuntimeException('The live payroll runner is unavailable.');
    $line='*/15 * * * * umask 077 && KCMC_PRIVATE_DATA_DIR='.kcmc_payroll_shell_quote($identity['private_directory']).' '.kcmc_payroll_shell_quote($php).' -n '.kcmc_payroll_shell_quote($script).' --run --expect-store '.kcmc_payroll_shell_quote($identity['fingerprint']).' >> '.kcmc_payroll_shell_quote($identity['private_directory'].'/payroll-cron.log').' 2>&1';
    // crontab interprets percent before the shell, including inside shell quotes.
    return str_replace('%','\\%',$line);
}

/** Private closed-period totals only; never include correction reasons or bank details. */
function kcmc_payroll_summaries(array $store,?DateTimeImmutable $asOf=null): array {
    $today=($asOf??new DateTimeImmutable('now',new DateTimeZone(KCMC_LOCAL_TIMEZONE)))->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))->format('Y-m-d');
    $groups=[];$names=[];foreach(kcmc_users() as $user)$names[(string)($user['id']??'')]=(string)($user['display_name']??'Employee');
    foreach(($store['periods']??[]) as $period){
        if(!is_array($period)||empty($period['user_id'])||empty($period['start'])||empty($period['end'])||$period['end']>=$today)continue;
        $uid=(string)$period['user_id'];$start=(string)$period['start'];$end=(string)$period['end'];
        try{kcmc_timeclock_validate_period($start,$end);}catch(Throwable $error){continue;}
        $minutes=0;$closed=0;$open=0;
        foreach(($store['entries']??[]) as $entry){
            if(!is_array($entry)||($entry['user_id']??'')!==$uid||($entry['work_date']??'')<$start||($entry['work_date']??'')>$end)continue;
            if(($entry['status']??'')==='open'||empty($entry['clock_out_at']))$open++;else{$minutes+=(int)($entry['net_minutes']??0);$closed++;}
        }
        $key=$start.'|'.$end;
        if(!isset($groups[$key]))$groups[$key]=['start'=>$start,'end'=>$end,'employees'=>[]];
        $groups[$key]['employees'][$uid]=['user_id'=>$uid,'name'=>$names[$uid]??'Former employee','minutes'=>$minutes,'completed_shifts'=>$closed,'open_shifts'=>$open,'correction_count'=>(int)($period['correction_count']??0)];
    }
    ksort($groups);
    foreach($groups as &$group){
        ksort($group['employees']);$signature=[];
        foreach($group['employees'] as $employee){$row=$employee;unset($row['name']);$signature[]=$row;}
        $group['revision']=hash('sha256',json_encode([$group['start'],$group['end'],$signature],JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR));
    }unset($group);
    return array_values($groups);
}
function kcmc_payroll_email(array $summary,array $recipient,array $settings,?callable $transport=null): array {
    $mail=kcmc_payroll_mail_settings();$to=strtolower(trim((string)($recipient['email']??'')));
    if(empty($mail['ready'])||!filter_var($to,FILTER_VALIDATE_EMAIL)||preg_match('/[\x00-\x20\x7f]/',$to)||!kcmc_payroll_valid_review_url((string)($settings['review_url']??'')))return ['sent'=>false,'reason'=>'not_configured'];
    $subject='KCMC payroll totals: '.$summary['start'].' through '.$summary['end'];
    $lines=['A closed KCMC pay period is ready for payroll review.','Period: '.$summary['start'].' through '.$summary['end'],''];
    $minutes=0;$open=0;
    foreach($summary['employees'] as $employee){
        $name=preg_replace('/[\r\n\x00-\x1f\x7f]/',' ',(string)$employee['name']);
        $lines[]=$name.': '.number_format($employee['minutes']/60,2,'.','').' hours; '.$employee['completed_shifts'].' completed shift(s); '.$employee['open_shifts'].' open shift(s).';
        $minutes+=$employee['minutes'];$open+=$employee['open_shifts'];
    }
    $lines[]='';$lines[]='Total completed time: '.number_format($minutes/60,2,'.','').' hours.';
    if($open)$lines[]='Open shifts need attention. Their unfinished time is excluded; no clock-out time has been invented.';
    $lines[]='Review the private time cards: '.$settings['review_url'];
    $lines[]='This is a time-total notification, not a payment or payroll submission.';
    $body=implode("\n",$lines);if(strlen($body)>50000)return ['sent'=>false,'reason'=>'summary_too_large'];
    $headers=['From: '.$mail['from_name'].' <'.$mail['from'].'>','Reply-To: '.$mail['from'],'Content-Type: text/plain; charset=UTF-8','X-Mailer: KCMC Connect'];
    $sender=$transport??static fn(string $email,string $title,string $message,array $mailHeaders):bool=>mail($email,$title,$message,$mailHeaders,'-f'.$mail['from']);
    try{$sent=$sender($to,$subject,$body,$headers)===true;}catch(Throwable $error){return ['sent'=>false,'reason'=>'transport_exception'];}
    return ['sent'=>$sent,'reason'=>$sent?'accepted_by_mail_transport':'transport_failed'];
}
class KcmcPayrollNoClaim extends RuntimeException {}

/** Claims each revision once before transport. A crash/uncertain delivery never auto-resends. */
function kcmc_payroll_handoff(string $expectedStore,?callable $transport=null): array {
    kcmc_payroll_expect_store($expectedStore);
    $settings=kcmc_payroll_settings();$recipient=kcmc_payroll_recipient($settings);
    if($recipient===null)return ['channel'=>'off','ready'=>false,'accepted'=>0,'failed'=>0,'pending_review'=>0];
    if(($settings['channel']??'')==='queue')return ['channel'=>'queue','ready'=>true,'accepted'=>0,'failed'=>0,'pending_review'=>0];
    $activation=(string)($settings['email_activation_date']??'');
    if(!kcmc_payroll_valid_activation_date($activation))throw new RuntimeException('Save owner payroll setup again to establish the email activation date.');
    if(empty(kcmc_payroll_mail_settings()['ready'])||!kcmc_payroll_valid_review_url((string)($settings['review_url']??'')))throw new RuntimeException('Payroll email sender or review address is not configured.');
    $recipientEmail=strtolower(trim((string)($recipient['email']??'')));
    if(!filter_var($recipientEmail,FILTER_VALIDATE_EMAIL)||preg_match('/[\x00-\x20\x7f]/',$recipientEmail))throw new RuntimeException('The selected payroll account needs a valid email address.');
    $result=['channel'=>'email','ready'=>true,'accepted'=>0,'failed'=>0,'pending_review'=>0];
    $summaries=array_values(array_filter(kcmc_payroll_summaries(kcmc_timeclock_store()),static fn($summary)=>$summary['end']>=$activation));
    foreach($summaries as $summary){
        kcmc_payroll_expect_store($expectedStore);
        $current=kcmc_payroll_settings();$currentRecipient=kcmc_payroll_recipient($current);
        if($currentRecipient===null||($current['channel']??'')!=='email'||$current!==$settings||$currentRecipient['id']!==$recipient['id'])throw new RuntimeException('Payroll delivery settings changed; review the next scheduled run.');
        $to=strtolower(trim((string)($recipient['email']??'')));$id=hash('sha256',$summary['revision']."\0".(string)$recipient['id']."\0".$to);
        $attempt=kcmc_random_id('payroll');
        try{$claim=kcmc_update_json_store(KCMC_TIMECLOCK,kcmc_timeclock_default_store(),function(array &$store)use($id,$summary,$recipient,$to,$attempt):bool{
            if(array_key_exists('payroll_deliveries',$store)&&!is_array($store['payroll_deliveries']))throw new RuntimeException('Payroll delivery history requires private review.');
            $store['payroll_deliveries']=$store['payroll_deliveries']??[];
            foreach($store['payroll_deliveries'] as $delivery){
                if(!is_array($delivery)||!preg_match('/\A[a-f0-9]{64}\z/',(string)($delivery['id']??''))||!in_array((string)($delivery['status']??''),['sending','accepted','failed'],true))throw new RuntimeException('Payroll delivery history requires private review.');
                if($delivery['id']===$id)throw new KcmcPayrollNoClaim();
            }
            // Re-read the actual locked totals; never mail a stale pre-lock summary.
            $fresh=null;foreach(kcmc_payroll_summaries($store) as $candidate)if($candidate['start']===$summary['start']&&$candidate['end']===$summary['end'])$fresh=$candidate;
            if($fresh===null||$fresh['revision']!==$summary['revision'])throw new KcmcPayrollNoClaim();
            $store['payroll_deliveries'][]=['id'=>$id,'revision'=>$summary['revision'],'start'=>$summary['start'],'end'=>$summary['end'],'recipient_id'=>(string)$recipient['id'],'recipient_email'=>$to,'status'=>'sending','attempt_id'=>$attempt,'started_at'=>gmdate(DATE_ATOM),'finished_at'=>null,'reason'=>null];
            return true;
        });}catch(KcmcPayrollNoClaim $noClaim){continue;}
        kcmc_payroll_expect_store($expectedStore);
        $beforeSend=kcmc_payroll_recipient();
        if(kcmc_payroll_settings()!==$settings||$beforeSend===null||$beforeSend['id']!==$recipient['id']||strtolower(trim((string)($beforeSend['email']??'')))!==$to)throw new RuntimeException('Payroll recipient changed after the claim; the pending attempt requires private review.');
        $delivery=kcmc_payroll_email($summary,$recipient,$settings,$transport);
        kcmc_payroll_expect_store($expectedStore);
        kcmc_update_json_store(KCMC_TIMECLOCK,kcmc_timeclock_default_store(),function(array &$store)use($id,$attempt,$delivery):void{
            foreach($store['payroll_deliveries'] as &$record)if(is_array($record)&&($record['id']??'')===$id&&($record['attempt_id']??'')===$attempt&&($record['status']??'')==='sending'){$record['status']=$delivery['sent']?'accepted':'failed';$record['reason']=$delivery['reason'];$record['finished_at']=gmdate(DATE_ATOM);}unset($record);
        });
        $result[$delivery['sent']?'accepted':'failed']++;
    }
    foreach(kcmc_timeclock_store()['payroll_deliveries']??[] as $record)if(is_array($record)&&($record['recipient_id']??'')===(string)$recipient['id']&&in_array((string)($record['status']??''),['sending','failed'],true))$result['pending_review']++;
    return $result;
}
