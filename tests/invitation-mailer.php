<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/invitation-mailer.php';

$delivery = [
    'email' => 'dana@example.invalid',
    'subject' => 'Your KCMC Connect invitation',
    'link' => 'https://bobsome1.com/kcmc-connect/member/activate.php?token=' . str_repeat('a', 64),
];
$delivery['message'] = "Hi Dana,\n\n{$delivery['link']}\n";

$passed = 0;
function check_mail(bool $ok, string $name): void {
    global $passed;
    if (!$ok) throw new RuntimeException('FAIL: ' . $name);
    $passed++;
    echo "PASS: {$name}\n";
}

$called = 0;
$fake = static function (string $to, string $subject, string $message, array $headers) use (&$called): bool {
    $called++;
    check_mail($to === 'dana@example.invalid', 'transport receives exact recipient');
    check_mail($subject === 'Your KCMC Connect invitation', 'transport receives exact subject');
    check_mail(str_contains($message, 'token='), 'transport receives invitation body');
    check_mail(isset($headers['From'], $headers['Reply-To'], $headers['Content-Type']), 'transport receives constrained headers');
    return true;
};

$r = kcmc_send_invitation_email($delivery, $fake, ['enabled' => false, 'from' => 'connect@example.org', 'from_name' => 'KCMC Connect']);
check_mail(!$r['sent'] && $r['reason'] === 'not_configured' && $called === 0, 'disabled mail never invokes transport');

$r = kcmc_send_invitation_email($delivery, $fake, ['enabled' => true, 'from' => 'bad address', 'from_name' => 'KCMC Connect']);
check_mail(!$r['sent'] && $r['reason'] === 'not_configured' && $called === 0, 'invalid sender fails closed');

$r = kcmc_send_invitation_email($delivery, $fake, ['enabled' => true, 'from' => 'connect@example.org', 'from_name' => 'KCMC Connect']);
check_mail($r['sent'] && $r['reason'] === 'sent' && $called === 1, 'configured explicit send uses injected transport once');

$bad = $delivery;
$bad['subject'] = "Invite\r\nBcc: attacker@example.invalid";
$r = kcmc_send_invitation_email($bad, $fake, ['enabled' => true, 'from' => 'connect@example.org', 'from_name' => 'KCMC Connect']);
check_mail(!$r['sent'] && $r['reason'] === 'invalid_delivery' && $called === 1, 'header injection is rejected before transport');

$bad = $delivery;
$bad['message'] = 'message without its bound link';
$r = kcmc_send_invitation_email($bad, $fake, ['enabled' => true, 'from' => 'connect@example.org', 'from_name' => 'KCMC Connect']);
check_mail(!$r['sent'] && $r['reason'] === 'invalid_delivery' && $called === 1, 'message must contain its bound invitation link');

$throwing = static function (): bool { throw new RuntimeException('synthetic'); };
$r = kcmc_send_invitation_email($delivery, $throwing, ['enabled' => true, 'from' => 'connect@example.org', 'from_name' => 'KCMC Connect']);
check_mail(!$r['sent'] && $r['reason'] === 'transport_exception', 'transport exception fails closed');

// Simulate the preserved cPanel config.php path without touching a real config file.
if (!function_exists('kcmc_config')) {
    function kcmc_config(): array {
        return [
            'invitation_mail_enabled' => true,
            'invitation_from' => 'cpanel@example.org',
            'invitation_from_name' => 'KCMC Mail',
        ];
    }
}
putenv('KCMC_INVITATION_MAIL_ENABLED');
putenv('KCMC_INVITATION_FROM');
putenv('KCMC_INVITATION_FROM_NAME');
$settings = kcmc_invitation_mail_settings();
check_mail($settings['ready'] && $settings['from'] === 'cpanel@example.org' && $settings['from_name'] === 'KCMC Mail', 'preserved cPanel config can enable direct mail');
putenv('KCMC_INVITATION_MAIL_ENABLED=0');
$settings = kcmc_invitation_mail_settings();
check_mail(!$settings['ready'], 'environment setting overrides preserved cPanel config');
putenv('KCMC_INVITATION_MAIL_ENABLED');

echo "Invitation mailer checks passed: {$passed}\n";
