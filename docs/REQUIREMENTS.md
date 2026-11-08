# Task 1 requirement-to-implementation matrix

Authority: supplied Assignment 2 requirements PDF, all four pages inspected.
Task 2 slide creation is outside the user's Task 1 finalization request.

| Requirement | Implementation and verification gate |
|---|---|
| Complete Airflow DAG | dags/cs611_task1.py; nine serial stage functions; actual task states required |
| Dockerfile | Airflow 2.10.5 / Python 3.12, pinned application dependencies, automatic data reconstruction |
| docker-compose.yaml | PostgreSQL, scheduler/webserver, loopback UI, persistent volumes and health checks |
| requirements.txt | Pinned application versions; pip check and test installation |
| data/ | Original CSVs reconstructed byte-for-byte from versioned gzip parts; SHA256 checks |
| datamart/ | Tracked empty folder; runtime SQLite/CSV and four charts |
| Readme.txt | Exactly one line containing the target GitHub URL |
| Training and model bank | Mature temporal train/validation, two candidates, versioned fitted pipeline |
| Inference across time | May 2024-Jan 2025, 4,515 predictions, model lineage |
| Monitoring gold tables | Immediate stability, per-feature drift, delayed mature performance |
| Visualization | Four generated PNGs; multiple model versions retained |
| Backfill and reruns | Unique indexes/upserts; full/repeat/cohort/CLI acceptance |
| Governance | GOVERNANCE.md: refresh SOP, thresholds, ownership, deployment options |
| Independent examiner | README clean-clone Docker path; workflow acceptance required |

File presence is a structural gate. Runtime PASS requires current real execution
and cannot be inferred from earlier reports or direct Python tests alone.
