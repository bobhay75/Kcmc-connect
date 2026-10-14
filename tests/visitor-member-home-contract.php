<?php
declare(strict_types=1);
require_once __DIR__ . '/../KCMC-Connect-Phase6-Recreated/lib/bootstrap.php';

$source = file_get_contents(__DIR__ . '/../KCMC-Connect-Phase6-Recreated/index.php');
$start = strpos($source, '  <section class="section welcome-next home-next"');
$end = strpos($source, '  <section class="section" aria-label="KCMC kids and family photos">', $start);
$section = substr($source, $start, $end - $start);
$kcmcPhoneHref = 'tel:4177394395';
$kcmc = ['bulletin' => ['date' => '2026-09-27']];
$today = new DateTimeImmutable('today', new DateTimeZone(KCMC_LOCAL_TIMEZONE));
$make = static fn(string $title, string $date, string $status = 'published'): array => ['title' => $title, 'date' => $date, 'status' => $status, 'time' => '10:30 AM', 'location' => 'KCMC'];
$events = [
    $make('Yesterday', $today->modify('-1 day')->format('Y-m-d')),
    $make('Invalid date', '2026-02-31'),
    $make('Hidden event', $today->format('Y-m-d'), 'draft'),
    $make('Today <script>alert(1)</script>', $today->format('Y-m-d')),
    $make('Tomorrow', $today->modify('+1 day')->format('Y-m-d')),
    $make('Third event', $today->modify('+2 days')->format('Y-m-d')),
    $make('Fourth event', $today->modify('+3 days')->format('Y-m-d')),
];
$kcmcEvents = kcmc_active_items($events);
usort($kcmcEvents, 'kcmc_compare_event_start');
ob_start();
eval('?>' . $section);
$html = ob_get_clean();
$check = static function(bool $ok, string $message): void {
    if (!$ok) throw new RuntimeException($message);
    echo "PASS: {$message}\n";
};
$check(substr_count($html, '<li>') === 3, 'homepage limits preview to three upcoming gatherings');
$check(!str_contains($html, 'Yesterday') && !str_contains($html, 'Invalid date') && !str_contains($html, 'Hidden event') && !str_contains($html, 'Fourth event'), 'past, invalid, unpublished and excess events are omitted');
$check(str_contains($html, 'Today &lt;script&gt;') && !str_contains($html, '<script>alert'), 'published event titles are escaped');
$check(str_contains($html, 'Sep 27, 2026'), 'published bulletin date is honestly displayed');
$check(str_contains($html, 'data-route="visit"') && str_contains($html, 'href="bulletin.php"') && str_contains($html, 'data-route="events"'), 'visitor, bulletin and event destinations are available without an account');
$kcmcEvents = [];
ob_start();
eval('?>' . $section);
$empty = ob_get_clean();
$check(str_contains($empty, 'More gathering dates will appear here when published.') && str_contains($empty, 'tel:4177394395'), 'empty calendar offers a useful office contact');
