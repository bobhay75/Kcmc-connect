<?php
require_once __DIR__ . '/../lib/bootstrap.php';
kcmc_private_headers();
$user = kcmc_require_role(['pastor_admin']);
$message = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) { http_response_code(403); exit('Invalid request.'); }
    $prayerId = (string)($_POST['prayer_id'] ?? '');
    $action = (string)($_POST['action'] ?? '');
    if (!in_array($action, ['approve', 'private', 'close'], true)) { http_response_code(422); exit('Invalid action.'); }
    $changed = kcmc_update_json_store(KCMC_PRAYERS, ['version' => 1, 'prayers' => []], function (array &$state) use ($prayerId, $action, $user): bool {
        foreach ($state['prayers'] as &$prayer) {
            if (($prayer['id'] ?? '') !== $prayerId) continue;
            if ($action === 'approve' && ($prayer['audience'] ?? '') === 'members') {
                $prayer['status'] = 'approved'; $prayer['approved_at'] = gmdate('c'); $prayer['approved_by'] = (string)$user['id'];
            } elseif ($action === 'private') {
                $prayer['status'] = 'private'; $prayer['audience'] = 'pastors_only'; $prayer['approved_at'] = null; $prayer['approved_by'] = null;
            } elseif ($action === 'close') {
                $prayer['status'] = 'closed';
            } else return false;
            $prayer['updated_at'] = gmdate('c');
            return true;
        }
        unset($prayer);
        return false;
    });
    if ($changed) { kcmc_audit('prayer.moderated', ['prayer_id' => $prayerId, 'action' => $action]); $message = 'Prayer request updated.'; }
}
$store = kcmc_read_json_store(KCMC_PRAYERS, ['version' => 1, 'prayers' => []]);
$prayers = array_values(array_filter($store['prayers'] ?? [], fn($p) => is_array($p) && ($p['status'] ?? '') !== 'closed'));
usort($prayers, fn($a, $b) => strcmp((string)($b['created_at'] ?? ''), (string)($a['created_at'] ?? '')));
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Prayer Approvals • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head><body class="portal-body"><main class="portal-shell"><header class="portal-top"><div><a class="portal-back" href="<?=kcmc_h(kcmc_url('member/'))?>">← Member home</a><p class="eyebrow">PASTOR APPROVALS</p><h1>Prayer privacy and sharing</h1><p class="portal-lead">Nothing reaches the member wall until a pastor approves it.</p></div><a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/prayer-team.php'))?>">Prayer team inbox</a></header><?php if ($message): ?><p class="portal-alert success"><?=kcmc_h($message)?></p><?php endif; ?><section class="portal-card"><div class="prayer-list"><?php if (!$prayers): ?><p class="portal-empty">No active requests.</p><?php endif; ?><?php foreach ($prayers as $prayer): ?><article class="prayer-card private"><div class="prayer-meta"><strong><?=kcmc_h((string)($prayer['public_name'] ?? 'Anonymous'))?></strong><span class="status-pill"><?=kcmc_h(ucwords((string)($prayer['status'] ?? 'received')))?></span><time><?=kcmc_h(date('M j, Y g:i A', strtotime((string)$prayer['created_at'])))?></time></div><p><?=nl2br(kcmc_h((string)$prayer['message']))?></p><small><?=($prayer['audience'] ?? '') === 'members' ? 'Member sharing requested' : 'Pastors and prayer team only'?></small><form class="portal-actions" method="post"><input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>"><input type="hidden" name="prayer_id" value="<?=kcmc_h((string)$prayer['id'])?>"><?php if (($prayer['audience'] ?? '') === 'members' && ($prayer['status'] ?? '') !== 'approved'): ?><button class="btn gold" name="action" value="approve">Approve for members</button><?php endif; ?><button class="btn secondary" name="action" value="private">Keep private</button><button class="btn secondary" name="action" value="close">Close request</button></form></article><?php endforeach; ?></div></section></main></body></html>
