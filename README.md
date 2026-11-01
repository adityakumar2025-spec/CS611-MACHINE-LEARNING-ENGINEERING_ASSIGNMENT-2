# CS611 Assignment 2 - Task 1

Run from the extracted project root with Docker Desktop running Linux containers:

```bash
docker-compose build
docker-compose up
```

Open http://localhost:18080 after the health check becomes healthy. Login:
`lecturer` / `lecturer`. The startup log prints this URL. Allow several minutes
for first image download, database migration and DAG discovery. The demo uses
two services: PostgreSQL metadata and Airflow scheduler/webserver. Allocate at
least 4 GB Docker RAM; 6 GB is recommended. Internet is needed to build images.
Both Compose v2's `docker-compose` compatibility executable and `docker compose`
accept the provided file; install a compatibility executable if your system
ships only the latter. Actual availability must be checked on the grading host.

In Airflow find **cs611_task1**, turn its pause toggle off, and click Trigger DAG.
Leave `cohort` null for the full nine-cohort historical replay. Wait for all nine
tasks to succeed. The optional cohort is a month-start from May 2024-Jan 2025.
This is an assignment replay, not live credit decision software.

CLI equivalents, from another terminal:

```bash
docker-compose exec airflow airflow dags list-import-errors
docker-compose exec airflow airflow dags unpause cs611_task1
docker-compose exec airflow airflow dags trigger cs611_task1
docker-compose exec airflow airflow dags list-runs -d cs611_task1
docker-compose exec airflow airflow dags trigger cs611_task1 --conf '{"cohort":"2024-09-01"}'
docker-compose exec airflow airflow dags backfill cs611_task1 -s 2024-09-01 -e 2024-09-01
```

For PowerShell, the UI trigger or `scripts/docker_acceptance.py` avoids shell
JSON quoting differences. CLI backfills derive the cohort from the historical
logical date. A normal manual trigger replays all cohorts unless `cohort` is set.
Scoring is bounded to the supplied historical cohorts. The DAG is paused by
default; its monthly schedule replays the supplied extract. Pause it after review
if leaving the services running. Manual triggers at the current date run all
nine tasks; no task end-date silently excludes current manual runs.

Outputs inside the Airflow container persist across restarts in named volumes:

| Path | Contents |
|---|---|
| /opt/project/model_bank | Registry, fitted full pipeline, reference data, model metadata |
| /opt/project/datamart/gold.sqlite | Four gold tables with unique indexes |
| /opt/project/datamart/gold_*.csv | Reviewable mirrors of gold tables |
| /opt/project/datamart/charts | stability.png, performance.png, maturity.png, feature_drift.png |
| /opt/project/evidence | Runtime contracts, comparison, counts, output validation |
| /opt/airflow/logs | Task logs |

Export generated outputs to the host without requiring bind-mount permissions:

```bash
docker-compose cp airflow:/opt/project/datamart ./generated-datamart
docker-compose cp airflow:/opt/project/model_bank ./generated-model-bank
docker-compose cp airflow:/opt/project/evidence ./generated-evidence
```

The supplied `datamart/` and `model_bank/` contain executed direct-Python sample
results. Docker named volumes start independently and the DAG must generate its
own results. `docker-compose down` retains state. Avoid `down -v` unless you
intend to delete this Compose project's generated data and Airflow history.

For a local Python check (Python 3.12):

```bash
python -m venv .venv
# Activate .venv using your operating system's activation command.
python -m pip install -r requirements.txt
python -m src.pipeline --run-id local-review
python -m pytest -q
python -m src.pipeline --run-id backfill-review --cohort 2024-09-01
```

These commands use relative paths. No private credentials, local interpreter or
developer absolute paths are required in the ZIP. Input discovery also accepts
the originally expected `(1)` filename suffixes in inputs/.

Read [the audit](docs/DATA_AUDIT.md), [temporal policy](docs/TEMPORAL_POLICY.md),
[architecture](docs/ARCHITECTURE.md), [governance/SOP](docs/GOVERNANCE.md), and
[requirements evidence](docs/REQUIREMENTS.md). The predicted target is a
**six-month severe-arrears amount proxy**, not contractual default. Same-day
attributes/financials are excluded. Later clickstream coverage is absent;
monitoring must expose that failure. Threshold 0.5 is illustrative and can have
very low recall. No claim of production suitability is made.

See evidence/acceptance_status.json and docs/PROGRESS.md for actual acceptance
status. Docker/Airflow success must be established from clean ZIP extraction;
direct Python success does not establish those gates. The verified one-line
GitHub repository URL is in Readme.txt. Raw datasets and customer-level outputs
are intentionally excluded from the public repository. The local submission ZIP
includes all four CSVs under data/ and can build independently.
