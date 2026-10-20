<?php
/** CLI-only read-only configuration summary. Never sends mail or prints secrets. */
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
if (function_exists('posix_geteuid') && posix_geteuid() !== 2162) {
    fwrite(STDERR,"Run in the bobsome1 cPanel Terminal.\n");exit(1);
}
$root='/home/bobsome1/public_html/kcmc-connect';
require $root.'/lib/bootstrap.php';
require $root.'/lib/visitor-welcome.php';
$settings=kcmc_visitor_welcome_settings();
$sendmail=trim((string)ini_get('sendmail_path'));
echo json_encode([
    'scope'=>'CLI configuration only; Apache-only environment settings may differ',
    'welcome_enabled'=>(bool)$settings['enabled'],
    'sender_configured'=>kcmc_visitor_welcome_email_valid((string)$settings['from']),
    'settings_ready'=>(bool)$settings['ready'],
    'php_mail_available'=>function_exists('mail'),
    'sendmail_path_configured'=>$sendmail!=='',
    'transport_attempted'=>false,
    'inbox_delivery_verified'=>false,
    'writes_performed'=>false,
],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES)."\n";
