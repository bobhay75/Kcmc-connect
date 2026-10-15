<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

/** Isolated staff collaboration; no content, payroll, prayer or account writes. */
final class KcmcTeamError extends RuntimeException {
    public function __construct(string $message, public int $status = 422, public string $errorCode = 'invalid_input') { parent::__construct($message); }
}
const KCMC_TEAM_MAX_BYTES = 8388608;
function kcmc_team_empty(): array { return ['version'=>1,'revision'=>0,'tasks'=>[],'comments'=>[],'preferences'=>[],'nonces'=>[]]; }
function kcmc_team_path(): string { return KCMC_PRIVATE_DATA . '/team-workspace.json'; }
function kcmc_team_fail(string $message, int $status = 422, string $code = 'invalid_input'): never { throw new KcmcTeamError($message,$status,$code); }
function kcmc_team_storage_error(): never { kcmc_team_fail('Workspace storage needs administrator review. No change was saved.',503,'storage_unavailable'); }
function kcmc_team_text(mixed $value, int $max, bool $required = false): string {
    if (!is_string($value) || !preg_match('//u',$value) || str_contains($value,"\0") || kcmc_text_length($value)>$max || ($required && trim($value)==='')) kcmc_team_fail('Check the text length and try again.');
    return $required ? trim($value) : $value;
}
function kcmc_team_date(mixed $value): string {
    if ($value === '') return '';
    if (!is_string($value) || !preg_match('/\A\d{4}-\d{2}-\d{2}\z/',$value)) kcmc_team_fail('Choose a valid date.');
    $date=DateTimeImmutable::createFromFormat('!Y-m-d',$value,new DateTimeZone(KCMC_LOCAL_TIMEZONE));
    if (!$date || $date->format('Y-m-d')!==$value) kcmc_team_fail('Choose a valid date.');
    return $value;
}
function kcmc_team_id(mixed $value, string $prefix): bool { return is_string($value) && preg_match('/\A'.preg_quote($prefix,'/').'_[a-f0-9]{24}\z/',$value)===1; }
function kcmc_team_user(array $user): void {
    if (empty($user['active']) || !is_string($user['id']??null) || $user['id']==='') kcmc_team_fail('Sign in to continue.',401,'authentication_required');
}
function kcmc_team_validate(array $state): void {
    if (($state['version']??null)!==1 || !is_int($state['revision']??null) || $state['revision']<0) kcmc_team_storage_error();
    foreach (['tasks','comments','preferences','nonces'] as $key) if (!is_array($state[$key]??null)) kcmc_team_storage_error();
    if (count($state['tasks'])>500 || count($state['comments'])>5000 || count($state['nonces'])>5000) kcmc_team_storage_error();
    foreach ($state['tasks'] as $id=>$task) {
        if (!is_array($task) || !kcmc_team_id($id,'teamtask') || ($task['id']??null)!==$id || !is_int($task['revision']??null) || $task['revision']<1
            || !is_string($task['assigned_to']??null) || !is_string($task['created_by']??null) || !is_string($task['updated_by']??null)
            || !is_int($task['created_at']??null) || !is_int($task['updated_at']??null) || !is_bool($task['blocked']??null)
            || !in_array($task['priority']??null,['low','normal','high'],true) || !in_array($task['status']??null,['open','in_progress','done'],true)
            || !is_string($task['publication_id']??null) || ($task['publication_id']!=='' && !kcmc_team_id($task['publication_id'],'pub'))) kcmc_team_storage_error();
        try {
            kcmc_team_text($task['title']??null,160,true); kcmc_team_text($task['body']??null,4000);
            kcmc_team_text($task['assigned_to'],120); kcmc_team_text($task['created_by'],120,true); kcmc_team_text($task['updated_by'],120,true);
            kcmc_team_date($task['start_date']??null); kcmc_team_date($task['due_date']??null);
        }
        catch (KcmcTeamError) { kcmc_team_storage_error(); }
        if ($task['start_date']!=='' && $task['due_date']!=='' && $task['start_date']>$task['due_date']) kcmc_team_storage_error();
    }
    foreach ($state['comments'] as $id=>$comment) {
        if (!is_array($comment) || !kcmc_team_id($id,'teamcomment') || ($comment['id']??null)!==$id || !is_array($comment['context']??null)
            || !in_array($comment['context']['kind']??null,['task','publication'],true) || !is_string($comment['author_id']??null) || !is_string($comment['parent_id']??null)
            || !is_int($comment['created_at']??null) || !kcmc_team_id($comment['context']['id']??null,$comment['context']['kind']==='task'?'teamtask':'pub')) kcmc_team_storage_error();
        try { kcmc_team_text($comment['body']??null,2000,true); kcmc_team_text($comment['author_id'],120,true); } catch (KcmcTeamError) { kcmc_team_storage_error(); }
        if ($comment['context']['kind']==='task' && !isset($state['tasks'][$comment['context']['id']])) kcmc_team_storage_error();
        if ($comment['parent_id']!=='') {
            $parent=$state['comments'][$comment['parent_id']]??null;
            if (!is_array($parent) || ($parent['context']??null)!==$comment['context'] || ($parent['id']??null)===$id) kcmc_team_storage_error();
            $seen=[$id=>true]; $cursor=$parent;
            while ($cursor) {
                if (!is_string($cursor['id']??null) || !is_string($cursor['parent_id']??null) || ($cursor['context']??null)!==$comment['context']) kcmc_team_storage_error();
                if (isset($seen[$cursor['id']])) kcmc_team_storage_error(); $seen[$cursor['id']]=true;
                $cursor=$cursor['parent_id']===''?null:($state['comments'][$cursor['parent_id']]??null);
            }
        }
    }
    foreach ($state['preferences'] as $uid=>$prefs) {
        if ((string)$uid==='' || !is_array($prefs) || !is_int($prefs['revision']??null) || $prefs['revision']<1
            || !in_array($prefs['view']??null,['list','board','timeline'],true) || !in_array($prefs['sort']??null,['smart','due','priority'],true)
            || !in_array($prefs['statusfilter']??null,['all','open','done'],true)) kcmc_team_storage_error();
    }
    foreach ($state['nonces'] as $key=>$record) {
        if (!preg_match('/\A[a-f0-9]{64}\z/',(string)$key) || !is_array($record) || !is_string($record['actor_id']??null)
            || !is_string($record['fingerprint']??null) || !preg_match('/\A[a-f0-9]{64}\z/',$record['fingerprint'])
            || !isset($state['comments'][$record['comment_id']??'']) || $state['comments'][$record['comment_id']]['author_id']!==$record['actor_id']) kcmc_team_storage_error();
    }
}
function kcmc_team_safe_file(array $stat): bool {
    return ($stat['mode']&0170000)===0100000 && $stat['nlink']===1 && ($stat['mode']&0007)===0
        && (!function_exists('posix_geteuid') || $stat['uid']===posix_geteuid());
}
function kcmc_team_read(): array {
    $path=kcmc_team_path(); clearstatcache(true,$path); $before=@lstat($path);
    if ($before===false) return kcmc_team_empty();
    if (!kcmc_team_safe_file($before) || $before['size']>KCMC_TEAM_MAX_BYTES) kcmc_team_storage_error();
    $handle=@fopen($path,'rb'); if (!$handle) kcmc_team_storage_error();
    try {
        $stat=fstat($handle);
        if (!$stat || !kcmc_team_safe_file($stat) || $stat['ino']!==$before['ino'] || $stat['dev']!==$before['dev']) kcmc_team_storage_error();
        $raw=stream_get_contents($handle,KCMC_TEAM_MAX_BYTES+1);
    } finally { fclose($handle); }
    if (!is_string($raw) || strlen($raw)>KCMC_TEAM_MAX_BYTES) kcmc_team_storage_error();
    try { $state=json_decode($raw,true,64,JSON_THROW_ON_ERROR); } catch (JsonException) { kcmc_team_storage_error(); }
    if (!is_array($state)) kcmc_team_storage_error(); kcmc_team_validate($state); return $state;
}
function kcmc_team_transaction(callable $callback): array {
    kcmc_ensure_private_storage(); $path=kcmc_team_path(); $lockPath=$path.'.lock';
    clearstatcache(true,$lockPath); $existing=@lstat($lockPath);
    if ($existing!==false && !kcmc_team_safe_file($existing)) kcmc_team_storage_error();
    $lock=@fopen($lockPath,'c+'); if (!$lock) kcmc_team_storage_error();
    $tmp=null;
    try {
        $stat=fstat($lock); if (!$stat || ($stat['mode']&0170000)!==0100000 || $stat['nlink']!==1 || (function_exists('posix_geteuid') && $stat['uid']!==posix_geteuid()) || !chmod($lockPath,0640)) kcmc_team_storage_error();
        if (!flock($lock,LOCK_EX)) kcmc_team_storage_error();
        clearstatcache(true,$lockPath); $current=@lstat($lockPath);
        if (!$current || $current['ino']!==$stat['ino'] || $current['dev']!==$stat['dev'] || !kcmc_team_safe_file($current)) kcmc_team_storage_error();
        $state=kcmc_team_read(); $before=$state; $result=$callback($state);
        if ($state===$before) return $result+['_changed'=>false];
        $state['revision']++; kcmc_team_validate($state);
        try { $raw=json_encode($state,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR)."\n"; } catch (JsonException) { kcmc_team_storage_error(); }
        if (strlen($raw)>KCMC_TEAM_MAX_BYTES) kcmc_team_fail('This workspace is full. Ask an administrator to review it.',503,'workspace_full');
        $tmp=$path.'.tmp-'.bin2hex(random_bytes(12)); $output=@fopen($tmp,'x+b'); if (!$output) kcmc_team_storage_error();
        try {
            if (!chmod($tmp,0640)) kcmc_team_storage_error();
            $offset=0; while ($offset<strlen($raw)) { $written=fwrite($output,substr($raw,$offset)); if ($written===false || $written===0) kcmc_team_storage_error(); $offset+=$written; }
            if (!fflush($output)) kcmc_team_storage_error(); if (function_exists('fsync') && !fsync($output)) kcmc_team_storage_error();
        } finally { fclose($output); }
        if (!@rename($tmp,$path)) kcmc_team_storage_error(); $tmp=null;
        return $result+['_changed'=>true];
    } finally { if ($tmp!==null) @unlink($tmp); flock($lock,LOCK_UN); fclose($lock); }
}
function kcmc_team_publications(): array {
    $path=KCMC_PRIVATE_DATA.'/publications.json';
    clearstatcache(true,$path); $stat=@lstat($path); if ($stat===false) return [];
    if (($stat['mode']&0170000)!==0100000 || $stat['nlink']!==1 || $stat['size']>KCMC_TEAM_MAX_BYTES) kcmc_team_fail('Publication storage needs administrator review.',503,'storage_unavailable');
    $raw=@file_get_contents($path); $store=is_string($raw)?json_decode($raw,true):null;
    if (!is_array($store) || !in_array($store['version']??null,[1,2],true) || !is_array($store['projects']??null)) kcmc_team_fail('Publication storage needs administrator review.',503,'storage_unavailable');
    $result=[]; foreach ($store['projects'] as $project) {
        if (!is_array($project) || !kcmc_team_id($project['id']??null,'pub') || !is_string($project['name']??null) || isset($result[$project['id']])) kcmc_team_fail('Publication storage needs administrator review.',503,'storage_unavailable');
        $result[$project['id']]=['id'=>$project['id'],'name'=>$project['name']];
    }
    return $result;
}
function kcmc_team_people(): array {
    $people=[]; foreach (kcmc_users() as $account) if (is_array($account) && !empty($account['active']) && is_string($account['id']??null) && $account['id']!=='') {
        $people[$account['id']]=['id'=>$account['id'],'name'=>(string)($account['display_name']??'KCMC account')];
    }
    uasort($people,static fn($a,$b)=>[strtolower($a['name']),$a['id']]<=>[strtolower($b['name']),$b['id']]); return $people;
}
function kcmc_team_can_task(array $user,array $task): bool { return kcmc_can_publish($user) || ($task['assigned_to']!=='' && $task['assigned_to']===$user['id']); }
/** Navigation only: do not create stores or disrupt Account when workspace is unavailable. */
function kcmc_team_has_assigned_tasks(array $user): bool {
    if (empty($user['active']) || !is_string($user['id']??null) || $user['id']==='') return false;
    try { $state=kcmc_team_read(); } catch (KcmcTeamError) { return false; }
    foreach ($state['tasks'] as $task) if ($task['assigned_to']===$user['id']) return true;
    return false;
}
function kcmc_team_context(array $state,array $user,string $kind,string $id): array {
    if ($kind==='task' && isset($state['tasks'][$id]) && kcmc_team_can_task($user,$state['tasks'][$id])) return ['kind'=>'task','id'=>$id,'label'=>$state['tasks'][$id]['title']];
    if ($kind==='publication') {
        if (!kcmc_can_publish($user)) kcmc_team_fail('You do not have access to that discussion.',403,'access_denied');
        $publications=kcmc_team_publications(); if (isset($publications[$id])) return ['kind'=>'publication','id'=>$id,'label'=>$publications[$id]['name']];
    }
    kcmc_team_fail('That item is not available.',404,'not_found');
}
function kcmc_team_comment_view(array $comment,array $people): array {
    return ['id'=>$comment['id'],'body'=>$comment['body'],'parent_id'=>$comment['parent_id'],'author_id'=>$comment['author_id'],
        'author_name'=>$people[$comment['author_id']]['name']??'KCMC staff','created_at'=>$comment['created_at']];
}
function kcmc_team_task_view(array $task,array $state,array $user,array $people): array {
    $result=array_intersect_key($task,array_flip(['id','revision','title','body','assigned_to','start_date','due_date','priority','status','blocked','publication_id','created_at','updated_at']));
    if (!kcmc_can_publish($user)) unset($result['publication_id']);
    $result['assignee_name']=$people[$task['assigned_to']]['name']??($task['assigned_to']===''?'Unassigned':'Unavailable account');
    $result['comment_count']=count(array_filter($state['comments'],static fn($c)=>$c['context']['kind']==='task' && $c['context']['id']===$task['id']));
    return $result;
}
/** Open work first; smart then blocked, overdue/today/future/undated, priority, date/id. */
function kcmc_team_sort_tasks(array $tasks,string $sort,string $today): array {
    $key=static function(array $t)use($sort,$today):array {
        $done=$t['status']==='done'?1:0; $priority=['high'=>0,'normal'=>1,'low'=>2][$t['priority']]; $due=$t['due_date'];
        $bucket=$due===''?3:($due<$today?0:($due===$today?1:2)); $date=$due===''?'9999-99-99':$due;
        if ($sort==='priority') return [$done,$priority,$t['blocked']?0:1,$bucket,$date,$t['created_at'],$t['id']];
        if ($sort==='due') return [$done,$bucket,$date,$t['blocked']?0:1,$priority,$t['created_at'],$t['id']];
        return [$done,$t['blocked']?0:1,$bucket,$priority,$date,$t['created_at'],$t['id']];
    };
    usort($tasks,static fn($a,$b)=>$key($a)<=>$key($b)); return $tasks;
}
function kcmc_team_default_preferences(): array { return ['revision'=>0,'view'=>'list','sort'=>'smart','statusfilter'=>'all']; }
function kcmc_team_list(array $user,?string $today=null): array {
    kcmc_team_user($user); $state=kcmc_team_read(); $publisher=kcmc_can_publish($user); $people=kcmc_team_people();
    $prefs=$state['preferences'][$user['id']]??kcmc_team_default_preferences(); $tasks=[];
    foreach ($state['tasks'] as $task) {
        if (!kcmc_team_can_task($user,$task)) continue;
        $tasks[]=kcmc_team_task_view($task,$state,$user,$people);
    }
    $today??=(new DateTimeImmutable('now',new DateTimeZone(KCMC_LOCAL_TIMEZONE)))->format('Y-m-d');
    return ['tasks'=>kcmc_team_sort_tasks($tasks,$prefs['sort'],$today),'users'=>$publisher?array_values($people):[],
        'publications'=>$publisher?array_values(kcmc_team_publications()):[],'preferences'=>$prefs,'can_manage'=>$publisher,'actor_id'=>$user['id'],'server_today'=>$today,'revision'=>$state['revision']];
}
function kcmc_team_thread(array $user,string $kind,string $id): array {
    kcmc_team_user($user); $state=kcmc_team_read(); $context=kcmc_team_context($state,$user,$kind,$id); $people=kcmc_team_people(); $comments=[];
    foreach ($state['comments'] as $comment) if ($comment['context']===['kind'=>$kind,'id'=>$id]) $comments[]=kcmc_team_comment_view($comment,$people);
    usort($comments,static fn($a,$b)=>[$a['created_at'],$a['id']]<=>[$b['created_at'],$b['id']]);
    return ['context'=>$context,'comments'=>$comments,'revision'=>$state['revision']];
}
function kcmc_team_expected(mixed $revision,int $actual): void {
    if (!is_int($revision) || $revision<0) kcmc_team_fail('Reload this item before saving.');
    if ($revision!==$actual) kcmc_team_fail('This item changed. Review the latest version before saving.',409,'revision_conflict');
}
function kcmc_team_task_input(mixed $input): array {
    if (!is_array($input)) kcmc_team_fail('Check the task details.');
    $task=['title'=>kcmc_team_text($input['title']??null,160,true),'body'=>kcmc_team_text($input['body']??'',4000),
        'assigned_to'=>kcmc_team_text($input['assigned_to']??'',120),'start_date'=>kcmc_team_date($input['start_date']??''),'due_date'=>kcmc_team_date($input['due_date']??''),
        'priority'=>$input['priority']??'normal','status'=>$input['status']??'open','blocked'=>$input['blocked']??false,'publication_id'=>$input['publication_id']??''];
    if (!in_array($task['priority'],['low','normal','high'],true) || !in_array($task['status'],['open','in_progress','done'],true) || !is_bool($task['blocked']) || !is_string($task['publication_id'])) kcmc_team_fail('Choose valid task options.');
    if ($task['assigned_to']!=='' && !isset(kcmc_team_people()[$task['assigned_to']])) kcmc_team_fail('Choose an active account for this task.');
    if ($task['publication_id']!=='' && !isset(kcmc_team_publications()[$task['publication_id']])) kcmc_team_fail('Choose an existing publication.');
    if ($task['start_date']!=='' && $task['due_date']!=='' && $task['start_date']>$task['due_date']) kcmc_team_fail('The due date must be on or after the start date.');
    return $task;
}
function kcmc_team_mutate(array $user,string $action,array $input,?int $now=null): array {
    kcmc_team_user($user); $now??=time();
    return kcmc_team_transaction(static function(array &$state)use($user,$action,$input,$now):array {
        $publisher=kcmc_can_publish($user); $uid=$user['id'];
        if (in_array($action,['create','update'],true)) {
            if (!$publisher) kcmc_team_fail('Only publishing administrators can manage tasks.',403,'access_denied');
            $fields=kcmc_team_task_input($input['task']??null);
            if ($action==='create') {
                if (count($state['tasks'])>=500) kcmc_team_fail('This workspace is full. Ask an administrator to review it.',503,'workspace_full');
                $id=kcmc_random_id('teamtask'); $task=$fields+['id'=>$id,'revision'=>1,'created_at'=>$now,'created_by'=>$uid,'updated_at'=>$now,'updated_by'=>$uid];
            } else {
                $id=is_string($input['task_id']??null)?$input['task_id']:''; $old=$state['tasks'][$id]??null;
                if (!$old) kcmc_team_fail('That task is not available.',404,'not_found'); kcmc_team_expected($input['revision']??null,$old['revision']);
                $task=$fields+['id'=>$id,'revision'=>$old['revision']+1,'created_at'=>$old['created_at'],'created_by'=>$old['created_by'],'updated_at'=>$now,'updated_by'=>$uid];
            }
            $state['tasks'][$id]=$task; return ['task'=>kcmc_team_task_view($task,$state,$user,kcmc_team_people())];
        }
        if ($action==='status') {
            $id=is_string($input['task_id']??null)?$input['task_id']:''; $task=$state['tasks'][$id]??null;
            if (!$task || !kcmc_team_can_task($user,$task)) kcmc_team_fail('That task is not available.',404,'not_found');
            kcmc_team_expected($input['revision']??null,$task['revision']); $status=$input['status']??null;
            if (!in_array($status,['open','in_progress','done'],true)) kcmc_team_fail('Choose a valid task status.');
            if ($task['status']!==$status) { $task['status']=$status; $task['revision']++; $task['updated_at']=$now; $task['updated_by']=$uid; $state['tasks'][$id]=$task; }
            return ['task'=>kcmc_team_task_view($task,$state,$user,kcmc_team_people())];
        }
        if ($action==='comment') {
            $context=$input['context']??null; if (!is_array($context) || !is_string($context['kind']??null) || !is_string($context['id']??null)) kcmc_team_fail('Choose a discussion.');
            $checked=kcmc_team_context($state,$user,$context['kind'],$context['id']); $context=['kind'=>$checked['kind'],'id'=>$checked['id']];
            $body=kcmc_team_text($input['body']??null,2000,true); $parent=$input['parent_id']??''; $nonce=$input['nonce']??null;
            if (!is_string($parent) || ($parent!=='' && (!isset($state['comments'][$parent]) || $state['comments'][$parent]['context']!==$context))) kcmc_team_fail('Reply to a message in this discussion.');
            if (!is_string($nonce) || !preg_match('/\A[A-Za-z0-9_-]{16,96}\z/',$nonce)) kcmc_team_fail('Reload this discussion before posting.');
            $key=hash('sha256',$uid."\0".$nonce); $fingerprint=hash('sha256',json_encode([$context,$parent,$body],JSON_THROW_ON_ERROR));
            if (isset($state['nonces'][$key])) {
                $record=$state['nonces'][$key]; if (!hash_equals($record['fingerprint'],$fingerprint)) kcmc_team_fail('That request was already used. Reload the discussion.',409,'nonce_conflict');
                return ['comment'=>kcmc_team_comment_view($state['comments'][$record['comment_id']],kcmc_team_people()),'duplicate'=>true];
            }
            if (count($state['comments'])>=5000) kcmc_team_fail('This workspace is full. Ask an administrator to review it.',503,'workspace_full');
            $id=kcmc_random_id('teamcomment'); $comment=['id'=>$id,'context'=>$context,'body'=>$body,'parent_id'=>$parent,'author_id'=>$uid,'created_at'=>$now];
            $state['comments'][$id]=$comment; $state['nonces'][$key]=['actor_id'=>$uid,'fingerprint'=>$fingerprint,'comment_id'=>$id];
            return ['comment'=>kcmc_team_comment_view($comment,kcmc_team_people()),'duplicate'=>false];
        }
        if ($action==='preferences') {
            $old=$state['preferences'][$uid]??kcmc_team_default_preferences(); kcmc_team_expected($input['revision']??null,$old['revision']); $prefs=$input['preferences']??null;
            if (!is_array($prefs) || array_diff(array_keys($prefs),['view','sort','statusfilter']) || !in_array($prefs['view']??null,['list','board','timeline'],true)
                || !in_array($prefs['sort']??null,['smart','due','priority'],true) || !in_array($prefs['statusfilter']??null,['all','open','done'],true)) kcmc_team_fail('Choose valid workspace preferences.');
            $prefs=['revision'=>$old['revision']+1,'view'=>$prefs['view'],'sort'=>$prefs['sort'],'statusfilter'=>$prefs['statusfilter']]; $state['preferences'][$uid]=$prefs; return ['preferences'=>$prefs];
        }
        kcmc_team_fail('Choose a valid action.');
    });
}
