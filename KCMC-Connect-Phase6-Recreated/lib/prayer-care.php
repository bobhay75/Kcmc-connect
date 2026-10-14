<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

// A separate opt-in ministry. Never import or grant access to legacy prayers.json.
const KCMC_CARE_ROLES = ['member', 'prayer_team', 'pastor_admin'];
function kcmc_care_empty(): array { return ['version'=>1, 'revision'=>0, 'warriors'=>[], 'entries'=>[], 'commitments'=>[]]; }
function kcmc_care_member(array $user): bool {
    return !empty($user['active']) && !empty($user['id']) && in_array($user['role'] ?? '', KCMC_CARE_ROLES, true);
}
function kcmc_care_leader(array $user): bool { return kcmc_care_member($user) && ($user['role'] ?? '') === 'pastor_admin'; }
function kcmc_care_warrior(array $state, array $user): bool {
    return kcmc_care_member($user) && ($state['warriors'][$user['id']]['status'] ?? '') === 'approved';
}
function kcmc_care_validate(array $state): void {
    if (($state['version'] ?? null) !== 1 || !is_int($state['revision'] ?? null) || $state['revision'] < 0) throw new RuntimeException('Prayer & Care storage needs administrator review.');
    foreach (['warriors','entries','commitments'] as $key) if (!is_array($state[$key] ?? null)) throw new RuntimeException('Prayer & Care storage needs administrator review.');
    foreach ($state['entries'] as $id=>$entry) {
        if (!is_array($entry) || ($entry['id'] ?? '') !== (string)$id || !is_string($entry['author'] ?? null) || !is_string($entry['message'] ?? null)
            || !in_array($entry['kind'] ?? '', ['need','praise'], true) || !in_array($entry['audience'] ?? '', ['pastoral','team','members'], true)
            || !in_array($entry['status'] ?? '', ['private','pending','approved','answered','closed'], true) || !is_int($entry['expires_at'] ?? null)) throw new RuntimeException('Prayer & Care storage needs administrator review.');
    }
    foreach ($state['warriors'] as $record) if (!is_array($record) || !in_array($record['status'] ?? '', ['pending','approved','declined','withdrawn'], true)) throw new RuntimeException('Prayer & Care storage needs administrator review.');
    foreach ($state['commitments'] as $ids) if (!is_array($ids) || array_filter($ids, fn($id)=>!is_string($id))) throw new RuntimeException('Prayer & Care storage needs administrator review.');
}
function kcmc_care_read(): array {
    $path = KCMC_PRIVATE_DATA . '/prayer-care.json';
    if (!file_exists($path)) return kcmc_care_empty();
    $raw = file_get_contents($path);
    $state = is_string($raw) ? json_decode($raw, true) : null;
    if (!is_array($state)) throw new RuntimeException('Prayer & Care storage needs administrator review.');
    kcmc_care_validate($state);
    return $state;
}
function kcmc_care_visible(array $entry, array $state, array $user, int $now): bool {
    if (!kcmc_care_member($user)) return false;
    if (kcmc_care_leader($user) || $entry['author'] === $user['id']) return true;
    if ($entry['status'] !== 'approved' || $entry['expires_at'] <= $now || empty($entry['consent'])) return false;
    return $entry['audience'] === 'members' || ($entry['audience'] === 'team' && kcmc_care_warrior($state, $user));
}
function kcmc_care_shared(array $entry, array $state, array $user, int $now): bool {
    return $entry['status'] === 'approved' && $entry['expires_at'] > $now && !empty($entry['consent'])
        && $entry['audience'] !== 'pastoral' && kcmc_care_visible($entry, $state, $user, $now);
}
function kcmc_care_text(array $input): string {
    $text = trim(is_string($input['message'] ?? null) ? $input['message'] : '');
    if (kcmc_text_length($text) < 10 || kcmc_text_length($text) > 2000) throw new DomainException('Please enter between 10 and 2,000 characters.');
    return $text;
}
function kcmc_care_apply(array &$state, array $user, string $action, array $input, int $now): void {
    if (!kcmc_care_member($user)) throw new DomainException('Access denied.');
    $uid = (string)$user['id'];
    if ($action === 'join') {
        if (($input['confidential'] ?? '') !== '1') throw new DomainException('Please agree to keep requests confidential.');
        if (in_array($state['warriors'][$uid]['status'] ?? '', ['pending','approved'], true)) throw new DomainException('Your signup is already recorded.');
        $state['warriors'][$uid] = ['name'=>(string)($user['display_name'] ?? 'Member'),'status'=>'pending','requested_at'=>$now];
        return;
    }
    if ($action === 'leave') {
        if (isset($state['warriors'][$uid])) $state['warriors'][$uid]['status'] = 'withdrawn';
        foreach ($state['commitments'] as &$ids) $ids = array_values(array_diff($ids, [$uid]));
        unset($ids);
        return;
    }
    if (in_array($action, ['approve_warrior','decline_warrior'], true)) {
        if (!kcmc_care_leader($user)) throw new DomainException('Pastoral approval is required.');
        $target = is_string($input['target'] ?? null) ? $input['target'] : '';
        if (!isset($state['warriors'][$target]) || $state['warriors'][$target]['status'] === 'withdrawn') throw new DomainException('That signup is no longer available.');
        $state['warriors'][$target]['status'] = $action === 'approve_warrior' ? 'approved' : 'declined';
        $state['warriors'][$target]['reviewed_by'] = $uid;
        $state['warriors'][$target]['reviewed_at'] = $now;
        return;
    }
    if ($action === 'submit') {
        $kind = $input['kind'] ?? '';
        $audience = $input['audience'] ?? 'pastoral';
        if (!in_array($kind, ['need','praise'], true) || !in_array($audience, ['pastoral','team','members'], true)) throw new DomainException('Choose a valid request type and audience.');
        $consent = ($input['consent'] ?? '') === '1';
        if ($audience !== 'pastoral' && !$consent) throw new DomainException('Permission is required before sharing with a group.');
        $message = kcmc_care_text($input);
        $id = kcmc_random_id('care');
        $state['entries'][$id] = ['id'=>$id,'author'=>$uid,'kind'=>$kind,'message'=>$message,
            'name'=>($input['name_display'] ?? '') === 'first_name' ? trim(explode(' ', (string)($user['display_name'] ?? 'Member'))[0]) : 'Anonymous',
            'audience'=>$audience,'consent'=>$consent,'status'=>$audience === 'pastoral' ? 'private' : 'pending',
            'created_at'=>$now,'updated_at'=>$now,'expires_at'=>$now+30*86400];
        return;
    }
    $id = is_string($input['entry_id'] ?? null) ? $input['entry_id'] : '';
    if (!isset($state['entries'][$id]) || !kcmc_care_visible($state['entries'][$id], $state, $user, $now)) throw new DomainException('That item is not available.');
    $entry =& $state['entries'][$id];
    if (in_array($action, ['pray','unpray'], true)) {
        if ($action === 'pray' && (!kcmc_care_warrior($state, $user) || $entry['kind'] !== 'need' || !kcmc_care_shared($entry, $state, $user, $now))) throw new DomainException('Approved prayer warriors can choose current shared prayer needs.');
        $ids = array_values(array_diff($state['commitments'][$id] ?? [], [$uid]));
        if ($action === 'pray') $ids[] = $uid;
        $state['commitments'][$id] = $ids;
        return;
    }
    if ($action === 'approve') {
        if (!kcmc_care_leader($user) || $entry['status'] !== 'pending' || $entry['audience'] === 'pastoral' || empty($entry['consent']) || $entry['expires_at'] <= $now) throw new DomainException('Only current, consented submissions can be approved.');
        $entry['status'] = 'approved'; $entry['approved_by'] = $uid; $entry['approved_at'] = $now;
    } elseif (in_array($action, ['update','private','answered','close'], true)) {
        if ($entry['author'] !== $uid && !kcmc_care_leader($user)) throw new DomainException('Only the submitter or pastoral leader may change this item.');
        if ($action === 'update') {
            if ($entry['author'] !== $uid) throw new DomainException('Only the submitter may revise their words.');
            $entry['message'] = kcmc_care_text($input);
            $entry['status'] = $entry['audience'] === 'pastoral' ? 'private' : 'pending';
            $entry['expires_at'] = $now+30*86400;
            unset($entry['approved_by'], $entry['approved_at']);
        } elseif ($action === 'private') {
            $entry['audience'] = 'pastoral'; $entry['consent'] = false; $entry['status'] = 'private';
            unset($entry['approved_by'], $entry['approved_at']);
        } elseif ($action === 'answered') {
            if ($entry['kind'] !== 'need') throw new DomainException('Only a prayer need can be marked answered.');
            $entry['status'] = 'answered'; // Never copies confidential words into a praise report.
        } else $entry['status'] = 'closed';
    } else throw new DomainException('Choose a valid action.');
    $entry['updated_at'] = $now;
}
function kcmc_care_save(array $user, string $action, array $input, int $revision): void {
    if (!kcmc_care_member($user)) throw new DomainException('Access denied.');
    kcmc_ensure_private_storage();
    $path = KCMC_PRIVATE_DATA . '/prayer-care.json';
    $lock = fopen($path . '.lock', 'c+');
    if (!$lock || !flock($lock, LOCK_EX)) throw new RuntimeException('Prayer & Care is busy. Please try again.');
    @chmod($path . '.lock', 0600);
    $tmp = null;
    try {
        $state = kcmc_care_read();
        if ($state['revision'] !== $revision) throw new DomainException('This page changed. Review the latest information and try again.');
        kcmc_care_apply($state, $user, $action, $input, time());
        $state['revision']++;
        kcmc_care_validate($state);
        $raw = json_encode($state, JSON_THROW_ON_ERROR|JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE);
        if (is_file($path)) {
            if (!copy($path, $path . '.previous.json')) throw new RuntimeException('Could not back up Prayer & Care. No update was saved.');
            @chmod($path . '.previous.json', 0600);
        }
        $tmp = $path . '.tmp-' . bin2hex(random_bytes(8));
        if (file_put_contents($tmp, $raw . "\n", LOCK_EX) === false) throw new RuntimeException('Could not save Prayer & Care.');
        @chmod($tmp, 0600);
        if (!rename($tmp, $path)) throw new RuntimeException('Could not save Prayer & Care.');
    } finally {
        if ($tmp !== null && is_file($tmp)) @unlink($tmp);
        flock($lock, LOCK_UN); fclose($lock);
    }
}
