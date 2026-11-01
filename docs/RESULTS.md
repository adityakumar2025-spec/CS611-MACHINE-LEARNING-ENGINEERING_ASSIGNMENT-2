# Executed model and pipeline results

These are observed results on the supplied data, not estimates of real-world
default performance. Details: evidence/model_comparison.json,
evidence/output_validation.json and evidence/test_results.txt.

Training: 1,031 applications (Jan-Feb 2023). Validation: 941 applications
(Sep-Oct 2023), 190 proxy positives, prevalence 20.19%. Training labels mature
by Aug 2 2023; validation labels mature by Apr 2 2024. Information cutoff is
Apr 30 2024, model available for simulated scoring May 1 2024.

| Validation model | PR-AUC/AP | ROC-AUC | Brier | Precision at .5 | Recall at .5 | Worst-month AP |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.3143 | 0.6323 | 0.1603 | 0.4545 | 0.1053 | 0.3074 |
| HistGradientBoosting | 0.2561 | 0.5864 | 0.1715 | 0.2857 | 0.1053 | 0.2546 |

Logistic Regression is champion. HGB fails the required AP improvement and
worsens Brier and worst-month AP. The full fitted preprocessing/model pipeline
is saved with its schema, cutoff, parameters, lineage hashes and metrics.

Out-of-time May-Jul 2024 evaluation: 1,494 applications, 378 proxy positives;
AP 0.3155, ROC-AUC 0.5706, Brier 0.1891, precision 0.48, recall 0.0635.
The fixed .5 threshold misses many positives and is not a deployable lending
rule. The windows were revised after coverage diagnostics; this is not a
blinded study. Model settings and threshold were fixed throughout.

Scoring: 4,515 applications across May 2024-Jan 2025. Gold tables contain
4,515 predictions, 9 immediate monitoring rows, 135 delayed as-of rows and
189 input-drift rows. Delayed rows retain pending-maturity status and null
outcome metrics until label availability.

Charts under datamart/charts/: stability.png, performance.png, maturity.png,
feature_drift.png. All four were opened and inspected. May/June contain lagged
clickstream variation; July onward has no customer coverage and collapses to
an imputed fallback score (ROC-AUC .5). The drift monitor flags the change.
Earlier cohorts also differ from the early training reference; large PSI calls
for investigation and does not establish a causal explanation.

19 tests pass. Two full runs and a September 2024 backfill preserve canonical
hashes for all four gold tables, excluding the intentionally updated publishing
run identifier. A fresh ZIP Python run regenerates the same data from empty
model/datamart folders. Docker/Airflow and exact-final-ZIP results are recorded
separately in evidence/docker_acceptance.json and
evidence/final_archive_acceptance.json. Clean-extraction Docker build/up, healthy
UI, all nine DAG tasks, repeat replay, configured historical cohort and actual
Airflow CLI backfill passed. Artifacts were generated in independent named
volumes and exported after execution; precomputed sample files were not used
as a substitute for executing the DAG.
