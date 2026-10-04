<?php
$path = __DIR__ . '/../KCMC-Connect-Phase6-Recreated/admin/publication-designer.php';
$src = file_get_contents($path);
$checks = [
  "protected admin role" => "kcmc_require_role(['pastor_admin', 'recovery_admin'])",
  "private headers" => "kcmc_private_headers()",
  "browser-only project storage" => "kcmc-publications-v1",
  "print PDF path" => "window.print()",
  "publisher templates" => 'data-template="flyer"',
  "KCMC asset library" => 'id="assetLibrary"',
  "editable project name field" => 'id="projectName"',
  "duplicate creates a distinct named copy" => "function duplicate(){const source=currentProjectName();projectId=null;projectName.value=source.slice(0,72)+' - Copy';save();",
  "project restoration passes through sanitizer" => "page.replaceChildren(sanitizeSavedMarkup(p.html))",
  "restoration has a tag allowlist" => "new Set(['DIV','SPAN','IMG','BR','B','STRONG','I','EM','U'])",
  "restoration has a style allowlist" => "styleProps.has(key)",
  "no bridge asset" => 'kimberling-city-missouri-bridge-2024.jpg',
  "no content.json write" => "data/content.json",
];
if (strpos($src, "prompt(") !== false) { fwrite(STDERR, "FAIL: browser prompt removed from naming workflow\\n"); exit(1); }
if (strpos($src, "page.innerHTML=p.html") !== false) { fwrite(STDERR, "FAIL: saved markup restored without sanitizer\\n"); exit(1); }
foreach ($checks as $label => $needle) {
    if ($label === 'no content.json write' || $label === 'no bridge asset') {
        if (strpos($src, $needle) !== false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
        continue;
    }
    if (strpos($src, $needle) === false) { fwrite(STDERR, "FAIL: $label\n"); exit(1); }
}
echo "publication designer contract OK\n";
