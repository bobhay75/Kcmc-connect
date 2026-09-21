<?php
return [
    'church_email' => 'secretary@umckc.org',
    'session_name' => 'KCMC_CONNECT_V3',

    // Optional cPanel-friendly direct invitation mail configuration.
    // Keep real values only in the server's preserved config.php, never Git.
    // Environment variables with the matching KCMC_INVITATION_* names override these.
    'invitation_mail_enabled' => false,
    'invitation_from' => '',
    'invitation_from_name' => 'KCMC Connect',
];
// First-run recovery setup uses only the server environment variable KCMC_SETUP_KEY.
