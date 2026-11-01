# Architecture and decisions

## ADR 1: local, inspectable pipeline

Use Airflow 2.10.5 with Python 3.12 and LocalExecutor, a PostgreSQL 16 metadata
database, and one application container running scheduler and webserver. This is
a local grading deployment, with no Redis, Celery, cloud account or credentials.
Persistent named volumes hold logs, working data, model bank, gold data and
execution evidence. Input CSVs are baked into the image read-only by convention.
The host UI port is bound to loopback. Two web workers and single-thread ML
keep the demo within a modest memory budget. Docker resources must be measured
on an installed engine; host memory alone does not establish container capacity.

Stages: validate_inputs -> prepare_features -> train_models -> register_model ->
historical_inference -> publish_predictions -> compute_monitoring ->
publish_monitoring -> validate_outputs. The DAG serializes runs and tasks.
Each stage reads persistent artifacts; no dataframes or models enter XCom.
Inputs are validated before transformation. The same Python functions power
the DAG and direct integration tests. Failures remain visible at task level.

## ADR 2: SQLite gold datamart and file model bank

PostgreSQL stores Airflow metadata only. SQLite stores four gold tables with
unique indexes; CSV mirrors make review convenient. Publication prepares a
staging table and swaps it transactionally. A retry converges on the same keys.
Single-writer orchestration prevents concurrent update races; this is not a
distributed datamart design. CSV export is atomic per file; it can be regenerated
if a crash occurs between database commit and CSV replacement.

Model bank: model_bank/<content-version>/pipeline.joblib, metadata.json and
reference.pkl. registry.json points at the selected champion. The version hashes
input hashes, source, feature policy, parameters and sklearn version. The full
imputer/scaler/estimator is saved. A checksum and schema gate protect retrieval.
Reference data contain only anonymous model inputs and model scores. Joblib
artifacts are loaded only from this trusted, locally generated model bank.

Both candidates are fitted once on training data. Selection uses mature temporal
validation only. Natural class prevalence is retained for calibrated probability
estimation; average precision is used for imbalance-aware comparison, together
with Brier loss, worst-month performance and simplicity. No resampling occurs
across time boundaries. Threshold 0.5 is a fixed demonstration policy, not a
cost-sensitive lending rule. Low recall at this threshold is reported honestly.

## ADR 3: conservative historical availability

See TEMPORAL_POLICY.md. Source data lack application time and ingestion time.
Monthly lagged clickstream is the only nonconstant feature family with a
defensible prior-date join. Same-day financials/attributes are excluded. A
six-month outcome horizon yields an explicit maturity embargo. A frozen model
is replayed only after all training and selection information would be available.
This is a simulated historical pipeline, not evidence of a real past deployment.

## ADR 4: missing coverage is an outcome to monitor

Clickstream covers 8,974 customers; later applicants are absent from it.
The final replay begins May 2024, allowing observation of covered May/June
cohorts followed by the July coverage collapse. The window was revised after
execution and coverage inspection, not through parameter or threshold tuning.
The holdout is an out-of-time engineering evaluation, not a pristine blinded
study. All experiments use fixed model settings and the same strict feature rule.
Fallback probabilities remain visible for the assignment; production policy
requires manual review when features disappear. Do not confuse successful
pipeline execution with useful lending performance.

## Gold keys

| Table | Unique key | Purpose |
|---|---|---|
| gold_predictions | loan_id, model_version, scoring_date | Application scores and provenance |
| gold_monitoring_immediate | application_cohort, model_version | Volume, missingness, score quantiles and PSI |
| gold_feature_drift | application_cohort, model_version, feature | Input PSI and missingness vs training |
| gold_monitoring_delayed | application_cohort, model_version, monitoring_asof | Explicit historical outcome availability and performance |

Prediction IDs are used for joining/audit only, never as model inputs. Repeated
prediction publication updates pipeline_run_id to the last publishing run;
probabilities and business keys stay deterministic. Model version changes are
kept as distinct rows for comparison. When changing temporal policy, use a fresh
Compose project/volumes to avoid mixing experiments in the final acceptance.
