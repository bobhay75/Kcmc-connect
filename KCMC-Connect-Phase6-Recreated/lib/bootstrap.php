<?php
declare(strict_types=1);

const KCMC_ROOT = __DIR__ . '/..';
const KCMC_DATA = KCMC_ROOT . '/data/content.json';
const KCMC_RELEASE_CONTENT = KCMC_ROOT . '/data/releases/3.0.0.json';
const KCMC_CONFIG = KCMC_ROOT . '/config.php';
const KCMC_BACKUPS = KCMC_ROOT . '/backups';
const KCMC_RETIRED_CONTENT_IDS = ['backpack-blessing-2026'];

$privateDataDir = trim((string)(getenv('KCMC_PRIVATE_DATA_DIR') ?: ''));
define('KCMC_PRIVATE_DATA', $privateDataDir !== '' ? rtrim($privateDataDir, '/') : KCMC_ROOT . '/data/private');
define('KCMC_USERS', KCMC_PRIVATE_DATA . '/users.json');
define('KCMC_INVITES', KCMC_PRIVATE_DATA . '/invites.json');
define('KCMC_PRAYERS', KCMC_PRIVATE_DATA . '/prayers.json');
define('KCMC_LOGIN_ATTEMPTS', KCMC_PRIVATE_DATA . '/login-attempts.json');
define('KCMC_AUDIT_LOG', KCMC_PRIVATE_DATA . '/audit.ndjson');

function kcmc_config(): array {
    $defaults = [
        'church_email' => 'secretary@umckc.org',
        'session_name' => 'KCMC_CONNECT_V3',
        'setup_key' => getenv('KCMC_SETUP_KEY') ?: '',
    ];
    if (is_file(KCMC_CONFIG)) {
        $cfg = require KCMC_CONFIG;
        if (is_array($cfg)) $defaults = array_replace($defaults, $cfg);
    }
    $envSetupKey = getenv('KCMC_SETUP_KEY');
    $defaults['setup_key'] = is_string($envSetupKey) ? trim($envSetupKey) : '';
    return $defaults;
}

function kcmc_base_path(): string {
    $script = str_replace('\\', '/', (string)($_SERVER['SCRIPT_NAME'] ?? ''));
    foreach (['/admin/', '/member/', '/api/'] as $segment) {
        $position = strpos($script, $segment);
        if ($position !== false) return rtrim(substr($script, 0, $position), '/');
    }
    $dir = rtrim(str_replace('\\', '/', dirname($script)), '/');
    return $dir === '.' || $dir === '/' ? '' : $dir;
}

function kcmc_url(string $path = ''): string {
    return kcmc_base_path() . '/' . ltrim($path, '/');
}

