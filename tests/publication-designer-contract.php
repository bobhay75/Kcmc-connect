<?php
$designerPath = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php';
$storePath = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-projects.php';
$mediaPath = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-media.php';
$src = file_get_contents($designerPath);
$store = file_get_contents($storePath);
$media = file_get_contents($mediaPath);

$designerChecks = [
  "protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "private headers" => "kcmc_private_headers()",
  "shared project endpoint" => "publication-projects.php",
  "shared media endpoint" => "publication-media.php",
  "structured item serializer" => "items:[...page.querySelectorAll('.item')].map(itemData)",
  "print PDF path" => "window.print()",
  "publisher templates" => 'data-template="flyer"',
  "KCMC asset library" => 'id="assetLibrary"',
  "shared media library" => 'id="sharedMediaLibrary"',
  "editable project name" => 'id="projectName"',
  "duplicate preserves shared storage" => "Independent copy ready — click Save",
  "multi-page controls" => 'id="pageIndicator"',
  "twelve-page cap" => "pageState.length>=12",
  "multi-page serializer" => "pages:pageState.map",
  "shared media id serializer" => "mediaId:el.dataset.mediaId",
  "multipart upload" => "new FormData()",
  "all-page print renderer" => "renderPrintPages()",
  "undo control" => 'id="undoBtn"',
  "redo control" => 'id="redoBtn"',
  "duplicate object control" => 'id="duplicateItemBtn"',
  "bring to front control" => 'id="bringFrontBtn"',
  "bring forward control" => 'id="bringForwardBtn"',
  "send backward control" => 'id="sendBackwardBtn"',
  "send to back control" => 'id="sendBackBtn"',
  "document history snapshot" => "function snapshotDocument()",
  "document undo" => "function undo()",
  "document redo" => "function redo()",
  "arrange selected object" => "function arrangeSelected(action)",
  "duplicate selected object" => "function duplicateSelectedItem()",
  "native input shortcut guard" => "active.matches('input,textarea,select')",
  "print waits for images" => "img.onload=resolve",
];
foreach ($designerChecks as $label => $needle) {
    if (strpos($src, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
foreach (['kimberling-city-missouri-bridge-2024.jpg', 'data/content.json', 'localStorage.setItem', 'prompt(', 'FileReader', 'readAsDataURL'] as $forbidden) {
    if (strpos($src, $forbidden) !== false) { fwrite(STDERR, "FAIL: forbidden designer content $forbidden\n"); exit(1); }
}

$storeChecks = [
  "store protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "store CSRF" => "kcmc_verify_csrf",
  "private publication store" => "publications.json",
  "validated item types" => "['text', 'shape', 'image']",
  "approved asset allowlist" => "kcmc-building-2024.webp",
  "validated shared media id" => "pub_media_exists",
  "shared media id format" => "pubmedia_[a-f0-9]{24}",
  "atomic private-store helper" => "kcmc_update_json_store",
  "audit record" => "publication_project_saved",
  "multi-page validator" => "Publication must contain between 1 and 12 pages.",
  "legacy one-page migration" => "pub_normalize_project",
  "store version two" => '$state[\'version\'] = 2;',
];
foreach ($storeChecks as $label => $needle) {
    if (strpos($store, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
foreach (['innerHTML', 'data/content.json', 'base64_decode'] as $forbidden) {
    if (strpos($store, $forbidden) !== false) { fwrite(STDERR, "FAIL: unsafe store token $forbidden\n"); exit(1); }
}

$mediaChecks = [
  "media protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "media private headers" => "kcmc_private_headers()",
  "media CSRF" => "kcmc_verify_csrf",
  "private media directory" => "KCMC_PRIVATE_DATA . '/publication-media'",
  "private media metadata" => "KCMC_PRIVATE_DATA . '/publication-media.json'",
  "five MB upload cap" => "KCMC_PUBLICATION_MEDIA_MAX_BYTES = 5242880",
  "MIME sniffing" => "finfo_open(FILEINFO_MIME_TYPE)",
  "image verification" => "getimagesize",
  "verified upload" => "is_uploaded_file",
  "random media id" => "kcmc_random_id('pubmedia')",
  "private file move" => "move_uploaded_file",
  "nosniff response" => "X-Content-Type-Options: nosniff",
  "no silent eviction" => "publication_media_capacity",
  "media audit" => "publication_media_uploaded",
];
foreach ($mediaChecks as $label => $needle) {
    if (strpos($media, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
foreach (['data/content.json', 'public_html', 'base64_decode', 'image/svg+xml'] as $forbidden) {
    if (strpos($media, $forbidden) !== false) { fwrite(STDERR, "FAIL: unsafe media token $forbidden\n"); exit(1); }
}

echo "publication designer shared-media contract OK\n";
