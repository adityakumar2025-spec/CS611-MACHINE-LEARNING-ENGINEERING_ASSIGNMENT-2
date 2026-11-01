# Validation gates and how to repeat them

The automated suite covers raw hashes, schema/key rejection, malformed numerics,
labels and horizon completeness, future-repayment perturbation, strict lagged
joins, future-clickstream perturbation, same-day fallback rejection, borrower
and maturity isolation, train-only preprocessing, serialization identity, metric
correctness, null/one-class handling, PSI behavior, champion policy, transactional
upsert/unique keys, output structure and backfill score identity.

`python scripts/final_qa.py` starts with empty output directories after moving
previous artifacts into milestones/. It executes the full pipeline twice,
then replays September 2024, comparing canonical hashes of all four tables.
The run identifier is intentionally omitted from the prediction hash because
it records the most recent publishing run. It runs pytest, builds a candidate
ZIP, extracts it into a new directory, verifies each manifest hash, attempts
Docker acceptance, then regenerates all outputs from the extracted code/data
with empty output directories. The final local extraction check reuses the
project Python environment; it is not a fresh dependency-installation test.

`python scripts/docker_acceptance.py --root <fresh-extraction>` requires the
lecturer's actual docker-compose command. It builds and runs Compose, verifies
login HTTP 200 and healthy database/scheduler, triggers all nine tasks via the
Airflow API, waits for success, repeats a full run, triggers a September cohort
backfill, verifies invariant score contents/counts and exports model/gold/chart
artifacts. It records every gate and terminates the Compose services while
preserving named volumes. UI defaults are lecturer/lecturer on loopback 18080.
Use a fresh extraction/Compose project to avoid reusing old data volumes.

The script exits 77 when docker-compose is absent, 1 on a failed gate, and 0
only on passed integration acceptance. Its failure is evidence of an unpassed
gate, never evidence that the Docker deployment works.

The packaging script labels an artifact VALIDATED only when Docker/Airflow
acceptance is recorded PASS and Readme.txt contains a real supplied repository
URL. Never manually edit the status to bypass these checks. Before final handoff,
verify the final updated ZIP is itself extracted and passes the same gates.

## Sources used for implementation

- [Official Airflow Docker guide](https://airflow.apache.org/docs/apache-airflow/2.10.5/howto/docker-compose/index.html)
- [Airflow 2.10.5 PythonOperator](https://airflow.apache.org/docs/apache-airflow/2.10.5/howto/operator/python.html)
- [Scikit-learn SimpleImputer](https://scikit-learn.org/1.5/modules/generated/sklearn.impute.SimpleImputer.html)
- [Scikit-learn HistGradientBoostingClassifier](https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)

Local implementation, test logs and the assignment PDF are the evidence for
project-specific results; library documentation alone cannot prove execution.
