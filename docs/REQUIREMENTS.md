# Requirement-to-evidence matrix

Source of authority: inputs/Assignment 2.pdf, all 4 pages read. The extracted
text is in evidence/assignment_full_text.txt. User's mission strengthens the
assignment requirements; no Task 2 slides will be created.

| Requirement | Acceptance evidence / gate |
|---|---|
| Compose build/up exposes Airflow (2 marks, PDF p3) | PASS: clean-extraction build/up logs; own container running; UI login HTTP 200; scheduler/database healthy |
| Working complete DAG (3 marks, p4) | PASS: all nine task states success; model/gold/chart artifacts exported; evidence/docker_acceptance.json |
| Train/evaluate/select and model bank (p1) | Candidate metrics, selection policy, versioned fitted pipelines and metadata |
| Model retrieval and inference over time (p1) | Gold prediction table, multiple application cohorts, per-row model lineage |
| Performance/stability gold tables (p1) | Gold monitoring tables with maturity and insufficient-sample handling |
| Real monitoring visualisation (p1) | Generated PNGs over monthly cohorts, inspected visually |
| Governance, refresh SOP, deployment choices (p1) | docs/GOVERNANCE.md |
| Backfill support (p2) | Repeated run and historical-cohort backfill equality tests |
| No leakage (p3) | Strict feature timestamps, mature labels, embargoed chronological splits, adversarial tests |
| Exact ZIP structure (p3) | Packaging manifest includes DAG, Dockerfile, compose, requirements, data/, datamart/, Readme.txt |
| Readme.txt one real GitHub URL (p3) | PASS: existing exact Assignment 2 repository discovered and verified; one-line URL |
| Private/raw-data handling (user) | Raw datasets excluded from Git; included only in local submission ZIP |
| Reproducibility (user) | Pinned runtime, input hashes, seed, model metadata, clean extraction test |

Passing unit tests or direct Python execution does not satisfy Docker/Airflow
acceptance. A candidate ZIP must not be described as validated while those gates
remain unexecuted.
