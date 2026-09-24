<?php
$path = __DIR__ . '/../admin/invitation-delivery.php';
$source = file_get_contents($path);
if ($source === false) {
    fwrite(STDERR, "Could not read invitation-delivery.php\n");
    exit(1);
}
$required = [
    "'Invitation sent'",
    'Invitation sent to <strong>',
    'Delivery problem? Show manual fallback',
    'if ($inviteWasSent)',
];
foreach ($required as $needle) {
    if (strpos($source, $needle) === false) {
        fwrite(STDERR, "Missing success-state marker: {$needle}\n");
        exit(1);
    }
}
if (strpos($source, "'Invitation email submitted'") !== false) {
    fwrite(STDERR, "Old ambiguous success heading remains.\n");
    exit(1);
}
echo "invitation success UI static check passed\n";
