<?php
$designerPath = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php';
$storePath = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-projects.php';
$src = file_get_contents($designerPath);
$store = file_get_contents($storePath);

$designerChecks = [
  "protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "private headers" => "kcmc_private_headers()",
  "shared project endpoint" => "publication-projects.php",
  "structured item serializer" => "items:[...page.querySelectorAll('.item')].map(itemData)",
  "print PDF path" => "window.print()",
  "publisher templates" => 'data-template="flyer"',
  "KCMC asset library" => 'id="assetLibrary"',
];
foreach ($designerChecks as $label => $needle) {
    if (strpos($src, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
foreach (['kimberling-city-missouri-bridge-2024.jpg', 'data/content.json', 'localStorage.setItem'] as $forbidden) {
    if (strpos($src, $forbidden) !== false) { fwrite(STDERR, "FAIL: forbidden designer content $forbidden\n"); exit(1); }
}

$storeChecks = [
  "store protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "store CSRF" => "kcmc_verify_csrf",
  "private publication store" => "publications.json",
  "validated item types" => "['text', 'shape', 'image']",
  "approved asset allowlist" => "kcmc-building-2024.webp",
  "atomic private-store helper" => "kcmc_update_json_store",
  "audit record" => "publication_project_saved",
];
foreach ($storeChecks as $label => $needle) {
    if (strpos($store, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
foreach (['innerHTML', 'data/content.json', 'base64_decode'] as $forbidden) {
    if (strpos($store, $forbidden) !== false) { fwrite(STDERR, "FAIL: unsafe store token $forbidden\n"); exit(1); }
}
echo "publication designer shared-storage contract OK\n";
