<?php
declare(strict_types=1);

/** Build a delivery card only for the exact, still-valid invitation created by this admin.
 * Pure helper: never creates/consumes invitations, opens URLs, sends mail or writes storage.
 * Browser confirmation is a usability guard; authorization remains in admin/users.php.
 */
function kcmc_invitation_delivery(array $store, string $link, string $email, string $creator, string $activationUrl, int $now): ?array {
    $parts = parse_url($activationUrl);
    if (!is_array($parts) || empty($parts['host']) || empty($parts['path']) ||
        isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment'])) return null;
    if (!in_array($parts['host'], ['bobsome1.com', 'www.bobsome1.com', 'localhost', '127.0.0.1', '[::1]'], true)) return null;
    $scheme = $parts['scheme'] ?? '';
    if ($scheme !== 'https' && !($scheme === 'http' && in_array($parts['host'], ['localhost', '127.0.0.1', '[::1]'], true))) return null;
    if ($creator === '' || $email !== strtolower(trim($email)) || !filter_var($email, FILTER_VALIDATE_EMAIL) ||
        preg_match('/[\x00-\x20\x7f]/', $email) || strlen($link) > 2048) return null;
    if (!preg_match('~\A' . preg_quote($activationUrl, '~') . '\?token=([a-f0-9]{64})\z~D', $link, $matches)) return null;
    $hash = hash('sha256', $matches[1]);
    $records = $store['invites'] ?? null;
    if (!is_array($records)) return null;
    $matched = [];
    foreach ($records as $record) {
        if (!is_array($record) || !is_string($record['token_hash'] ?? null)) continue;
        if (hash_equals($hash, $record['token_hash'])) $matched[] = $record;
    }
    // Ambiguous records must never be presented as a verified name/link pairing.
    if (count($matched) !== 1) return null;
    $invite = $matched[0];
    $roleNames = ['member' => 'Member', 'prayer_team' => 'Prayer team',
        'pastor_admin' => 'Pastor administrator', 'recovery_admin' => 'Recovery administrator'];
    $role = $invite['role'] ?? null;
    $name = $invite['display_name'] ?? null;
    $expiry = $invite['expires_at'] ?? null;
    if (($invite['email'] ?? null) !== $email || ($invite['created_by'] ?? null) !== $creator ||
        !empty($invite['used_at']) || !is_string($role) || !isset($roleNames[$role]) ||
        !is_string($name) || strlen(trim($name)) < 2 || strlen($name) > 300 ||
        preg_match('/[\x00-\x1f\x7f]/', $name) || !is_string($expiry)) return null;
    $expiresAt = strtotime($expiry);
    if ($expiresAt === false || $expiresAt <= $now) return null;
    $name = trim($name);
    $subject = 'Your KCMC Connect invitation';
    $message = "Hi {$name},\n\nHere is your personal KCMC Connect invitation for {$email}:\n\n{$link}\n\n" .
        "Confirm the page names you, then create your own password with at least 12 characters. " .
        "Please keep this one-time link private and do not forward it.\n\n" .
        "If the page names someone else or says this invitation is no longer valid, stop and contact the KCMC administrator who sent it.\n\nThank you,\nKCMC Connect";
    // No activation token or message body is put in either compose URL.
    // Gmail compose parameters are a convenience, not an API delivery guarantee.
    $gmail = 'https://mail.google.com/mail/?' . http_build_query(
        ['view' => 'cm', 'fs' => '1', 'to' => $email, 'su' => $subject], '', '&', PHP_QUERY_RFC3986);
    $mail = 'mailto:' . rawurlencode($email) . '?subject=' . rawurlencode($subject);
    return ['name' => $name, 'email' => $email, 'role' => $roleNames[$role], 'link' => $link,
        'subject' => $subject, 'message' => $message, 'gmail_url' => $gmail, 'email_url' => $mail,
        'expires_label' => gmdate('F j, Y, g:i A', $expiresAt) . ' UTC'];
}
