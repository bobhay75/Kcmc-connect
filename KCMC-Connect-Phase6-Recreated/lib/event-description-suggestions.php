<?php
declare(strict_types=1);

/**
 * Editor-only suggestions, not a content migration. No reads or writes occur here.
 * Source: data/content.json at 904cc12080a8eff38f319fa4ef2afd985f8f8f64,
 * the September event records and news.groups/news.outreach already in the app.
 * Unknown or changed events receive no suggestion. Never replace existing text.
 */
function kcmc_event_description_suggestion(array $event): ?array {
    if (array_key_exists('description', $event) &&
        (!is_string($event['description']) || trim($event['description']) !== '')) return null;
    $id = $event['id'] ?? null;
    if (!is_string($id)) return null;
    $references = [
        'griefshare-0902' => [
            'title' => 'GriefShare begins', 'date' => '2026-09-02', 'time' => '9:30 AM', 'location' => 'KCMC',
            'text' => 'GriefShare begins at KCMC on September 2 at 9:30 AM.',
            'source' => 'Existing September event listing. This is a brief schedule summary; no additional program details were recorded.',
        ],
        'mens-breakfast-0905' => [
            'title' => 'Men’s Ministry Breakfast', 'date' => '2026-09-05', 'time' => '8:30 AM', 'location' => 'KCMC Fellowship Hall',
            'text' => 'Men’s Ministry breakfast and fellowship in the KCMC Fellowship Hall.',
            'source' => 'Existing September event listing and church-news group description.',
        ],
        'adult-bible-study-0913' => [
            'title' => 'Adult Bible Study with Linda Rann', 'date' => '2026-09-13', 'time' => '10:15 AM', 'location' => 'KCMC',
            'text' => 'Adult Bible Study with Linda Rann at KCMC on September 13 at 10:15 AM.',
            'source' => 'Existing September event listing. This is a brief schedule summary; no study topic or additional details were recorded.',
        ],
        'ladies-fellowship-0917' => [
            'title' => 'KCMC Ladies Fellowship', 'date' => '2026-09-17', 'time' => '12:30 PM', 'location' => 'KCMC Fellowship Hall',
            'text' => 'KCMC Ladies Fellowship meets September 17 at 12:30 PM; bring a sack lunch. Harbor House leadership will share the program.',
            'source' => 'Existing September church-news outreach note.',
        ],
        'jaffe-potluck-0929' => [
            'title' => 'Potluck and Michael Jaffe presentation', 'date' => '2026-09-29', 'time' => '5:00 PM', 'location' => 'KCMC',
            'text' => 'The September 29 potluck begins at 5:00 PM, followed by Michael Jaffe’s presentation at 6:00 PM.',
            'source' => 'Existing September church-news outreach note.',
        ],
    ];
    if (!isset($references[$id])) return null;
    $reference = $references[$id];
    $expected = ['id' => $id];
    foreach (['title', 'date', 'time', 'location'] as $field) {
        if (($event[$field] ?? null) !== $reference[$field]) return null;
        $expected[$field] = $reference[$field];
    }
    return ['text' => $reference['text'], 'source' => $reference['source'], 'expected' => $expected];
}
