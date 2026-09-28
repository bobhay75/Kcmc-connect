<?php
declare(strict_types=1);

const KCMC_ROOT = __DIR__ . '/..';
const KCMC_DATA = KCMC_ROOT . '/data/content.json';
const KCMC_RELEASE_CONTENT = KCMC_ROOT . '/data/releases/3.0.0.json';
const KCMC_CONFIG = KCMC_ROOT . '/config.php';
const KCMC_BACKUPS = KCMC_ROOT . '/backups';
const KCMC_RETIRED_CONTENT_IDS = ['backpack-blessing-2026'];
const KCMC_LOCAL_TIMEZONE = 'America/Chicago';

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

function kcmc_session_cookie_present(): bool {
    $name = (string)(kcmc_config()['session_name'] ?? '');
    return $name !== '' && isset($_COOKIE[$name]) && is_string($_COOKIE[$name]) && $_COOKIE[$name] !== '';
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

function kcmc_local_date_value(string $value, string $format = 'Y-m-d'): string {
    if (trim($value) === '') return '';
    try {
        $timezone = new DateTimeZone(KCMC_LOCAL_TIMEZONE);
        return (new DateTimeImmutable($value, $timezone))
            ->setTimezone($timezone)
            ->format($format);
    } catch (Throwable) {
        return '';
    }
}

function kcmc_local_datetime_iso(string $value, bool $endOfDay = false): string {
    $value = trim($value);
    if ($value === '') return '';
    $format = $endOfDay ? '!Y-m-d' : '!Y-m-d\TH:i';
    $expected = $endOfDay ? 'Y-m-d' : 'Y-m-d\TH:i';
    $timezone = new DateTimeZone(KCMC_LOCAL_TIMEZONE);
    $date = DateTimeImmutable::createFromFormat($format, $value, $timezone);
    if ($date === false || $date->format($expected) !== $value) return '';
    if ($endOfDay) $date = $date->setTime(23, 59, 59);
    return $date->format(DateTimeInterface::ATOM);
}

function kcmc_valid_event_date(string $value): bool {
    $value = trim($value);
    if ($value === '') return false;
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value, new DateTimeZone(KCMC_LOCAL_TIMEZONE));
    return $date !== false && $date->format('Y-m-d') === $value;
}

function kcmc_event_time_minutes(string $value): ?int {
    $value = trim($value);
    if ($value === '') return null;
    if (!preg_match('/\A(0?[1-9]|1[0-2]):([0-5][0-9])\s*([AaPp][Mm])\z/', $value, $m)) return null;
    $hour = (int)$m[1];
    $minute = (int)$m[2];
    if (strtolower($m[3]) === 'pm' && $hour !== 12) $hour += 12;
    if (strtolower($m[3]) === 'am' && $hour === 12) $hour = 0;
    return ($hour * 60) + $minute;
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

function kcmc_apply_required_public_content(array &$data): bool {
    $requiredEvents = [
        [
            'id' => 'trunk-or-treat-2026',
            'title' => 'Trunk or Treat!',
            'date' => '2026-10-31',
            'time' => '4:30 PM',
            'end_time' => '6:30 PM',
            'location' => 'KCMC parking lot',
            'address' => '57 Kimberling City Center Lane, Kimberling City, MO 65686',
            'label' => 'Free community event',
            'description' => 'Free candy, hot dogs, chips and drinks, plus music and family fun. All are welcome.',
            'image' => 'assets/visuals/trunk-or-treat-2026.webp',
            'image_alt' => 'Autumn Trunk or Treat graphic with friendly ghosts, pumpkins and an open car trunk filled with candy beside a lake.',
            'rsvp' => false,
            'priority' => 100,
            'status' => 'published',
            'expires_at' => '2026-10-31T23:59:59-05:00',
        ],
    ];

    $changed = false;

    // cPanel preserves production data/content.json across deployments. Supply
    // a default only when hours are missing: later Publishing Desk corrections
    // and temporary closures must survive every public read and restore.
    if (!isset($data['contact']) || !is_array($data['contact'])) {
        $data['contact'] = [];
        $changed = true;
    }
    $defaultOfficeHours = 'Tue–Thu • 9:00 AM–4:00 PM';
    $savedOfficeHours = $data['contact']['office_hours'] ?? null;
    if (!is_string($savedOfficeHours) || trim($savedOfficeHours) === '') {
        $data['contact']['office_hours'] = $defaultOfficeHours;
        $changed = true;
    }

    if (!isset($data['events']) || !is_array($data['events'])) $data['events'] = [];
    $existingIds = [];
    foreach ($data['events'] as $event) {
        if (is_array($event) && isset($event['id'])) $existingIds[(string)$event['id']] = true;
    }

    foreach ($requiredEvents as $event) {
        if (isset($existingIds[$event['id']])) continue;
        $data['events'][] = $event;
        $changed = true;
    }
    return $changed;
}

function kcmc_featured_announcement_index(array $announcements): ?int {
    foreach ($announcements as $index => $announcement) {
        if (is_array($announcement) && ($announcement['id'] ?? '') === 'owner-announcement') return (int)$index;
    }

    $selected = null;
    $selectedPriority = PHP_INT_MIN;
    foreach ($announcements as $index => $announcement) {
        if (!is_array($announcement)) continue;
        $id = (string)($announcement['id'] ?? '');
        if ($id === '' || in_array($id, KCMC_RETIRED_CONTENT_IDS, true)) continue;
        $priority = (int)($announcement['priority'] ?? 0);
        if ($selected === null || $priority > $selectedPriority) {
            $selected = (int)$index;
            $selectedPriority = $priority;
        }
    }
    return $selected;
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
            // Contact hours belong to the Publishing Desk. The shared fallback
            // below supplies missing hours without replacing approved changes.
            $data['meta']['content_release'] = '3.0.0';
        }
    }
    // Serve migrations and approved release content without writing during a
    // public request. The Publishing Desk persists the layered view on publish.
    kcmc_apply_required_public_content($data);
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

