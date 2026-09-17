<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/service-decks.php';

$user = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();

$jobs = kcmc_service_deck_list_jobs($user);
$isPastor = kcmc_can_approve_service_decks($user);
$importConfigured = kcmc_service_deck_import_key_configured();
$csrf = kcmc_csrf();
$messageParam = $_GET['msg'] ?? '';
$errorParam = $_GET['error'] ?? '';
$message = is_string($messageParam) ? substr(trim($messageParam), 0, 300) : '';
$error = is_string($errorParam) ? substr(trim($errorParam), 0, 300) : '';

$displayTime = static function (string $value): string {
    if (trim($value) === '') return 'Unknown time';
    try {
        return (new DateTimeImmutable($value))
            ->setTimezone(new DateTimeZone(KCMC_LOCAL_TIMEZONE))
            ->format('M j, Y g:i A');
    } catch (Throwable) {
        return $value;
    }
};
$displayStatus = static function (string $value): string {
    return ucwords(strtolower(str_replace('_', ' ', $value)));
};
$validHash = static fn(string $value): bool => preg_match('/\A[a-f0-9]{64}\z/', $value) === 1;
?><!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="robots" content="noindex,nofollow,noarchive">
    <title>Sermon Assistant • KCMC Connect</title>
    <link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>">
    <style>
        .deck-layout{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(310px,.88fr);gap:20px;align-items:start}
        .deck-stack{display:grid;gap:20px}.deck-warning{border-color:rgba(214,173,98,.55);background:rgba(214,173,98,.1)}
        .deck-warning h2{font-size:clamp(1.55rem,3vw,2.25rem)}.deck-warning p:last-child{margin-bottom:0}
        .deck-item{position:relative;padding:18px;border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.045)}
        .deck-item-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
        .deck-item-head strong{color:#f1d694}.deck-item-buttons{display:flex;gap:6px;flex-wrap:wrap}
        .deck-item-buttons button{min-height:36px;padding:7px 10px;border-radius:999px;border:1px solid var(--line);background:#173b56;color:#fff;font:inherit;font-weight:800;cursor:pointer}
        .deck-item-buttons button:disabled{cursor:not-allowed;opacity:.42}.deck-fields{display:grid;grid-template-columns:minmax(170px,.42fr) minmax(0,1fr);gap:12px}
        .deck-content{grid-column:1/-1}.deck-form-footer{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
        .deck-form-footer .btn,.deck-form-footer button{font:inherit;cursor:pointer}.deck-help{color:#aebfc9;font-size:.88rem;margin:.2em 0 0}
        .job-list{display:grid;gap:18px}.job-card{border:1px solid var(--line);border-radius:20px;padding:20px;background:rgba(255,255,255,.04)}
        .job-card h3{font-family:Georgia,serif;font-size:1.75rem;font-weight:400;margin:.15em 0}.job-top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
        .job-meta{display:flex;gap:9px;align-items:center;flex-wrap:wrap;color:#aebfc9;font-size:.88rem}.job-hash{display:block;overflow-wrap:anywhere;font:600 .76rem/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;color:#bdd0db}
        .job-section{margin-top:17px;padding-top:16px;border-top:1px solid var(--line)}.job-section h4{margin:0 0 8px}.job-section .portal-form{margin-top:10px}
        .job-history{display:grid;gap:8px;padding:0;margin:10px 0 0;list-style:none}.job-history li{padding-left:13px;border-left:3px solid rgba(214,173,98,.45);color:#c6d4dc}
        .job-history small{display:block;color:#91a8b5}.deck-files{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
        .deck-files label{min-width:0}.btn.danger{background:#7d3030;border-color:#a84c4c}.btn[disabled]{cursor:not-allowed;opacity:.5}
        .status-pill{white-space:nowrap}.empty-jobs{margin:0}.inline-note{margin:.4em 0;color:#aebfc9}
        @media(max-width:900px){.deck-layout{grid-template-columns:1fr}.deck-fields,.deck-files{grid-template-columns:1fr}.deck-content{grid-column:auto}.job-top{display:grid}}
    </style>
</head>
<body class="portal-body">
<main class="portal-shell">
    <header class="portal-top">
        <div>
            <a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a>
            <p class="eyebrow">PRIVATE PASTOR WORKFLOW</p>
            <h1>Sermon Assistant</h1>
            <p class="portal-lead">Prepare an editable Front Porch service deck, review the exact file, and record a pastor’s decision.</p>
        </div>
        <a class="btn secondary" href="<?=kcmc_h(kcmc_url('member/'))?>">Member home</a>
    </header>

    <?php if ($message !== ''): ?><p class="portal-alert success" role="status"><?=kcmc_h($message)?></p><?php endif; ?>
    <?php if ($error !== ''): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>

    <section class="portal-card deck-warning">
        <p class="eyebrow">PRIVATE BY DESIGN</p>
        <h2>Nothing here publishes automatically.</h2>
        <p>Requests and generated files stay in private storage. Download the request for the trusted builder, import only its signed ready package, then have a signed-in pastor review and decide on the exact deck hash.</p>
    </section>

    <div class="deck-layout portal-section">
        <section class="portal-card">
            <p class="eyebrow">NEW REQUEST</p>
            <h2>Plan the service in order.</h2>
            <p class="deck-help">Only the verified Front Porch style is available. Enter Scripture, announcements, and any supplied lyrics exactly as authorized; the assistant does not fetch or invent text.</p>
            <form class="portal-form" method="post" action="<?=kcmc_h(kcmc_url('admin/service-deck-action.php'))?>">
                <input type="hidden" name="csrf" value="<?=kcmc_h($csrf)?>">
                <input type="hidden" name="action" value="create">
                <input type="hidden" name="service_style" value="Front Porch">
                <div class="deck-fields">
                    <label>Service name<input name="service_name" maxlength="160" autocomplete="off" placeholder="Sunday worship" required></label>
                    <label>Service date<input type="date" name="service_date" required></label>
                    <label>Style<input value="Front Porch" disabled aria-describedby="style-help"></label>
                    <p class="deck-help" id="style-help">Style is locked to the approved Front Porch format.</p>
                </div>

                <div id="deck-items" class="deck-stack" aria-label="Ordered service items">
                    <article class="deck-item" data-deck-item>
                        <div class="deck-item-head"><strong>Item <span data-order>1</span></strong><div class="deck-item-buttons"><button type="button" data-move="up" aria-label="Move item up">↑ Up</button><button type="button" data-move="down" aria-label="Move item down">Down ↓</button><button type="button" data-remove aria-label="Remove item">Remove</button></div></div>
                        <div class="deck-fields">
                            <label>Item type<select name="items[0][type]" data-name="type" data-item-type><option value="service_title">Service title</option><option value="song">Song</option><option value="scripture">Scripture</option><option value="sermon_title">Sermon title</option><option value="announcement">Announcement</option><option value="blank">Intentional blank</option></select></label>
                            <label><span data-title-label>Title</span><input name="items[0][title]" data-name="title" maxlength="240" autocomplete="off" data-item-title required></label>
                            <label class="deck-content"><span data-content-label>Optional subtitle</span><textarea name="items[0][text]" data-name="text" rows="6" maxlength="20000" data-item-content placeholder="Optional supporting text"></textarea></label>
                        </div>
                    </article>
                </div>

                <template id="deck-item-template">
                    <article class="deck-item" data-deck-item>
                        <div class="deck-item-head"><strong>Item <span data-order></span></strong><div class="deck-item-buttons"><button type="button" data-move="up" aria-label="Move item up">↑ Up</button><button type="button" data-move="down" aria-label="Move item down">Down ↓</button><button type="button" data-remove aria-label="Remove item">Remove</button></div></div>
                        <div class="deck-fields">
                            <label>Item type<select data-name="type" data-item-type><option value="service_title">Service title</option><option value="song">Song</option><option value="scripture">Scripture</option><option value="sermon_title">Sermon title</option><option value="announcement">Announcement</option><option value="blank">Intentional blank</option></select></label>
                            <label><span data-title-label>Title</span><input data-name="title" maxlength="240" autocomplete="off" data-item-title required></label>
                            <label class="deck-content"><span data-content-label>Optional subtitle</span><textarea data-name="text" rows="6" maxlength="20000" data-item-content placeholder="Optional supporting text"></textarea></label>
                        </div>
                    </article>
                </template>

                <div class="deck-form-footer">
                    <button class="btn secondary" type="button" id="add-deck-item">Add service item</button>
                    <button class="btn gold" type="submit">Create private request</button>
                    <span class="deck-help" id="item-count" aria-live="polite"></span>
                </div>
            </form>
        </section>

        <aside class="deck-stack">
            <section class="portal-card">
                <p class="eyebrow">SAFE HANDOFF</p>
                <h2>Build outside the website.</h2>
                <ol class="portal-list">
                    <li>Create and download the exact request JSON.</li>
                    <li>Run the private builder with the approved archive and shared import key.</li>
                    <li>Import the deck, <code>approval.json</code>, and <code>kcmc-import.json</code>.</li>
                    <li>A pastor downloads and visually reviews the exact deck before deciding.</li>
                </ol>
                <?php if (!$importConfigured): ?><p class="portal-alert warning">Signed package import is unavailable until <code>KCMC_SERMON_IMPORT_KEY</code> is configured privately on the server.</p><?php endif; ?>
                <?php if (!$isPastor): ?><p class="portal-alert warning">You can prepare requests and import signed packages. A pastor administrator must make every approval or change decision.</p><?php endif; ?>
            </section>
        </aside>
    </div>

    <section class="portal-card portal-section">
        <p class="eyebrow">PRIVATE JOB HISTORY</p>
        <h2>Requests and pastor decisions</h2>
        <div class="job-list">
            <?php if (!$jobs): ?><p class="portal-empty empty-jobs">No service-deck requests yet.</p><?php endif; ?>
            <?php foreach ($jobs as $job):
                if (!is_array($job)) continue;
                $jobId = (string)($job['id'] ?? $job['job_id'] ?? '');
                if ($jobId === '') continue;
                $request = is_array($job['request'] ?? null) ? $job['request'] : [];
                $serviceName = (string)($job['service_name'] ?? 'Untitled service');
                $serviceDate = (string)($job['service_date'] ?? '');
                $status = strtoupper((string)($job['status'] ?? 'REQUEST_READY'));
                $requestHash = strtolower((string)($request['sha256'] ?? ''));
                $deckHash = strtolower((string)($job['deck_sha256'] ?? ($job['artifacts']['deck']['sha256'] ?? '')));
                $history = is_array($job['history'] ?? null) ? $job['history'] : [];
                $itemCount = (int)($job['item_count'] ?? 0);
                $canImport = $importConfigured && $status === 'REQUEST_READY';
                $canDecide = $status === 'AWAITING_PASTOR_APPROVAL' && $validHash($deckHash);
            ?>
            <article class="job-card">
                <div class="job-top">
                    <div>
                        <div class="job-meta"><span><?=kcmc_h($serviceDate !== '' ? $serviceDate : 'Date not supplied')?></span><span>•</span><span><?=kcmc_h((string)$itemCount)?> item<?=($itemCount === 1 ? '' : 's')?></span></div>
                        <h3><?=kcmc_h($serviceName)?></h3>
                    </div>
                    <span class="status-pill"><?=kcmc_h($displayStatus($status))?></span>
                </div>
                <p class="job-meta">Created <?=kcmc_h($displayTime((string)($job['created_at'] ?? '')))?> • Job <?=kcmc_h($jobId)?></p>
                <?php if ($validHash($requestHash)): ?><small>Request SHA-256</small><code class="job-hash"><?=kcmc_h($requestHash)?></code><?php endif; ?>
                <?php if ($validHash($deckHash)): ?><small>Exact deck SHA-256</small><code class="job-hash"><?=kcmc_h($deckHash)?></code><?php endif; ?>

                <div class="portal-actions job-section">
                    <a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/service-deck-download.php?job_id=' . rawurlencode($jobId) . '&artifact=request'))?>">Download request JSON</a>
                    <?php if ($validHash($deckHash)): ?><a class="btn gold" href="<?=kcmc_h(kcmc_url('admin/service-deck-download.php?job_id=' . rawurlencode($jobId) . '&artifact=deck'))?>">Download exact deck</a><?php endif; ?>
                </div>

                <?php if ($canImport): ?>
                <div class="job-section">
                    <h4>Import signed ready package</h4>
                    <p class="inline-note">All three files must come from the same trusted builder run.</p>
                    <form class="portal-form" method="post" enctype="multipart/form-data" action="<?=kcmc_h(kcmc_url('admin/service-deck-action.php'))?>">
                        <input type="hidden" name="csrf" value="<?=kcmc_h($csrf)?>">
                        <input type="hidden" name="action" value="import">
                        <input type="hidden" name="job_id" value="<?=kcmc_h($jobId)?>">
                        <div class="deck-files">
                            <label>PowerPoint deck<input type="file" name="deck" accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation" required></label>
                            <label>Approval manifest<input type="file" name="manifest" accept=".json,application/json" required></label>
                            <label>Signed import envelope<input type="file" name="envelope" accept=".json,application/json" required></label>
                        </div>
                        <button class="btn gold" type="submit">Verify and import privately</button>
                    </form>
                </div>
                <?php elseif (!$importConfigured && $status === 'REQUEST_READY'): ?>
                <p class="portal-alert warning job-section">Import is unavailable until the server import key is configured.</p>
                <?php endif; ?>

                <?php if ($canDecide && $isPastor): ?>
                <div class="job-section">
                    <h4>Pastor decision for this exact deck</h4>
                    <p class="inline-note">Download and inspect the deck first. Your current password confirms that this decision comes from your own account.</p>
                    <form class="portal-form" method="post" action="<?=kcmc_h(kcmc_url('admin/service-deck-action.php'))?>">
                        <input type="hidden" name="csrf" value="<?=kcmc_h($csrf)?>">
                        <input type="hidden" name="action" value="approve">
                        <input type="hidden" name="job_id" value="<?=kcmc_h($jobId)?>">
                        <input type="hidden" name="reviewed_deck_sha256" value="<?=kcmc_h($deckHash)?>">
                        <label class="portal-check"><input type="checkbox" name="visual_reviewed" value="1" required><span>I visually reviewed the downloaded deck whose SHA-256 is shown above.</span></label>
                        <label>Current password<input type="password" name="current_password" autocomplete="current-password" required></label>
                        <label>Approval note (optional)<textarea name="notes" maxlength="2000" rows="3"></textarea></label>
                        <button class="btn gold" type="submit">Approve exact deck</button>
                    </form>
                    <form class="portal-form" method="post" action="<?=kcmc_h(kcmc_url('admin/service-deck-action.php'))?>">
                        <input type="hidden" name="csrf" value="<?=kcmc_h($csrf)?>">
                        <input type="hidden" name="action" value="request_changes">
                        <input type="hidden" name="job_id" value="<?=kcmc_h($jobId)?>">
                        <input type="hidden" name="reviewed_deck_sha256" value="<?=kcmc_h($deckHash)?>">
                        <label>Required changes<textarea name="notes" maxlength="2000" rows="4" required></textarea></label>
                        <label>Current password<input type="password" name="current_password" autocomplete="current-password" required></label>
                        <button class="btn danger" type="submit">Request changes</button>
                    </form>
                </div>
                <?php elseif ($canDecide): ?>
                <p class="portal-alert warning job-section">Pastor approval required. A pastor administrator must download, visually review, and decide on this exact deck.</p>
                <?php endif; ?>

                <?php if ($status === 'APPROVED'): ?><p class="portal-alert success job-section">Pastor approval is recorded for this hash. The deck was not published automatically.</p><?php endif; ?>
                <?php if ($status === 'CHANGES_REQUESTED'): ?><p class="portal-alert warning job-section">This hash was not approved. Use the notes below, then create a new private request for the revised service.</p><?php endif; ?>

                <?php if ($history): ?>
                <div class="job-section">
                    <h4>History</h4>
                    <ol class="job-history">
                        <?php foreach (array_reverse($history) as $event): if (!is_array($event)) continue;
                            $eventLabel = (string)($event['action'] ?? $event['event'] ?? $event['status'] ?? 'Updated');
                            $eventAt = (string)($event['at'] ?? $event['created_at'] ?? '');
                            $eventActor = is_array($event['actor'] ?? null) ? (string)($event['actor']['display_name'] ?? '') : '';
                            $eventNotes = (string)($event['notes'] ?? '');
                        ?>
                        <li><?=kcmc_h($displayStatus($eventLabel))?><?php if ($eventAt !== '' || $eventActor !== ''): ?><small><?php if ($eventAt !== ''): ?><?=kcmc_h($displayTime($eventAt))?><?php endif; ?><?php if ($eventAt !== '' && $eventActor !== ''): ?> • <?php endif; ?><?=kcmc_h($eventActor)?></small><?php endif; ?><?php if ($eventNotes !== ''): ?><p><?=nl2br(kcmc_h($eventNotes))?></p><?php endif; ?></li>
                        <?php endforeach; ?>
                    </ol>
                </div>
                <?php endif; ?>
            </article>
            <?php endforeach; ?>
        </div>
    </section>
</main>

<script>
(() => {
    'use strict';
    const list = document.getElementById('deck-items');
    const template = document.getElementById('deck-item-template');
    const addButton = document.getElementById('add-deck-item');
    const count = document.getElementById('item-count');
    const maximumItems = 100;
    if (!list || !template || !addButton || !count) return;

    const labels = {
        service_title: ['Service title', 'Optional subtitle', 'Optional supporting text'],
        song: ['Song title', 'Authorized lyrics (optional for an exact archive match)', 'Paste authorized lyrics, or leave blank to use an exact approved archive match'],
        scripture: ['Scripture reference or title', 'Authorized Scripture text', 'Paste the authorized Scripture text'],
        sermon_title: ['Sermon title', 'Optional supporting text', 'Optional supporting text'],
        announcement: ['Announcement title', 'Authorized announcement text', 'Paste the approved announcement text'],
        blank: ['Optional private label', 'No content for an intentional blank', 'Intentional blank slide']
    };

    const syncType = item => {
        const type = item.querySelector('[data-item-type]');
        const title = item.querySelector('[data-item-title]');
        const content = item.querySelector('[data-item-content]');
        const titleLabel = item.querySelector('[data-title-label]');
        const contentLabel = item.querySelector('[data-content-label]');
        if (!type || !title || !content || !titleLabel || !contentLabel) return;
        const settings = labels[type.value] || labels.song;
        titleLabel.textContent = settings[0];
        contentLabel.textContent = settings[1];
        content.placeholder = settings[2];
        title.required = type.value !== 'blank';
        content.dataset.name = type.value === 'song' ? 'lyrics' : 'text';
        content.required = type.value === 'scripture' || type.value === 'announcement';
        content.disabled = type.value === 'blank';
        if (content.disabled) content.value = '';
    };

    const syncOrder = () => {
        const items = [...list.querySelectorAll('[data-deck-item]')];
        items.forEach((item, index) => {
            const order = item.querySelector('[data-order]');
            if (order) order.textContent = String(index + 1);
            syncType(item);
            item.querySelectorAll('[data-name]').forEach(field => {
                field.name = `items[${index}][${field.dataset.name}]`;
            });
            const up = item.querySelector('[data-move="up"]');
            const down = item.querySelector('[data-move="down"]');
            const remove = item.querySelector('[data-remove]');
            if (up) up.disabled = index === 0;
            if (down) down.disabled = index === items.length - 1;
            if (remove) remove.disabled = items.length === 1;
        });
        addButton.disabled = items.length >= maximumItems;
        count.textContent = `${items.length} of ${maximumItems} items`;
    };

    list.addEventListener('change', event => {
        if (event.target.matches('[data-item-type]')) syncOrder();
    });
    list.addEventListener('click', event => {
        const button = event.target.closest('button');
        const item = event.target.closest('[data-deck-item]');
        if (!button || !item) return;
        if (button.matches('[data-remove]') && list.children.length > 1) item.remove();
        if (button.dataset.move === 'up' && item.previousElementSibling) list.insertBefore(item, item.previousElementSibling);
        if (button.dataset.move === 'down' && item.nextElementSibling) list.insertBefore(item.nextElementSibling, item);
        syncOrder();
    });
    addButton.addEventListener('click', () => {
        if (list.querySelectorAll('[data-deck-item]').length >= maximumItems) return;
        const clone = template.content.cloneNode(true);
        list.appendChild(clone);
        syncOrder();
        const added = list.lastElementChild;
        const select = added && added.querySelector('[data-item-type]');
        if (select) select.focus();
    });
    syncOrder();
})();
</script>
</body>
</html>
