<?php
declare(strict_types=1);

/** Explicit document chrome only. Loading this helper never writes a response. */
function kcmc_screen_assets(): string {
    return '<link rel="stylesheet" href="' . kcmc_h(kcmc_url('app-theme.css?v=20261015-1')) . '" media="screen">'
        . '<script src="' . kcmc_h(kcmc_url('app-navigation.js?v=20261015-1')) . '" defer></script>'
        . '<style media="print">.screen-navigation{display:none!important}</style>';
}

/** A real local link remains usable when JavaScript or browser history is absent. */
function kcmc_screen_back(string $fallback = ''): string {
    if (!preg_match('/\A[A-Za-z0-9_\/.\-]*\z/', $fallback)
        || str_starts_with($fallback, '/')
        || in_array('..', explode('/', $fallback), true)
        || in_array('.', explode('/', $fallback), true)) {
        $fallback = '';
    }
    return '<a class="screen-back" href="' . kcmc_h(kcmc_url($fallback))
        . '" data-kcmc-back data-kcmc-app-base="' . kcmc_h(kcmc_url()) . '">'
        . '<span aria-hidden="true">←</span> Back</a>';
}

/** Call only from an HTML document; callers decide whether account links apply. */
function kcmc_screen_navigation(string $fallback = '', bool $signedIn = false): string {
    $links = kcmc_screen_back($fallback)
        . '<a href="' . kcmc_h(kcmc_url()) . '">Home</a>';
    return '<nav class="screen-navigation" aria-label="Page controls">' . $links . '</nav>';
}

/** Human-facing form/page failure only; APIs and downloads keep their own responses. */
function kcmc_screen_error(string $message, int $status, string $fallback = 'member/', bool $signedIn = true): never {
    http_response_code($status);
    kcmc_private_headers();
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<meta name="robots" content="noindex,nofollow"><title>Request not completed • KCMC Connect</title>'
        . '<link rel="stylesheet" href="' . kcmc_h(kcmc_url('styles.css?v=3.0.0')) . '">'
        . kcmc_screen_assets() . '</head><body class="portal-body">'
        . kcmc_screen_navigation($fallback, $signedIn)
        . '<main class="portal-shell portal-narrow"><section class="portal-card">'
        . '<h1>Unable to complete this request</h1><p role="alert">' . kcmc_h($message)
        . '</p></section></main></body></html>';
    exit;
}
