<?php
require_once __DIR__ . '/lib/bootstrap.php';
// Preserve incoming links without serving the retired monthly newsletter.
header('Cache-Control: no-store, max-age=0');
header('Location: ./#news', true, 302);
exit;
