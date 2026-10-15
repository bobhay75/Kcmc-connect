<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/team-workspace.php';
kcmc_private_headers(); header('Content-Type: application/json; charset=utf-8'); header('X-Content-Type-Options: nosniff');
try {
    $method=strtoupper((string)($_SERVER['REQUEST_METHOD']??'GET'));
    if (!in_array($method,['GET','POST'],true)) { header('Allow: GET, POST'); kcmc_team_fail('Method not allowed.',405,'method_not_allowed'); }
    $user=kcmc_session_cookie_present()?kcmc_current_user($method==='POST'):null;
    if (!$user) kcmc_team_fail('Sign in to continue.',401,'authentication_required');
    if ($method==='GET') {
        // Polls neither prolong idle expiry nor retain the session lock during I/O.
        session_write_close(); $action=$_GET['action']??'list';
        if ($action==='list') $result=kcmc_team_list($user);
        elseif ($action==='thread' && is_string($_GET['kind']??null) && is_string($_GET['id']??null)) $result=kcmc_team_thread($user,$_GET['kind'],$_GET['id']);
        else kcmc_team_fail('Choose a valid view.');
    } else {
        if ((int)($_SERVER['CONTENT_LENGTH']??0)>32768) kcmc_team_fail('This request is too large.',413,'request_too_large');
        $raw=file_get_contents('php://input',false,null,0,32769);
        if (!is_string($raw) || strlen($raw)>32768) kcmc_team_fail('This request is too large.',413,'request_too_large');
        try { $input=json_decode($raw,true,32,JSON_THROW_ON_ERROR); } catch (JsonException) { kcmc_team_fail('Invalid JSON request.'); }
        if (!is_array($input) || !is_string($input['csrf']??null) || !kcmc_verify_csrf($input['csrf'])) kcmc_team_fail('Reload this page before saving.',403,'invalid_csrf');
        $action=$input['action']??null; if (!is_string($action)) kcmc_team_fail('Choose a valid action.');
        // The authenticated actor and CSRF decision are fixed for this request.
        // A contended workspace write must not retain this browser's session lock.
        session_write_close();
        $result=kcmc_team_mutate($user,$action,$input); $changed=$result['_changed']; unset($result['_changed']);
        if ($changed) {
            $metadata=['count'=>1];
            if (isset($result['task'])) $metadata['task_id']=$result['task']['id'];
            if (isset($result['comment'])) $metadata['comment_id']=$result['comment']['id'];
            kcmc_audit('team.'.$action,$metadata);
        }
        if (session_status()===PHP_SESSION_ACTIVE) session_write_close();
    }
    echo json_encode(['ok'=>true]+$result,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
} catch (KcmcTeamError $error) {
    if (session_status()===PHP_SESSION_ACTIVE) session_write_close(); http_response_code($error->status);
    echo json_encode(['ok'=>false,'error'=>$error->getMessage(),'code'=>$error->errorCode],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
} catch (Throwable) {
    if (session_status()===PHP_SESSION_ACTIVE) session_write_close(); http_response_code(503);
    echo json_encode(['ok'=>false,'error'=>'Workspace is temporarily unavailable. Try again later.','code'=>'storage_unavailable']);
}
