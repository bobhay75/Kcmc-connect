<?php
declare(strict_types=1);
// Exercise the actual save closure with synthetic in-memory state. No bootstrap,
// authentication, HTTP, private store, or audit operation is invoked.
$sourcePath = $argv[1] ?? __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-projects.php';
$case = $argv[2] ?? 'all';
$source = file_get_contents($sourcePath);
if (!is_string($source) || !in_array($case, ['all', 'new', 'update'], true)) {
    fwrite(STDERR, "Usage: php publication-project-retention-contract.php [SOURCE.php] [all|new|update]\n");
    exit(1);
}
$matched = preg_match('/kcmc_update_json_store\(\$storePath, \$defaultStore, (function \(array &\$state\) use \(\$project\): void \{[\s\S]*?\n\})\);/', $source, $match);
if ($matched !== 1) {
    fwrite(STDERR, "Could not extract the exact publication save closure\n");
    exit(1);
}
$closureSource = $match[1];

function retention_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, "FAIL: {$message}\n");
        exit(1);
    }
    echo "PASS: {$message}\n";
}

function retention_project(int $number): array {
    $item = ['type' => 'text', 'text' => " \tOriginal {$number}\n\n________\n\t ", 'x' => 70, 'y' => 80, 'w' => 600, 'h' => 90];
    $media = ['type' => 'image', 'mediaId' => 'pubmedia_' . str_repeat('a', 24), 'alt' => 'Synthetic shared photograph'];
    $record = ['id' => 'pub_' . sprintf('%024x', $number), 'name' => "Original {$number}",
               'updated' => gmdate('c', 1700000000 + $number), 'updated_by' => 'synthetic-owner'];
    // Preserve both legacy and multi-page records, not only IDs or list length.
    if ($number % 2 === 0) {
        $record['pages'] = [['pageSize' => 'letter', 'orientation' => 'portrait', 'items' => [$item, $media]],
                            ['pageSize' => 'half', 'orientation' => 'landscape', 'items' => [$item]]];
    } else {
        $record['pageSize'] = 'letter';
        $record['orientation'] = 'portrait';
        $record['items'] = [$item, $media];
    }
    return $record;
}

function retention_state(int $count): array {
    $projects = [];
    for ($number = 1; $number <= $count; $number++) $projects[] = retention_project($number);
    return ['version' => 2, 'projects' => $projects, 'unrelated_fixture' => ['preserve' => true]];
}

function retention_save(string $closureSource, array $project, array &$state): void {
    // The closure captures this project's value exactly as the real endpoint does.
    $save = eval('return ' . $closureSource . ';');
    if (!$save instanceof Closure) throw new RuntimeException('Save closure was not callable');
    $save($state);
}

function retention_index(array $state): array {
    $index = [];
    foreach ($state['projects'] as $project) {
        retention_check(!isset($index[$project['id']]), 'saved project IDs remain unique');
        $index[$project['id']] = $project;
    }
    return $index;
}

if ($case === 'all' || $case === 'new') {
    $state = retention_state(50);
    $originals = $state['projects'];
    $project = retention_project(51);
    $project['updated'] = '2031-01-01T00:00:00Z';
    retention_save($closureSource, $project, $state);
    retention_check(count($state['projects']) === 51, '51st save must preserve every existing publication');
    $index = retention_index($state);
    foreach ($originals as $original) {
        retention_check(isset($index[$original['id']]) && $index[$original['id']] === $original,
                        '51st save preserves original ID and all authored/page/media content: ' . $original['id']);
    }
    retention_check($index[$project['id']] === $project, '51st new publication is saved intact');
    retention_check($state['unrelated_fixture'] === ['preserve' => true], 'save preserves unrelated state');
}

if ($case === 'all' || $case === 'update') {
    $state = retention_state(51);
    $originals = $state['projects'];
    $project = retention_project(25);
    $project['name'] = 'Updated publication';
    $project['updated'] = '2031-01-02T00:00:00Z';
    $project['items'][0]['text'] = "Updated only this project\n\n________";
    retention_save($closureSource, $project, $state);
    retention_check(count($state['projects']) === 51, 'update must preserve every other existing publication');
    $index = retention_index($state);
    foreach ($originals as $original) {
        $expected = $original['id'] === $project['id'] ? $project : $original;
        retention_check(isset($index[$expected['id']]) && $index[$expected['id']] === $expected,
                        'update preserves each unaffected ID/content and replaces only its target: ' . $expected['id']);
    }
    retention_check($state['unrelated_fixture'] === ['preserve' => true], 'update preserves unrelated state');
}
echo "Publication save-retention closure checks passed; all projects are synthetic.\n";
