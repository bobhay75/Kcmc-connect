<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/public-presentation.php';
function verify(bool $ok, string $message): void {
    if (!$ok) { fwrite(STDERR, "FAIL: $message\n"); exit(1); }
    echo "PASS: $message\n";
}
$notes = ["The answer is ______.  Keep these spaces.", "<script>not executable</script>", "Mary Lou’s Friday update"];
$input = [
    'news' => ['title' => 'The Bridge to Salvation', 'highlights' => ['private-looking monthly metrics']],
    'announcements' => [
        ['id' => 'sep-news-16', 'title' => 'Retired monthly newsletter'],
        ['id' => 'front-pew-friday', 'title' => 'Mary Lou newsletter and Friday schedule'],
        ['id' => 'owner-announcement', 'status' => 'hidden', 'body' => 'Keep this hidden'],
    ],
    'bulletin' => ['notes' => $notes],
    'events' => [['id' => 'approved-event', 'status' => 'hidden', 'description' => 'Keep exactly as supplied']],
];
$before = serialize($input);
$out = kcmc_public_content_view($input);
verify(!isset($out['news']), 'monthly source is absent from public output');
verify(array_column($out['announcements'], 'id') === ['front-pew-friday', 'owner-announcement'], 'only the named retired announcement is filtered');
verify($out['bulletin']['notes'] === $notes, 'message wording, blanks, spaces and literal text are preserved');
verify($out['events'] === $input['events'], 'event content and hidden state are not rewritten');
verify(serialize($input) === $before, 'editorial model is not mutated');
verify(kcmc_public_content_view($out) === $out, 'public filtering is idempotent');
$stored = hash_file('sha256', KCMC_DATA);
kcmc_public_content();
verify(hash_file('sha256', KCMC_DATA) === $stored, 'public content read does not write persisted content');
$root = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/';
foreach (['index.php', 'api/content.php'] as $file) {
    verify(str_contains((string)file_get_contents($root.$file), 'kcmc_public_content()'), "$file uses the public projection");
}
$home = (string)file_get_contents($root.'index.php');
verify(!preg_match('/bridge|Verified members only|The Bridge to Salvation|Sermon library|Search sermons/i', $home), 'public homepage excludes retired branding and wording');
verify(str_contains($home, 'data-end-time') && str_contains($home, 'data-kcmc-form="visit"'), 'calendar and connection workflows are retained');
verify(substr_count($home, 'data-hero-photo') === 5, 'hero contains all five reviewed church and ministry photos');
verify(str_contains($home, 'kcmc-ministry-group.jpg') && str_contains($home, 'KCMC ministry group gathered for a church community photo'), 'ministry group gallery photo has useful alt text');
verify(str_contains($home, 'trunk-or-treat-2026.webp') && str_contains($home, 'KCMC families and community members at the 2026 Trunk or Treat'), 'Trunk-or-Treat gallery photo has useful alt text');
verify(str_contains((string)file_get_contents($root.'bulletin.php'), 'kcmc_h($note)'), 'bulletin notes remain escaped, not interpreted');
verify(!str_contains((string)file_get_contents($root.'sw.js'), 'kimberling-city-missouri-bridge'), 'offline precache excludes the retired bridge photo');
verify(str_contains((string)file_get_contents($root.'news.php'), "Location: ./#news"), 'old newsletter URL redirects to current updates');
echo "Tony launch cleanup contract passed.\n";
