# Task 1 delivery tracker

- [x] All four assignment pages read; full extracted text saved.
- [x] Input inventory and host discovery.
- [x] Dataset forensic audit and temporal policy.
- [x] Minimal executable pipeline.
- [x] Modelling, inference, monitoring and governance.
- [x] Automated QA and local execution (19 tests; repeat/backfill; fresh ZIP Python generation).
- [x] Clean ZIP extraction, Docker build, UI and all nine DAG tasks succeeded.
- [x] Real GitHub URL in one-line Readme.txt (exact Assignment 2 repository verified).

## Environment findings

2026-11-01: Four original CSVs and PDF present in inputs. Git installed;
workspace is initially inside the user's home repository, so create an isolated
project repository. Python 3.12 managed runtime requires sandbox escalation.
Project-local environment installed via PyPI. Docker/docker-compose/docker compose
are absent; WSL lists no distributions. Host RAM 32 GB, free approximately 9.3 GB.
Initial probes were sandbox-limited. Host-side discovery subsequently found
Docker Desktop 4.93.0 / Engine 29.8.1, both Compose commands v5.5.1,
20 engine CPUs and 4,163,051,520 bytes (~3.88 GiB) engine memory. Image build
and pip check pass after aligning pandas to 2.1.4. Existing unrelated containers
own ports 8080/8081; this project uses loopback 18080. Its own UI, metadata DB
and scheduler are healthy. Clean-extraction full DAG, repeat, configured cohort
backfill and actual Airflow CLI backfill all passed. The exact final archive also
passed clean-extraction integration. Verification is repeated after final
documentation/packaging; see evidence/final_archive_acceptance.json.

## Execution milestones

- First vertical slice ran training/reload, scoring and monitoring; archived
  under milestones/vertical_slice, outside final submission.
- Final maturity policy trains Jan-Feb 2023, validates Sep-Oct 2023, freezes
  information Apr 30 2024 and scores May 2024-Jan 2025 (9 cohorts).
- Direct Python produces 4,515 predictions, 9 immediate monitoring rows,
  135 delayed as-of rows and 189 drift rows, plus 4 visually inspected PNGs.
- 19 tests pass; full rerun and September backfill preserve hashes of all four
  gold tables. Fresh ZIP Python generation starts with empty output folders.
- Target is severe_arrears_6m_proxy. July-onward customers lack clickstream;
  monitoring exposes coverage loss and constant fallback scores.
- Exact-match GitHub Assignment 2 repository exists and is public. Data and
  customer-level artifacts are excluded from Git; only source/aggregate evidence.
- Docker: all nine tasks succeeded in the full replay, repeat replay and
  configured September backfill. Actual Airflow CLI September backfill also
  completed successfully with invariant prediction content/counts.
- Runtime artifacts, SQLite/CSV tables and all four charts were exported from
  the container after execution. UI login HTTP 200 and scheduler/DB healthy.

## Authoritative assessment

PDF pages 3-4: 2 marks for compose build/up exposing accessible Airflow;
3 marks for DAG execution producing model artifacts, predictions and performance/
stability monitoring. Required ZIP: DAG, Dockerfile, docker-compose.yaml,
requirements.txt, data/, datamart/, optional utils/, Readme.txt containing only
one GitHub URL. Backfills and leakage prevention explicitly required/encouraged.
Task 2 slides are outside this delivery.
