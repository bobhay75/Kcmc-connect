<?php
declare(strict_types=1);

const KCMC_ROOT = __DIR__ . '/..';
const KCMC_DATA = KCMC_ROOT . '/data/content.json';
const KCMC_CONFIG = KCMC_ROOT . '/config.php';
const KCMC_BACKUPS = KCMC_ROOT . '/backups';

function kcmc_config(): array {
    $defaults = [
        'church_email' => 'secretary@umckc.org',
        'setup_key' => getenv('KCMC_SETUP_KEY') ?: '',
        'admin_password_hash' => getenv('KCMC_ADMIN_PASSWORD_HASH') ?: '',
        'session_name' => 'KCMC_PHASE6_OWNER',
    ];
    if (is_file(KCMC_CONFIG)) {
        $cfg = require KCMC_CONFIG;
        if (is_array($cfg)) $defaults = array_replace($defaults, $cfg);
    }
    // Setup keys are accepted only from the server environment, never from a deployed file.
    $envSetupKey = getenv('KCMC_SETUP_KEY');
    $defaults['setup_key'] = is_string($envSetupKey) ? trim($envSetupKey) : '';
    return $defaults;
}

function kcmc_base_path(): string {
    $script = str_replace('\\\\', '/', (string)($_SERVER['SCRIPT_NAME'] ?? ''));
    $adminPos = strpos($script, '/admin/');
    if ($adminPos !== false) return rtrim(substr($script, 0, $adminPos), '/');
    $dir = rtrim(str_replace('\\\\', '/', dirname($script)), '/');
    return $dir === '.' ? '' : $dir;
}

function kcmc_url(string $path = ''): string {
    return kcmc_base_path() . '/' . ltrim($path, '/');
}

function kcmc_session_start(): void {
    if (session_status() === PHP_SESSION_ACTIVE) return;
    $cfg = kcmc_config();
    session_name((string)$cfg['session_name']);
    session_set_cookie_params([
        'httponly' => true,
        'secure' => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'),
        'samesite' => 'Strict',
        'path' => kcmc_base_path() . '/',
    ]);
    session_start();
}

function kcmc_content(): array {
    $raw = @file_get_contents(KCMC_DATA);
    $data = $raw ? json_decode($raw, true) : null;
    return is_array($data) ? $data : [];
}

function kcmc_write_content(array $data, string $actor = 'owner'): void {
    if (!is_dir(KCMC_BACKUPS)) mkdir(KCMC_BACKUPS, 0750, true);
    if (is_file(KCMC_DATA)) {
        $stamp = gmdate('Ymd-His');
        @copy(KCMC_DATA, KCMC_BACKUPS . "/content-$stamp.json");
    }
    $data['meta']['updated_at'] = gmdate('c');
    $data['meta']['updated_by'] = $actor;
    $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if ($json === false) throw new RuntimeException('Unable to encode content.');
    $tmp = KCMC_DATA . '.tmp';
    if (file_put_contents($tmp, $json . PHP_EOL, LOCK_EX) === false) throw new RuntimeException('Unable to write content.');
    if (!rename($tmp, KCMC_DATA)) throw new RuntimeException('Unable to publish content.');
}

function kcmc_owner_configured(): bool {
    $cfg = kcmc_config();
    return !empty($cfg['admin_password_hash']);
}

function kcmc_owner_logged_in(): bool {
    kcmc_session_start();
    return !empty($_SESSION['kcmc_owner']);
}

function kcmc_require_owner(): void {
    if (!kcmc_owner_logged_in()) {
        header('Location: ' . kcmc_url('admin/login.php'));
        exit;
    }
}

function kcmc_csrf(): string {
    kcmc_session_start();
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(24));
    return $_SESSION['csrf'];
}

function kcmc_verify_csrf(?string $token): bool {
    kcmc_session_start();
    return is_string($token) && isset($_SESSION['csrf']) && hash_equals($_SESSION['csrf'], $token);
}

function kcmc_h(string $value): string { return htmlspecialchars($value, ENT_QUOTES, 'UTF-8'); }

function kcmc_active_items(array $items): array {
    $now = time();
    return array_values(array_filter($items, function(array $item) use ($now): bool {
        if (($item['status'] ?? 'published') !== 'published') return false;
        if (!empty($item['starts_at']) && strtotime((string)$item['starts_at']) > $now) return false;
        if (!empty($item['expires_at']) && strtotime((string)$item['expires_at']) <= $now) return false;
        return true;
    }));
}
