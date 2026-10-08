<?php
declare(strict_types=1);

/** One-time visit receipts, never a subscription or a staff invitation.
 * Production sending requires independent server-only approval/configuration.
 * Tests inject a transport; no browser-provided sender, URL or message is used.
 */
const KCMC_VISITOR_WELCOME_STATE = KCMC_PRIVATE_DATA . '/visitor-welcome-delivery.json';
const KCMC_VISITOR_WELCOME_WINDOW = 86400;

function kcmc_visitor_welcome_email_valid(string $email): bool {
    return strlen($email) <= 254 && filter_var($email, FILTER_VALIDATE_EMAIL) !== false
        && preg_match('/\A[a-z0-9][a-z0-9._+\-]*@[a-z0-9.\-]+\z/i', $email) === 1;
}

function kcmc_visitor_welcome_settings(?array $override = null): array {
    $config = $override ?? kcmc_config();
    $get = static function (string $key, mixed $fallback) use ($config, $override): mixed {
        $env = $override === null ? getenv('KCMC_' . strtoupper($key)) : false;
        return $env !== false ? $env : ($config[$key] ?? $fallback);
    };
    $enabled = in_array($get('visitor_welcome_mail_enabled', false), [true, 1, '1'], true);
    $from = strtolower(trim((string)$get('visitor_welcome_from', $config['invitation_from'] ?? '')));
    $name = trim((string)$get('visitor_welcome_from_name', 'KCMC Connect'));
    $base = rtrim(trim((string)$get('visitor_welcome_base_url', 'https://bobsome1.com/kcmc-connect/')), '/') . '/';
    $parts = parse_url($base);
    $validBase = is_array($parts) && ($parts['scheme'] ?? '') === 'https'
        && !empty($parts['host']) && !isset($parts['user'], $parts['pass'])
        && !isset($parts['query']) && !isset($parts['fragment'])
        && !preg_match('/[\x00-\x20\x7f]/', $base);
    // A username without a password must also be rejected (no embedded credentials).
    $validBase = $validBase && !isset($parts['user']) && !isset($parts['pass']);
    $validName = $name !== '' && strlen($name) <= 120 && !preg_match('/[\x00-\x1f\x7f]/', $name);
    return ['enabled' => $enabled, 'from' => $from, 'from_name' => $name, 'base_url' => $base,
        'ready' => $enabled && kcmc_visitor_welcome_email_valid($from) && $validName && $validBase];
}

/** Read published contact fields without initializing, repairing or writing content.json. */
function kcmc_visitor_welcome_contact(): array {
    $raw = @file_get_contents(KCMC_DATA);
    $data = is_string($raw) ? json_decode($raw, true) : null;
    return is_array($data['contact'] ?? null) ? $data['contact'] : [];
}

function kcmc_visitor_welcome_message(array $visit, array $settings, ?array $contact = null): array {
    $contact ??= kcmc_visitor_welcome_contact();
    $reply = strtolower(trim((string)($contact['email'] ?? 'secretary@umckc.org')));
    if (!kcmc_visitor_welcome_email_valid($reply)) $reply = 'secretary@umckc.org';
    $phone = trim((string)($contact['phone'] ?? '417-739-4395'));
    if (!preg_match('/\A[0-9+(). xX#-]{7,40}\z/', $phone)) $phone = '417-739-4395';
    $address = trim((string)($contact['address'] ?? '57 Kimberling City Center Lane, Kimberling City, MO 65686'));
    if ($address === '' || strlen($address) > 240 || preg_match('/[\x00-\x1f\x7f]/', $address)) {
        $address = '57 Kimberling City Center Lane, Kimberling City, MO 65686';
    }
    // Never reflect visitor notes, phone numbers or arbitrary URLs into outgoing mail.
    $first = explode(' ', trim((string)($visit['name'] ?? '')))[0];
    if (preg_match("/\A[\p{L}\p{M}'\x{2019}-]{1,80}\z/u", $first) !== 1) $first = 'there';
    $service = (string)($visit['service'] ?? '');
    $base = $settings['base_url'];
    $body = "Hi {$first},\n\n"
        . "We're glad you're planning to visit Kimberling City Methodist Church. Come as you are - there is a place for you here.\n\n"
        . "Your visit request is saved for our welcome team.\n"
        . "Your selected Sunday service: {$service}\n"
        . "Where: {$address}\n"
        . "Directions: https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7\n\n"
        . "A FEW EASY NEXT STEPS\n"
        . "See upcoming gatherings and community events: {$base}#events\n"
        . "Ask about a Bible study, group or family connection: {$base}#partner\n"
        . "Explore ways to serve: {$base}#serve\n"
        . "Read the current Sunday bulletin: {$base}bulletin.php\n\n"
        . "Bringing children? Launch Kids meets during the 10:30 AM Contemporary service. Reply or call the office with family, arrival or accessibility questions.\n\n"
        . "Invite someone to come with you: {$base}#visit\n\n"
        . "Questions? Reply to this email or call {$phone}.\n"
        . "Your KCMC church family\n\n"
        . "This one-time email responds to a visit request. It does not create an account or subscribe you to ongoing updates. If you did not request it, no action is needed.\n";
    return ['subject' => 'Welcome to KCMC - your visit and next steps', 'body' => $body, 'reply_to' => $reply];
}

