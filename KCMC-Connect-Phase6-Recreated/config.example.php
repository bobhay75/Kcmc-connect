<?php
return [
    'church_email' => 'secretary@umckc.org',
    // Set this to a long random value before first-run setup, or use KCMC_SETUP_KEY env var.
    'setup_key' => '',
    // Optional: set a password hash directly instead of using /admin/setup.php.
    // Generate with: php -r "echo password_hash('YOUR-PASSWORD', PASSWORD_DEFAULT), PHP_EOL;"
    'admin_password_hash' => '',
    'session_name' => 'KCMC_PHASE6_OWNER',
];
