<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/public-presentation.php';

function art_check(bool $value, string $label): void {
    if (!$value) throw new RuntimeException($label);
    echo 'PASS: ' . $label . PHP_EOL;
}

$expectedImage = 'assets/visuals/trunk-or-treat-2026.svg';
$expectedAlt = 'Bright autumn Trunk or Treat illustration with decorated car trunks, pumpkins, wrapped candy, lollipops and festive bunting.';
$event = ['id' => 'trunk-or-treat-2026', 'title' => 'Saved event title', 'date' => '2026-10-31', 'description' => 'Saved editorial copy.', 'status' => 'draft', 'image' => 'assets/visuals/trunk-or-treat-2026.webp', 'image_alt' => 'Old photographed flyer', 'custom_field' => 'Keep me'];
$other = ['id' => 'other-event', 'image' => 'assets/visuals/other.webp', 'image_alt' => 'Another event'];
$data = ['contact' => ['office_hours' => 'Saved office hours'], 'events' => [$event, $other], 'custom_section' => ['saved' => true]];
$before = $data;
art_check(kcmc_apply_required_public_content($data), 'legacy event receives current artwork');
$before['events'][0]['image'] = $expectedImage;
$before['events'][0]['image_alt'] = $expectedAlt;
art_check($data === $before, 'only artwork fields change; all authored event, contact and unrelated content survives');
art_check(!kcmc_apply_required_public_content($data), 'artwork migration is idempotent');
$missing = ['contact' => ['office_hours' => 'Saved office hours'], 'events' => []];
kcmc_apply_required_public_content($missing);
art_check(count($missing['events']) === 1 && $missing['events'][0]['image'] === $expectedImage && $missing['events'][0]['image_alt'] === $expectedAlt, 'newly supplied event uses the same illustration and honest alt text');

$storedHash = hash_file('sha256', KCMC_DATA);
$rendered = kcmc_content();
$api = kcmc_public_content();
foreach (['rendered event pages' => $rendered, 'public content API' => $api] as $label => $view) {
    $events = array_values(array_filter($view['events'] ?? [], static fn($item): bool => is_array($item) && ($item['id'] ?? '') === 'trunk-or-treat-2026'));
    art_check(count($events) === 1 && $events[0]['image'] === $expectedImage && $events[0]['image_alt'] === $expectedAlt, $label . ' uses the SVG even with the preserved legacy JSON seed');
}
art_check(hash_file('sha256', KCMC_DATA) === $storedHash, 'public artwork reads never rewrite stored content');
echo 'Trunk or Treat artwork contracts passed.' . PHP_EOL;