function kcmc_current_user(bool $recordActivity = true): ?array {
    kcmc_session_start();
    $id = (string)($_SESSION['kcmc_user_id'] ?? '');
    if ($id === '') return null;
    $user = kcmc_find_user_by_id($id);
    if (!$user || empty($user['active'])) {
        unset($_SESSION['kcmc_user_id']);
        return null;
    }

    require_once __DIR__ . '/session-lifetime.php';
    $now = time();
    $lifetime = kcmc_session_apply_lifetime($_SESSION, $now, $recordActivity);
    if (($lifetime['status'] ?? '') !== 'active') {
        $reason = (string)($lifetime['status'] ?? 'expired');
        kcmc_session_audit_expiration($id, $reason, $now);
        $_SESSION = [];
        session_regenerate_id(true);
        $_SESSION['csrf'] = bin2hex(random_bytes(24));
        $_SESSION['kcmc_session_expired'] = $reason;
        return null;
    }
    if (!empty($lifetime['regenerate'])) {
        session_regenerate_id(true);
        kcmc_session_mark_regenerated($_SESSION, $now);
    }
    return $user;
}

function kcmc_current_user_if_session(): ?array {
    if (!kcmc_session_cookie_present()) return null;
    header('Cache-Control: private, no-store, max-age=0');
    header('Vary: Cookie');
    return kcmc_current_user(false);
}

function kcmc_login_user(array $user): void {
    kcmc_session_start();
    require_once __DIR__ . '/session-lifetime.php';
    session_regenerate_id(true);
    $_SESSION['kcmc_user_id'] = (string)$user['id'];
    $_SESSION['csrf'] = bin2hex(random_bytes(24));
    kcmc_session_initialize_auth($_SESSION, time());
}

function kcmc_logout_user(): void {
    kcmc_session_start();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', [
            'expires' => time() - 42000,
            'path' => (string)$p['path'],
            'domain' => (string)($p['domain'] ?? ''),
            'secure' => (bool)$p['secure'],
            'httponly' => (bool)$p['httponly'],
            'samesite' => (string)($p['samesite'] ?? 'Lax'),
        ]);
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
    $expired = !empty($_SESSION['kcmc_session_expired']);
    unset($_SESSION['kcmc_session_expired']);
    $query = 'next=' . rawurlencode($target) . ($expired ? '&expired=1' : '');
    header('Location: ' . kcmc_url('member/login.php?' . $query));
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
    return array_values(array_filter($items, function($item) use ($now): bool {
        if (!is_array($item)) return false;
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
