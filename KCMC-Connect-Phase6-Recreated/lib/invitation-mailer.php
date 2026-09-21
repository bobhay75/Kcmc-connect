<?php
declare(strict_types=1);

/**
 * Server-side invitation email transport.
 *
 * Sending is fail-closed: both KCMC_INVITATION_MAIL_ENABLED=1 and a valid
 * KCMC_INVITATION_FROM address are required. Tests inject a fake transport;
 * production falls back to PHP mail() only after explicit configuration.
 */
function kcmc_invitation_mail_settings(?array $override = null): array {
    if ($override !== null) {
        $enabled = !empty($override['enabled']);
        $from = strtolower(trim((string)($override['from'] ?? '')));
        $name = trim((string)($override['from_name'] ?? 'KCMC Connect'));
    } else {
        $enabled = trim((string)(getenv('KCMC_INVITATION_MAIL_ENABLED') ?: '')) === '1';
        $from = strtolower(trim((string)(getenv('KCMC_INVITATION_FROM') ?: '')));
        $name = trim((string)(getenv('KCMC_INVITATION_FROM_NAME') ?: 'KCMC Connect'));
    }

    $validFrom = $from !== '' && filter_var($from, FILTER_VALIDATE_EMAIL) &&
        !preg_match('/[\x00-\x20\x7f]/', $from);
    $validName = $name !== '' && strlen($name) <= 120 &&
        !preg_match('/[\r\n\x00]/', $name);

    return [
        'enabled' => $enabled,
        'from' => $from,
        'from_name' => $name,
        'ready' => $enabled && $validFrom && $validName,
    ];
}

function kcmc_invitation_mail_ready(?array $override = null): bool {
    return !empty(kcmc_invitation_mail_settings($override)['ready']);
}

/**
 * @return array{sent:bool,reason:string}
 */
function kcmc_send_invitation_email(array $delivery, ?callable $transport = null, ?array $settingsOverride = null): array {
    $settings = kcmc_invitation_mail_settings($settingsOverride);
    if (empty($settings['ready'])) return ['sent' => false, 'reason' => 'not_configured'];

    $to = strtolower(trim((string)($delivery['email'] ?? '')));
    $subject = trim((string)($delivery['subject'] ?? ''));
    $message = (string)($delivery['message'] ?? '');
    $link = (string)($delivery['link'] ?? '');

    if (!filter_var($to, FILTER_VALIDATE_EMAIL) || preg_match('/[\x00-\x20\x7f]/', $to) ||
        $subject === '' || strlen($subject) > 180 || preg_match('/[\r\n\x00]/', $subject) ||
        $message === '' || strlen($message) > 12000 || preg_match('/\x00/', $message) ||
        $link === '' || !str_contains($message, $link)) {
        return ['sent' => false, 'reason' => 'invalid_delivery'];
    }

    $headers = [
        'From' => $settings['from_name'] . ' <' . $settings['from'] . '>',
        'Reply-To' => $settings['from'],
        'Content-Type' => 'text/plain; charset=UTF-8',
        'X-Mailer' => 'KCMC Connect',
    ];

    $sender = $transport ?? static function (string $recipient, string $mailSubject, string $body, array $mailHeaders): bool {
        return mail($recipient, $mailSubject, $body, $mailHeaders);
    };

    try {
        $sent = $sender($to, $subject, $message, $headers) === true;
    } catch (Throwable $e) {
        return ['sent' => false, 'reason' => 'transport_exception'];
    }

    return $sent
        ? ['sent' => true, 'reason' => 'sent']
        : ['sent' => false, 'reason' => 'transport_failed'];
}
