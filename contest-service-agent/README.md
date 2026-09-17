# KCMC Service Agent — Agents for Humans 2026

KCMC Service Agent turns a service request into one editable, QA-checked PowerPoint draft and then stops for human approval. The working local pipeline is deterministic and does not need cloud credentials.

## What is complete

- searches a metadata catalog first, then an approved private PowerPoint archive
- refuses to reuse catalog records unless the source deck path and SHA-256 were explicitly confirmed
- indexes archive titles, slide ranges, style metadata, and duplicates without exporting lyrics, notes, or images
- reuses an entire deck or an indexed slide range
- safely imports editable slide content and keeps identically named images from different source decks distinct
- creates missing lyric slides only from text supplied by an authorized human
- applies the verified KCMC lyric baseline: 16:9, black background, centered white Arial Narrow at 60 pt
- checks PowerPoint readability, editable text, geometry, typography, and probable overflow
- assembles one complete service deck in request order
- writes a production report, approval manifest, and offline approval page
- blocks archive path traversal and prevents output from being written inside the private source archive
- keeps `autopublish` false and never sends, uploads, or publishes a result

## Local setup and tests

Python 3.11 or newer is recommended.

```bash
cd contest-service-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Install `requirements.txt` instead when using the optional Strands/Amazon Bedrock entry point.

## Build a service draft

Keep the real PowerPoint archive outside the repository (or under an ignored private directory). Then run:

```bash
python app/cli.py data/service-request.sample.json \
  --catalog data/private/kcmc-song-catalog.json \
  --archive /absolute/path/to/approved-private-archive \
  --out build/sunday-front-porch
```

The request JSON contains `service_name`, `service_style`, and a `songs` array. Each song needs a title and may include authorized lyrics. Missing lyrics are not fetched, inferred, or invented.

The command exits with status 0 when every requested item is ready for review and status 2 when human input or selection is still required. Either way, it writes a report and approval materials. A complete run produces:

- `<service-name>.pptx` — editable assembled draft
- `draft-assets/` — newly generated song decks
- `production-report.json` — progress, QA, blockers, and counts
- `approval.json` — approval state initialized with no decision
- `approval.html` — offline review page that only downloads a decision file

## Build a private archive catalog

```bash
python app/archive_extractor.py /absolute/path/to/approved-private-archive \
  --confirmation-manifest /absolute/path/to/confirmed-decks.json \
  --out data/private/kcmc-song-catalog.json
```

The confirmation manifest is private JSON in this form:

```json
{
  "approved_decks": [
    {"source_deck": "relative/path/service.pptx", "sha256": "64-character-sha256"}
  ]
}
```

Only exact path-and-hash matches are indexed. Missing entries and changed files are reported as unconfirmed and excluded. The catalog contains metadata only. Generated decks can contain supplied lyrics, so generated output, the confirmation manifest, and the source archive must remain private unless a human explicitly approves their destination.

## Human authority and scope

Every run ends in `AWAITING_PASTOR_APPROVAL`; `approved` and `autopublish` remain false. The approval page has no network access and cannot send or publish. Live KCMC Connect integration, deployment, AgentCore hosting, and tracing are separate operations and are not performed by this local build.

The optional Strands entry point remains in `app/service_agent.py`. Amazon Bedrock use requires separately configured AWS credentials.

## Hackathon disclosure

This service-agent module was created during the Agents for Humans submission period. It may work with the pre-existing KCMC Connect website and church presentation assets; those pre-existing components are not claimed as newly created contest work.
