<?php
declare(strict_types=1);

// CLI-only. Never load app bootstrap: it can initialize or migrate live stores.
if (PHP_SAPI !== 'cli') { http_response_code(403); exit; }

function kcmc_plan_timestamp(string $value): DateTimeImmutable {
    if (!preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/D', $value)) {
        throw new InvalidArgumentException('An explicit ISO timestamp with timezone is required.');
    }
    try { $time = new DateTimeImmutable($value); }
    catch (Throwable $e) { throw new InvalidArgumentException('Invalid timestamp.'); }
    $errors = DateTimeImmutable::getLastErrors();
    if ($errors !== false && ($errors['warning_count'] || $errors['error_count'])) {
        throw new InvalidArgumentException('Invalid timestamp.');
    }
    return $time;
}

function kcmc_plan_canonical($value): string {
    $normalize = function ($item) use (&$normalize) {
        if ($item instanceof stdClass) {
            $properties = get_object_vars($item);
            ksort($properties, SORT_STRING);
            $result = new stdClass();
            foreach ($properties as $key => $child) $result->{$key} = $normalize($child);
            return $result;
        }
        if (is_array($item)) return array_map($normalize, $item);
        return $item;
    };
    return json_encode($normalize($value), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}

function kcmc_plan_events(stdClass $document): array {
    if (!isset($document->events) || !is_array($document->events)) {
        throw new InvalidArgumentException('A complete content snapshot with an events array is required.');
    }
    $map = [];
    foreach ($document->events as $row) {
        if (!$row instanceof stdClass || !isset($row->id) || !is_string($row->id)
            || !preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$/D', $row->id)) {
            throw new InvalidArgumentException('Every event requires a valid unique string ID.');
        }
        if (array_key_exists($row->id, $map)) throw new InvalidArgumentException('Duplicate event ID.');
        $map[$row->id] = $row;
    }
    return $map;
}

function kcmc_plan_title_key(stdClass $row): string {
    if (!isset($row->title, $row->date) || !is_string($row->title) || !is_string($row->date)) return '';
    return $row->date . '|' . strtolower((string)preg_replace('/\s+/u', ' ', trim($row->title)));
}

function kcmc_plan_skip_reason(stdClass $row, DateTimeImmutable $asOf): ?string {
    if (($row->status ?? null) !== 'published') return 'not_published';
    foreach (['title', 'date', 'time', 'location', 'expires_at'] as $key) {
        if (!isset($row->{$key}) || !is_string($row->{$key}) || trim($row->{$key}) === '') return 'incomplete_event';
    }
    $date = DateTimeImmutable::createFromFormat('!Y-m-d', $row->date, new DateTimeZone('America/Chicago'));
    if (!$date || $date->format('Y-m-d') !== $row->date) return 'invalid_date';
    if (!preg_match('/^(?:0?[1-9]|1[0-2]):[0-5][0-9] (?:AM|PM)$/D', $row->time)) return 'invalid_time';
    try {
        $expires = kcmc_plan_timestamp($row->expires_at);
        if (isset($row->starts_at)) {
            if (!is_string($row->starts_at)) return 'invalid_timestamp';
            if (kcmc_plan_timestamp($row->starts_at) > $asOf) return 'not_yet_published';
        }
    } catch (InvalidArgumentException $e) { return 'invalid_timestamp'; }
    if ($expires <= $asOf) return 'expired';
    if ($row->date < $asOf->setTimezone(new DateTimeZone('America/Chicago'))->format('Y-m-d')) return 'past_date';
    return null;
}

/** Produces a proposal only. It neither returns a merged content document nor writes one. */
function kcmc_event_reconciliation_plan(stdClass $baseline, stdClass $source, stdClass $live, DateTimeImmutable $asOf): array {
    $base = kcmc_plan_events($baseline);
    $repo = kcmc_plan_events($source);
    $host = kcmc_plan_events($live);
    $plan = [
        'schema_version' => 1,
        'mode' => 'read_only_proposal',
        'write_enabled' => false,
        'as_of' => $asOf->format(DateTimeInterface::ATOM),
        'timezone' => 'America/Chicago',
        'requires_unfiltered_host_snapshot' => true,
        'requires_editorial_approval' => true,
        'proposed_additions' => [],
        'already_present' => [],
        'preserved_host_only_ids' => array_values(array_diff(array_keys($host), array_keys($repo))),
        'preserved_missing_baseline_ids' => [],
        'skipped' => [],
        'conflicts' => [],
    ];
    foreach ($repo as $id => $row) {
        if (array_key_exists($id, $base)) {
            // A missing old row may be an intentional editorial deletion. Never restore it automatically.
            if (!array_key_exists($id, $host)) $plan['preserved_missing_baseline_ids'][] = $id;
            $changed = kcmc_plan_canonical($base[$id]) !== kcmc_plan_canonical($row);
            $alreadyMatches = array_key_exists($id, $host) && kcmc_plan_canonical($host[$id]) === kcmc_plan_canonical($row);
            if ($changed && !$alreadyMatches) $plan['conflicts'][] = ['id' => $id, 'reason' => 'repository_changed_existing_event'];
            continue;
        }
        if (array_key_exists($id, $host)) {
            if (kcmc_plan_canonical($host[$id]) === kcmc_plan_canonical($row)) $plan['already_present'][] = $id;
            else $plan['conflicts'][] = ['id' => $id, 'reason' => 'same_id_different_content'];
            continue;
        }
        $reason = kcmc_plan_skip_reason($row, $asOf);
        if ($reason !== null) { $plan['skipped'][] = ['id' => $id, 'reason' => $reason]; continue; }
        $key = kcmc_plan_title_key($row);
        $possibleDuplicates = [];
        foreach ($host as $hostId => $hostRow) {
            if ($key !== '' && kcmc_plan_title_key($hostRow) === $key) $possibleDuplicates[] = $hostId;
        }
        // Also avoid proposing multiple new IDs for an apparently identical event.
        foreach ($plan['proposed_additions'] as $proposed) {
            if ($key !== '' && kcmc_plan_title_key($proposed) === $key) $possibleDuplicates[] = $proposed->id;
        }
        if ($possibleDuplicates !== []) {
            $plan['conflicts'][] = ['id' => $id, 'reason' => 'possible_duplicate_event', 'matching_ids' => $possibleDuplicates];
            continue;
        }
        $plan['proposed_additions'][] = clone $row;
    }
    $plan['status'] = $plan['conflicts'] === [] ? 'ready_for_editorial_review' : 'conflict_review_required';
    $plan['counts'] = [];
    foreach (['proposed_additions', 'already_present', 'preserved_host_only_ids', 'preserved_missing_baseline_ids', 'skipped', 'conflicts'] as $key) {
        $plan['counts'][$key] = count($plan[$key]);
    }
    return $plan;
}

function kcmc_plan_read_snapshot(string $path): array {
    // Local regular files only; no URLs, stream wrappers, symlinks, pipes, or private-store initialization.
    if ($path === '' || $path[0] !== '/' || strpos($path, '://') !== false || is_link($path) || !is_file($path)) {
        throw new InvalidArgumentException('Inputs must be absolute paths to local regular snapshot files.');
    }
    $handle = @fopen($path, 'rb');
    if ($handle === false) throw new RuntimeException('Cannot read an input snapshot.');
    try {
        if (!flock($handle, LOCK_SH)) throw new RuntimeException('Cannot lock an input snapshot for reading.');
        $raw = stream_get_contents($handle, 8388609);
        if ($raw === false || strlen($raw) > 8388608) throw new RuntimeException('Snapshot exceeds the 8 MiB limit or cannot be read.');
        $decoded = json_decode($raw, false, 128, JSON_THROW_ON_ERROR);
        if (!$decoded instanceof stdClass) throw new InvalidArgumentException('Content snapshot must be a JSON object.');
        kcmc_plan_events($decoded);
        return ['document' => $decoded, 'sha256' => hash('sha256', $raw)];
    } finally { fclose($handle); }
}

function kcmc_plan_main(array $arguments): int {
    try {
        if ($arguments === ['--help']) {
            echo "Usage: php tools/plan-event-reconciliation.php --baseline=/absolute/baseline.json --source=/absolute/source.json --live=/absolute/unfiltered-host-snapshot.json --as-of=2026-09-30T04:00:00-05:00\n";
            echo "Read-only JSON proposal on stdout. No apply mode. Never supply an API-filtered response as the host snapshot.\n";
            return 0;
        }
        $options = [];
        foreach ($arguments as $argument) {
            if (!preg_match('/^--(baseline|source|live|as-of)=(.+)$/sD', $argument, $match) || isset($options[$match[1]])) {
                throw new InvalidArgumentException('Use each documented --name=value option exactly once. No write/apply option exists.');
            }
            $options[$match[1]] = $match[2];
        }
        foreach (['baseline', 'source', 'live', 'as-of'] as $required) {
            if (!isset($options[$required])) throw new InvalidArgumentException('Missing required option: ' . $required);
        }
        $asOf = kcmc_plan_timestamp($options['as-of']);
        $inputs = [];
        foreach (['baseline', 'source', 'live'] as $label) $inputs[$label] = kcmc_plan_read_snapshot($options[$label]);
        $plan = kcmc_event_reconciliation_plan($inputs['baseline']['document'], $inputs['source']['document'], $inputs['live']['document'], $asOf);
        $plan['input_sha256'] = array_map(static fn(array $input): string => $input['sha256'], $inputs);
        echo json_encode($plan, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . "\n";
        return $plan['conflicts'] === [] ? 0 : 2;
    } catch (Throwable $error) {
        // Do not echo input bodies, filenames, or arbitrary JSON snippets.
        fwrite(STDERR, "Event plan failed: " . ($error instanceof JsonException ? 'Invalid JSON.' : $error->getMessage()) . "\n");
        return 1;
    }
}

if (realpath((string)($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) exit(kcmc_plan_main(array_slice($argv, 1)));
