<?php
declare(strict_types=1);
const KCMC_WELCOME_DRAFTS = KCMC_PRIVATE_DATA . '/welcome-drafts.json';
function kcmc_welcome_draft_default(array $row): array {
    $name = trim((string)($row['name'] ?? ''));
    $first = preg_split('/\s+/', $name)[0] ?? '';
    if(preg_match("/\A[\p{L}\p{M}'\x{2019}-]{1,80}\z/u", $first)!==1)$first='';
    $greeting = $first !== '' ? 'Hi ' . $first . ',' : 'Hello,';
    $base = 'https://bobsome1.com/kcmc-connect/';
    $contact = kcmc_content()['contact'] ?? [];
    $address = trim((string)($contact['address'] ?? '57 Kimberling City Center Lane, Kimberling City, MO 65686'));
    $phone = trim((string)($contact['phone'] ?? '417-739-4395'));
    $body = $greeting . "\n\nWelcome to Kimberling City Methodist Church! Thank you for reaching out. We look forward to getting to know you.\n\n";
    $service = trim((string)($row['service'] ?? ''));
    if (in_array($service,['8:00 AM — Front Porch Gospel','9:15 AM — Traditional Worship','10:30 AM — Contemporary Worship'],true)) $body .= 'You selected: ' . $service . ".\n\n";
    $body .= "Our Sunday services:\n8:00 AM — Front Porch Gospel\n9:15 AM — Traditional Worship\n10:30 AM — Contemporary Worship\n\n";
    $body .= "Launch Kids Children's Church meets during the 10:30 AM service.\n\nFind us: {$address}\nDirections: https://maps.app.goo.gl/W6kRCHvbaVJ7mwte7\n\n";
    $body .= "YOUR KCMC WELCOME PACKAGE\n" . $base . "welcome-kit.php\n\nCurrent bulletin: " . $base . "bulletin.php\nChurch calendar: " . $base . "church-calendar.html\nExplore groups and church life: " . $base . "#partner\n\n";
    $body .= "If you have an arrival, family or accessibility question, reply to this email or call {$phone}.\n\nCalled to love and serve.\nYour KCMC church family";
    return ['subject'=>'Welcome to KCMC — we’re glad you reached out','body'=>$body,'revision'=>0];
}
function kcmc_welcome_draft_read(string $id, array $row): array {
    $state = kcmc_read_json_store(KCMC_WELCOME_DRAFTS, ['version'=>1,'drafts'=>[]]);
    $draft = $state['drafts'][$id] ?? null;
    return is_array($draft) ? $draft : kcmc_welcome_draft_default($row);
}
function kcmc_welcome_draft_save(string $id, string $subject, string $body, int $revision, string $actor): array {
    if ($id === '' || strlen($id)>160 || trim($subject)==='' || strlen($subject)>200 || preg_match('/[\r\n\x00]/',$subject) || trim($body)==='' || strlen($body)>6000 || str_contains($body,"\0")) return ['ok'=>false,'error'=>'Enter a subject up to 200 bytes and a message up to 6,000 bytes.'];
    return kcmc_update_json_store(KCMC_WELCOME_DRAFTS,['version'=>1,'drafts'=>[]],static function(array &$state) use($id,$subject,$body,$revision,$actor): array {
        $current = (int)($state['drafts'][$id]['revision']??0);
        if ($current !== $revision) return ['ok'=>false,'error'=>'Another staff member saved this draft. Reload before editing again.'];
        $state['drafts'][$id]=['subject'=>trim($subject),'body'=>trim($body),'revision'=>$current+1,'updated_at'=>gmdate('c'),'updated_by'=>$actor];
        return ['ok'=>true];
    });
}