function kcmc_is_https(): bool {
    if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') return true;
    return strtolower((string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https';
}

function kcmc_session_start(): void {
    if (session_status() === PHP_SESSION_ACTIVE) return;
    $cfg = kcmc_config();
    ini_set('session.use_strict_mode', '1');
    ini_set('session.use_only_cookies', '1');
    session_name((string)$cfg['session_name']);
    session_set_cookie_params([
        'httponly' => true,
        'secure' => kcmc_is_https(),
        'samesite' => 'Lax',
        'path' => kcmc_base_path() . '/',
    ]);
    session_start();
}

function kcmc_private_headers(): void {
    header('Cache-Control: no-store, max-age=0');
    header('Pragma: no-cache');
    header('X-Robots-Tag: noindex, nofollow, noarchive');
    header('Referrer-Policy: no-referrer');
}

function kcmc_h(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function kcmc_text_length(string $value): int {
    return function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
}

function kcmc_normalize_email(string $email): string {
    return strtolower(trim($email));
}

function kcmc_valid_email(string $email): bool {
    return filter_var(kcmc_normalize_email($email), FILTER_VALIDATE_EMAIL) !== false;
}

function kcmc_random_id(string $prefix): string {
    return $prefix . '_' . bin2hex(random_bytes(12));
}

function kcmc_ensure_private_storage(): void {
    if (!is_dir(KCMC_PRIVATE_DATA) && !mkdir(KCMC_PRIVATE_DATA, 0750, true) && !is_dir(KCMC_PRIVATE_DATA)) {
        throw new RuntimeException('Private storage is unavailable.');
    }
    @chmod(KCMC_PRIVATE_DATA, 0750);
}

function kcmc_read_json_store(string $path, array $default): array {
    kcmc_ensure_private_storage();
    $raw = @file_get_contents($path);
    if ($raw === false || trim($raw) === '') return $default;
    $data = json_decode($raw, true);
    return is_array($data) ? $data : $default;
}

function kcmc_update_json_store(string $path, array $default, callable $callback): mixed {
    kcmc_ensure_private_storage();
    $lock = @fopen($path . '.lock', 'c+');
    if ($lock === false || !flock($lock, LOCK_EX)) throw new RuntimeException('Could not lock private storage.');
    try {
        $raw = @file_get_contents($path);
        $data = $raw ? json_decode($raw, true) : null;
        if (!is_array($data)) $data = $default;
        $result = $callback($data);
        $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if ($json === false) throw new RuntimeException('Could not encode private data.');
        $tmp = $path . '.tmp-' . bin2hex(random_bytes(6));
        if (file_put_contents($tmp, $json . PHP_EOL, LOCK_EX) === false) throw new RuntimeException('Could not write private data.');
        @chmod($tmp, 0640);
        if (!rename($tmp, $path)) {
            @unlink($tmp);
            throw new RuntimeException('Could not publish private data.');
        }
        return $result;
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function kcmc_sanitize_audit_context(array $context): array {
    $safe = [];
    foreach ($context as $key => $value) {
        if (preg_match('/(?:password|token|message|body|text|setup_key)/i', (string)$key)) continue;
        $safe[$key] = is_array($value) ? kcmc_sanitize_audit_context($value) : $value;
    }
    return $safe;
}

function kcmc_audit(string $action, array $context = []): void {
    kcmc_ensure_private_storage();
    $record = [
        'at' => gmdate('c'),
        'action' => $action,
        'actor_id' => (string)(kcmc_current_user()['id'] ?? 'system'),
        'ip_hash' => hash('sha256', (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown')),
        'context' => kcmc_sanitize_audit_context($context),
    ];
    @file_put_contents(KCMC_AUDIT_LOG, json_encode($record, JSON_UNESCAPED_SLASHES) . PHP_EOL, FILE_APPEND | LOCK_EX);
    @chmod(KCMC_AUDIT_LOG, 0640);
}

function kcmc_content(): array {
    $raw = @file_get_contents(KCMC_DATA);
    $data = $raw ? json_decode($raw, true) : null;
    if (!is_array($data)) return [];
    if (($data['meta']['content_release'] ?? '') !== '3.0.0' && is_file(KCMC_RELEASE_CONTENT)) {
        $releaseRaw = @file_get_contents(KCMC_RELEASE_CONTENT);
        $release = $releaseRaw ? json_decode($releaseRaw, true) : null;
        if (is_array($release) && ($release['version'] ?? '') === '3.0.0') {
            foreach (['announcements', 'events', 'news'] as $section) {
                if (isset($release[$section]) && is_array($release[$section])) $data[$section] = $release[$section];
            }
            if (isset($release['contact']['office_hours'])) $data['contact']['office_hours'] = (string)$release['contact']['office_hours'];
            $data['meta']['content_release'] = '3.0.0';
            try { kcmc_write_content($data, 'Version 3 content migration'); } catch (Throwable) { /* Serve the migrated view even if storage is temporarily read-only. */ }
        }
    }
    $date = (string)($data['bulletin']['date'] ?? '');
    if ($date !== '' && strtotime($date . ' 23:59:59') < strtotime('-7 days')) $data['bulletin']['date'] = '';
    $data['meta']['effective_version'] = '3.0.0';
    return $data;
}

function kcmc_write_content(array $data, string $actor = 'system'): void {
    if (!is_dir(KCMC_BACKUPS) && !mkdir(KCMC_BACKUPS, 0750, true) && !is_dir(KCMC_BACKUPS)) throw new RuntimeException('Unable to create backup storage.');
    $lock = @fopen(KCMC_DATA . '.lock', 'c+');
    if ($lock === false || !flock($lock, LOCK_EX)) throw new RuntimeException('Unable to lock content storage.');
    try {
        if (is_file(KCMC_DATA)) {
            $stamp = gmdate('Ymd-His') . '-' . bin2hex(random_bytes(3));
            @copy(KCMC_DATA, KCMC_BACKUPS . "/content-$stamp.json");
        }
        $data['meta']['version'] = '3.0.0';
        $data['meta']['updated_at'] = gmdate('c');
        $data['meta']['updated_by'] = $actor;
        $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if ($json === false) throw new RuntimeException('Unable to encode content.');
        $tmp = KCMC_DATA . '.tmp-' . bin2hex(random_bytes(6));
        if (file_put_contents($tmp, $json . PHP_EOL, LOCK_EX) === false) throw new RuntimeException('Unable to write content.');
        if (!rename($tmp, KCMC_DATA)) { @unlink($tmp); throw new RuntimeException('Unable to publish content.'); }
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function kcmc_users_store(): array {
    return kcmc_read_json_store(KCMC_USERS, ['version' => 1, 'users' => []]);
}

function kcmc_users(): array {
    return array_values(array_filter(kcmc_users_store()['users'] ?? [], 'is_array'));
}

function kcmc_find_user_by_id(string $id): ?array {
    foreach (kcmc_users() as $user) if (($user['id'] ?? '') === $id) return $user;
    return null;
}

function kcmc_find_user_by_email(string $email): ?array {
    $needle = kcmc_normalize_email($email);
    foreach (kcmc_users() as $user) if (($user['email_normalized'] ?? '') === $needle) return $user;
    return null;
}

function kcmc_has_any_users(): bool {
    return count(kcmc_users()) > 0;
}

function kcmc_current_user(): ?array {
    kcmc_session_start();
    $id = (string)($_SESSION['kcmc_user_id'] ?? '');
    if ($id === '') return null;
    $user = kcmc_find_user_by_id($id);
    if (!$user || empty($user['active'])) {
        unset($_SESSION['kcmc_user_id']);
        return null;
    }
    return $user;
}

function kcmc_login_user(array $user): void {
    kcmc_session_start();
    session_regenerate_id(true);
    $_SESSION['kcmc_user_id'] = (string)$user['id'];
    $_SESSION['csrf'] = bin2hex(random_bytes(24));
}

function kcmc_logout_user(): void {
    kcmc_session_start();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'] ?? '', (bool)$p['secure'], (bool)$p['httponly']);
    }
    session_destroy();
}

function kcmc_role(array $user): string {
    return (string)($user['role'] ?? 'member');
}

function kcmc_has_role(array $roles, ?array $user = null): bool {
    $user ??= kcmc_current_user();
    return $user !== null && in_array(kcmc_role($user), $roles, true);
}

function kcmc_can_publish(?array $user = null): bool {
    return kcmc_has_role(['pastor_admin', 'recovery_admin'], $user);
}

function kcmc_can_manage_users(?array $user = null): bool {
    return kcmc_has_role(['pastor_admin', 'recovery_admin'], $user);
}

function kcmc_can_moderate_prayers(?array $user = null): bool {
    return kcmc_has_role(['pastor_admin'], $user);
}

function kcmc_can_view_private_prayers(?array $user = null): bool {
    return kcmc_has_role(['prayer_team', 'pastor_admin'], $user);
}

function kcmc_safe_next(string $candidate, string $fallback = 'member/'): string {
    $candidate = trim($candidate);
    if ($candidate === '' || str_contains($candidate, "\n") || str_contains($candidate, "\r") || str_starts_with($candidate, '//')) return kcmc_url($fallback);
    $parts = parse_url($candidate);
    if ($parts === false || isset($parts['scheme']) || isset($parts['host'])) return kcmc_url($fallback);
    $path = (string)($parts['path'] ?? '');
    $base = kcmc_base_path();
    if (!str_starts_with($path, $base . '/')) return kcmc_url($fallback);
    return $candidate;
}

function kcmc_require_login(string $next = ''): array {
    kcmc_private_headers();
    $user = kcmc_current_user();
    if ($user) return $user;
    $target = $next !== '' ? $next : (string)($_SERVER['REQUEST_URI'] ?? kcmc_url('member/'));
    header('Location: ' . kcmc_url('member/login.php?next=' . rawurlencode($target)));
    exit;
}

function kcmc_require_role(array $roles): array {
    $user = kcmc_require_login();
    if (!kcmc_has_role($roles, $user)) {
        http_response_code(403);
        kcmc_private_headers();
        exit('Access denied.');
    }
    return $user;
}

function kcmc_csrf(): string {
    kcmc_session_start();
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(24));
    return (string)$_SESSION['csrf'];
}

function kcmc_verify_csrf(?string $token): bool {
    kcmc_session_start();
    return is_string($token) && isset($_SESSION['csrf']) && hash_equals((string)$_SESSION['csrf'], $token);
}

function kcmc_login_key(string $email): string {
    return hash('sha256', kcmc_normalize_email($email) . '|' . (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'));
}

function kcmc_login_is_blocked(string $email): bool {
    $state = kcmc_read_json_store(KCMC_LOGIN_ATTEMPTS, ['attempts' => []]);
    $entry = $state['attempts'][kcmc_login_key($email)] ?? [];
    return (int)($entry['locked_until'] ?? 0) > time();
}

function kcmc_record_login_failure(string $email): void {
    $key = kcmc_login_key($email);
    kcmc_update_json_store(KCMC_LOGIN_ATTEMPTS, ['attempts' => []], function (array &$state) use ($key): void {
        $now = time();
        $entry = $state['attempts'][$key] ?? ['count' => 0, 'window_started' => $now, 'locked_until' => 0];
        if (($now - (int)$entry['window_started']) > 900) $entry = ['count' => 0, 'window_started' => $now, 'locked_until' => 0];
        $entry['count'] = (int)$entry['count'] + 1;
        if ($entry['count'] >= 5) $entry['locked_until'] = $now + 900;
        $state['attempts'][$key] = $entry;
    });
}

function kcmc_clear_login_failures(string $email): void {
    $key = kcmc_login_key($email);
    kcmc_update_json_store(KCMC_LOGIN_ATTEMPTS, ['attempts' => []], function (array &$state) use ($key): void {
        unset($state['attempts'][$key]);
    });
}

function kcmc_update_user_login(string $id): void {
    kcmc_update_json_store(KCMC_USERS, ['version' => 1, 'users' => []], function (array &$state) use ($id): void {
        foreach ($state['users'] as &$user) if (($user['id'] ?? '') === $id) $user['last_login_at'] = gmdate('c');
        unset($user);
    });
}

function kcmc_active_items(array $items): array {
    $now = time();
    return array_values(array_filter($items, function(array $item) use ($now): bool {
        if (in_array((string)($item['id'] ?? ''), KCMC_RETIRED_CONTENT_IDS, true)) return false;
        if (($item['status'] ?? 'published') !== 'published') return false;
        if (!empty($item['starts_at']) && strtotime((string)$item['starts_at']) > $now) return false;
        if (!empty($item['expires_at']) && strtotime((string)$item['expires_at']) <= $now) return false;
        return true;
    }));
}

function kcmc_owner_configured(): bool { return kcmc_has_any_users(); }
function kcmc_owner_logged_in(): bool { return kcmc_can_publish(); }
function kcmc_require_owner(): void { kcmc_require_role(['pastor_admin', 'recovery_admin']); }
