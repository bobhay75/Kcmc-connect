# KCMC Service Agent — Agents for Humans 2026

A newly created Strands Agents project that turns a pastor's service request into an approval-ready, editable worship presentation workflow.

## Problem
Church staff repeatedly search archives, rebuild missing worship slides, apply service-specific formatting, check editability, assemble deliverables, and hand them back for pastoral approval. The work is repetitive but still requires human judgment.

## Agent workflow
1. Receive service type, sermon context, and song list.
2. Search the existing PowerPoint archive first.
3. Reuse editable assets when available.
4. Create drafts only for missing assets.
5. Run editability/quality checks.
6. Produce an approval manifest.
7. Stop for pastor approval — no autonomous publishing.

## Why this is agentic
The Strands agent decides which tools to invoke and in what order. The user provides the service request; the agent performs archive retrieval, asset creation, QA, and handoff preparation, surfacing only exceptions and the final approval decision.

## Human authority
`autopublish` is hard-coded false in the approval manifest. The system is designed to assist ministry production, not make pastoral or theological decisions.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/demo.py
```

For autonomous Strands execution, configure AWS credentials for Amazon Bedrock and call `run_service_request(...)` from `app/service_agent.py`.

## Hackathon disclosure
This Strands-based service agent module is newly created during the Agents for Humans submission period. It may integrate with the pre-existing KCMC Connect website and pre-existing church presentation assets; those pre-existing components are not claimed as newly created contest work.

## Planned competition upgrades
- exact KCMC Traditional / Front Porch / Contemporary visual profiles
- archive indexing and duplicate detection
- sermon/Scripture slide extraction
- complete deck assembly from existing PPTX assets
- approval UI
- AgentCore deployment and tracing
- quantitative demo: time saved and QA defect reduction
