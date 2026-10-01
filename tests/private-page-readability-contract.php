<?php
declare(strict_types=1);
// Source/palette regression checks. Browser fixture renders are separate evidence;
// neither this test nor a successful CI run certifies the live installation.
$root = dirname(__DIR__) . '/KCMC-Connect-Phase6-Recreated/';
$paths = ['admin/health.php', 'admin/audit.php', 'admin/timecards.php', 'member/timeclock.php'];
$checks = 0;
function readability_check(bool $condition, string $label): void {
    global $checks;
    if (!$condition) throw new RuntimeException($label);
    echo 'PASS ' . ++$checks . ': ' . $label . "\n";
}
function readability_luminance(string $hex): float {
    $hex = ltrim($hex, '#');
    if (strlen($hex) === 3) $hex = $hex[0].$hex[0].$hex[1].$hex[1].$hex[2].$hex[2];
    if (!preg_match('/^[0-9a-fA-F]{6}$/D', $hex)) throw new RuntimeException('Invalid fixture color');
    $sum = 0.0;
    foreach ([0.2126, 0.7152, 0.0722] as $index => $weight) {
        $v = hexdec(substr($hex, $index * 2, 2)) / 255;
        $sum += ($v <= 0.04045 ? $v / 12.92 : (($v + 0.055) / 1.055) ** 2.4) * $weight;
    }
    return $sum;
}
function readability_ratio(string $a, string $b): float {
    $a = readability_luminance($a); $b = readability_luminance($b);
    return (max($a, $b) + 0.05) / (min($a, $b) + 0.05);
}
try {
    foreach ($paths as $path) {
        $source = file_get_contents($root . $path);
        readability_check(is_string($source), $path . ': source readable');
        $start = strpos($source, '/* Private-page contrast v2:');
        $end = $start === false ? false : strpos($source, '</style>', $start);
        readability_check($start !== false && $end !== false, $path . ': local inline fix exists');
        $css = substr($source, $start, $end - $start);
        $required = [
            'body.portal-body{--ink:#17324c;--muted:#536273;--line:#607080;background:#eef2f4;color:#17324c;color-scheme:light}',
            '.portal-body :is(.portal-card,.health-stat,.health-check,.audit-row,.audit-empty,.tc-card){background:#fff;color:#17324c}',
            '.portal-body .btn.secondary{background:#fff;color:#17324c;border-color:#607080}',
            '.portal-body .eyebrow{color:#745221}',
            '.portal-body .portal-back{color:#174d75}',
            '.portal-body :is(input:not([type=hidden]),select,textarea){background:#fff;color:#17324c;border:1px solid #607080;color-scheme:light}',
            '.portal-body input::placeholder,.portal-body textarea::placeholder{color:#536273;opacity:1}',
            '.portal-body .portal-alert.error{background:#fbe4e4;color:#7d2525;border-color:#a33434}',
            '.portal-body .portal-alert.success{background:#e6f3e7;color:#215b2d;border-color:#2b7a46}',
            '.portal-body .portal-alert.warning{background:#fff3d6;color:#77510c;border-color:#a06b12}',
            '.portal-body :is(a,button,input,select,textarea,summary):focus-visible{outline:3px solid #174d75;outline-offset:3px}',
        ];
        foreach ($required as $index => $rule) readability_check(str_contains($css, $rule), $path . ': palette/scope rule ' . ($index + 1));
        readability_check(!str_contains($css, '!important'), $path . ': no blanket important override');
        readability_check(str_contains($source, 'kcmc_private_headers();'), $path . ': private response headers retained');
        readability_check(str_contains($source, $path === 'member/timeclock.php' ? 'kcmc_require_login()' : 'kcmc_require_role('), $path . ': access gate retained');
    }
    foreach ([
        ['#17324c','#eef2f4'], ['#17324c','#fff'], ['#536273','#fff'],
        ['#536273','#eef2f4'], ['#745221','#fff'], ['#745221','#eef2f4'],
        ['#174d75','#eef2f4'], ['#607080','#f5f8fa'], ['#7d2525','#fbe4e4'],
        ['#215b2d','#e6f3e7'], ['#77510c','#fff3d6'], ['#18212a','#d6ad62'],
    ] as [$foreground, $background]) {
        readability_check(readability_ratio($foreground, $background) >= 4.5, $foreground . '/' . $background . ': text contrast >= 4.5');
    }
    readability_check(readability_ratio('#fff','#fff') < 4.5, 'negative control detects the original white-button-on-white defect');
    readability_check(readability_ratio('#607080','#fff') >= 3, 'control border contrasts with white background');
    readability_check(readability_ratio('#174d75','#eef2f4') >= 3, 'focus outline contrasts with page background');
    echo "PASS: $checks private-page readability source/palette checks\n";
} catch (Throwable $error) {
    fwrite(STDERR, 'FAIL: ' . $error->getMessage() . "\n");
    exit(1);
}