/** Publicly returned statuses never claim that an inbox received a message. */
function kcmc_visitor_welcome_confirmation(string $status): string {
    $saved = 'Your visit request is saved for our welcome team. ';
    if ($status === 'accepted') return $saved . 'Your welcome email has been accepted for delivery; check your inbox and spam folder. Your next steps are below.';
    if ($status === 'suppressed') return $saved . 'A welcome email was already requested for this address in the last 24 hours, so no repeat email was sent. Your next steps are below.';
    return $saved . 'We could not send the welcome email right now. Your request is still saved, and your next steps are below. Contact the church office with any questions.';
}

function kcmc_visitor_welcome_status_label(string $status): string {
    return match ($status) {
        'accepted' => 'Accepted for delivery; inbox receipt not confirmed',
        'attempting' => 'Attempt started; delivery unconfirmed - check before resending',
        'not_configured' => 'Not enabled - personal follow-up needed',
        'suppressed' => 'No repeat email within 24 hours',
        'unavailable' => 'Not sent - personal follow-up needed',
        default => 'No delivery recorded',
    };
}

function kcmc_visitor_welcome_states(): array {
    $raw = @file_get_contents(KCMC_VISITOR_WELCOME_STATE);
    $state = is_string($raw) ? json_decode($raw, true) : null;
    return is_array($state['deliveries'] ?? null) ? $state['deliveries'] : [];
}

/** Claim before the external handoff: a retry or crash cannot send the same receipt twice. */
function kcmc_visitor_welcome_claim(string $id, string $email, bool $ready, int $now): array {
    if (is_file(KCMC_VISITOR_WELCOME_STATE)) {
        $raw = file_get_contents(KCMC_VISITOR_WELCOME_STATE);
        $existing = is_string($raw) ? json_decode($raw, true) : null;
        if (!is_array($existing) || !is_array($existing['deliveries'] ?? null) || !is_array($existing['recipients'] ?? null)) {
            throw new RuntimeException('Welcome delivery state is unavailable.');
        }
    }
    $hash = hash('sha256', 'kcmc-visitor-welcome|' . $email);
    return kcmc_update_json_store(KCMC_VISITOR_WELCOME_STATE, ['version' => 1, 'deliveries' => [], 'recipients' => []],
        static function (array &$state) use ($id, $hash, $ready, $now): array {
            foreach ($state['deliveries'] as $key => $row) {
                if ((int)($row['at'] ?? 0) < $now - 30 * KCMC_VISITOR_WELCOME_WINDOW) unset($state['deliveries'][$key]);
            }
            foreach ($state['recipients'] as $key => $stamp) {
                if ((int)$stamp <= $now - KCMC_VISITOR_WELCOME_WINDOW) unset($state['recipients'][$key]);
            }
            if (isset($state['deliveries'][$id])) return ['send' => false, 'status' => (string)$state['deliveries'][$id]['status']];
            if (count($state['deliveries']) >= 5000) return ['send' => false, 'status' => 'unavailable'];
            $status = !$ready ? 'not_configured' : (isset($state['recipients'][$hash]) ? 'suppressed' : 'attempting');
            $state['deliveries'][$id] = ['status' => $status, 'at' => $now];
            if ($status === 'attempting') $state['recipients'][$hash] = $now;
            return ['send' => $status === 'attempting', 'status' => $status];
        });
}

/** @return array{status:string} */
function kcmc_visitor_welcome_send(string $id, array $visit, ?callable $transport = null, ?array $settingsOverride = null, ?int $now = null): array {
    $services = ['8:00 AM — Front Porch Gospel', '9:15 AM — Traditional Worship', '10:30 AM — Contemporary Worship'];
    $email = strtolower(trim((string)($visit['email'] ?? '')));
    if (($visit['kind'] ?? '') !== 'visit') return ['status' => 'not_applicable'];
    if (!preg_match('/\Aconnection_[a-f0-9]{24}\z/', $id) || !kcmc_visitor_welcome_email_valid($email)
        || !in_array($visit['service'] ?? '', $services, true)) return ['status' => 'unavailable'];
    $settings = kcmc_visitor_welcome_settings($settingsOverride);
    $now ??= time();
    try {
        $claim = kcmc_visitor_welcome_claim($id, $email, !empty($settings['ready']), $now);
    } catch (Throwable) {
        return ['status' => 'unavailable'];
    }
    if (empty($claim['send'])) return ['status' => $claim['status']];
    $message = kcmc_visitor_welcome_message($visit, $settings);
    $headers = [
        'From' => '"' . addcslashes($settings['from_name'], '\\"') . '" <' . $settings['from'] . '>',
        'Reply-To' => $message['reply_to'],
        'MIME-Version' => '1.0',
        'Content-Type' => 'text/plain; charset=UTF-8',
        'Content-Transfer-Encoding' => 'quoted-printable',
        'Auto-Submitted' => 'auto-generated',
        'X-Auto-Response-Suppress' => 'All',
    ];
    $sender = $transport ?? static function (string $to, string $subject, string $body, array $mailHeaders, string $envelope): bool {
        return mail($to, $subject, $body, $mailHeaders, $envelope);
    };
    try {
        $sent = $sender($email, $message['subject'], quoted_printable_encode(str_replace("\n", "\r\n", $message['body'])), $headers, '-f' . $settings['from']) === true;
    } catch (Throwable) {
        $sent = false;
    }
    $status = $sent ? 'accepted' : 'unavailable';
    try {
        kcmc_update_json_store(KCMC_VISITOR_WELCOME_STATE, [], static function (array &$state) use ($id, $status): void {
            if (!isset($state['deliveries'][$id])) throw new RuntimeException('Welcome attempt is missing.');
            $state['deliveries'][$id]['status'] = $status;
        });
    } catch (Throwable) {
        // The persisted pre-send claim still prevents a duplicate. Do not send again.
    }
    return ['status' => $status];
}
