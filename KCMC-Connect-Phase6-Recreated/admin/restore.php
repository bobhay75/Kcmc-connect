<?php
declare(strict_types=1);
require_once __DIR__ . '/../lib/bootstrap.php';
require_once __DIR__ . '/../lib/content-restore.php';
$current = kcmc_require_role(['pastor_admin', 'recovery_admin']);
kcmc_private_headers();
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!kcmc_verify_csrf($_POST['csrf'] ?? null)) {
        $error = 'Please reload and try again.';
    } elseif (trim((string)($_POST['confirm_restore'] ?? '')) !== 'RESTORE') {
        $error = 'Type RESTORE exactly to confirm this recovery action.';
    } elseif (!isset($_FILES['backup']) || !is_array($_FILES['backup'])) {
        $error = 'Choose a KCMC public-content backup JSON file.';
    } elseif ((int)($_FILES['backup']['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        $error = 'The backup upload did not complete successfully.';
    } elseif ((int)($_FILES['backup']['size'] ?? 0) < 1 || (int)($_FILES['backup']['size'] ?? 0) > KCMC_RESTORE_MAX_BYTES) {
        $error = 'Backup file is empty or exceeds the 2 MB restore limit.';
    } else {
        $tmp = (string)($_FILES['backup']['tmp_name'] ?? '');
        if ($tmp === '' || !is_uploaded_file($tmp)) {
            $error = 'The uploaded backup could not be verified.';
        } else {
            $raw = @file_get_contents($tmp);
            if (!is_string($raw)) {
                $error = 'The uploaded backup could not be read.';
            } else {
                try {
                    $result = kcmc_restore_public_content($raw, (string)($current['id'] ?? 'administrator'));
                    if (empty($result['ok'])) {
                        $error = (string)($result['error'] ?? 'Backup validation failed.');
                    } else {
                        kcmc_audit('content.restored', ['bytes' => strlen($raw)]);
                        $success = 'Public KCMC content was restored. The previous live content was automatically preserved in backup storage first.';
                    }
                } catch (Throwable) {
                    $error = 'The restore could not be completed. The current live content remains available for review.';
                }
            }
        }
    }
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Restore Content • KCMC Connect</title><link rel="stylesheet" href="<?=kcmc_h(kcmc_url('styles.css?v=3.0.0'))?>"></head>
<body class="portal-body"><main class="portal-shell portal-narrow">
<a class="portal-back" href="<?=kcmc_h(kcmc_url('admin/'))?>">← Publishing desk</a>
<section class="portal-card"><p class="eyebrow">CONTENT RECOVERY</p><h1>Restore a KCMC public-content backup</h1><p>Use a JSON file downloaded from the KCMC Publishing Desk backup control. Restoring writes only the public content store. Member accounts, invitations, prayer requests, audit history and push subscriptions are separate private data and are not part of this recovery path.</p>
<p class="portal-alert warning">Before the uploaded backup replaces public content, KCMC automatically copies the current live content into backup storage.</p>
<?php if ($error): ?><p class="portal-alert error" role="alert"><?=kcmc_h($error)?></p><?php endif; ?>
<?php if ($success): ?><p class="portal-alert success" role="status"><?=kcmc_h($success)?></p><?php endif; ?>
<form class="portal-form" method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="<?=kcmc_h(kcmc_csrf())?>">
<label>KCMC content backup JSON<input type="file" name="backup" accept="application/json,.json" required></label>
<label>Confirmation<input name="confirm_restore" autocomplete="off" spellcheck="false" placeholder="Type RESTORE" required></label>
<p class="portal-fine">Maximum file size: 2 MB. The file must contain KCMC public sections for contact, announcements, bulletin and events. Files containing private-data sections are rejected.</p>
<button class="btn gold" type="submit">Validate and restore content</button>
</form>
<div class="portal-actions"><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/backup.php'))?>">Download current backup</a><a class="btn secondary" href="<?=kcmc_h(kcmc_url('admin/'))?>">Return to publishing</a></div>
</section></main></body></html>
