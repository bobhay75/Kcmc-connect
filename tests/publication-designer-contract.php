<?php
$path = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php';
$src = file_get_contents($path);
$checks = [
  "protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "private headers" => "kcmc_private_headers()",
  "browser-only project storage" => "kcmc-publications-v1",
  "print PDF path" => "window.print()",
  "publisher templates" => 'data-template="flyer"',
  "no content.json write" => "data/content.json",
];
foreach ($checks as $label => $needle) {
    if ($label === 'no content.json write') {
        if (strpos($src, $needle) !== false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
        continue;
    }
    if (strpos($src, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
echo "publication designer contract OK\n";
