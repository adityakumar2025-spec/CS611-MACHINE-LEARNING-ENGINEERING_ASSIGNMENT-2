# Governance, retraining SOP and deployment options

## Ownership and cadence

For this demonstration the pipeline owner is the ML engineer; proposed production
owners are Credit Risk (target and decision policy), Data Engineering (availability
and contracts), Model Risk (independent validation and promotion), and MLOps
(deployment, monitoring, rollback). These are proposed roles, not actual signoffs.

Run immediate quality/stability monitoring per scoring batch and review monthly.
Replay performance at month end, only after a complete six-month outcome horizon
plus the assumed one-day ingestion lag. Review champion/challenger quarterly.
At least 30 mature labels are needed for displayed metrics. One-class cohorts
have undefined discrimination and show null PR-AUC/ROC-AUC with explicit status.
No label, outcome rate or calibration metric is imputed before maturity.

## Proposed alerts (governance choices, not regulatory standards)

- Input or score PSI >= 0.10: amber investigation; >= 0.25: red investigation.
- Clickstream missingness > 20 percentage points above the training reference,
  a completely missing feature family, invalid keys or schema: red data incident.
- Scoring volume differs > 30% from the previous comparable month: investigate
  business calendar effects and ingestion completeness before model action.
- Mature-cohort AP falls > 0.05 below validation AP, or Brier increases > 0.03,
  in two successive adequately sized cohorts: open model review. Always compare
  prevalence, cohort size and data coverage; AP varies with prevalence.
- One cohort with fewer than 30 labels or one class: report insufficient evidence,
  accumulate a longer window and do not interpret null discrimination as zero.

The generated immediate alert field implements the PSI levels. Missingness,
volume and delayed-performance triggers are review SOPs, not autonomous retraining
actions. The actual July-onward loss of feature coverage is a red incident.
The assignment retains fallback scores to demonstrate monitoring; production
would suspend automated credit decisions and send applications to manual review.

## Refresh and promotion SOP

1. Investigate and repair upstream coverage first. Retraining on missing data
   alone does not repair a missing source. Validate source SLAs/feature meanings.
2. Obtain an approved contractual default definition and application-time data
   contract. Reconcile repayments, horizon, cures, exclusions and label maturity.
3. Build a new dated dataset using only information available at each origin;
   record hashes, schema, ETL policy, code revision and maturity cutoff.
4. Reserve a later untouched evaluation window. Use maturity embargoes and
   grouped borrower isolation if repeat loans occur. Fit preprocessing on train.
5. Train baseline/challenger; report AP, ROC, Brier, recall, precision, counts,
   uncertainty and segment/fairness diagnostics. This submission does not validate
   fairness, causal effects, economic losses or real-world default performance.
6. Compare against the existing model on the same cohorts and availability rules.
   Current automatic demonstration rule promotes HGB only with AP improvement
   >= .01, Brier degradation <= .01 and worst-month AP degradation <= .02;
   otherwise retain Logistic Regression. Reassess thresholds on development data
   using agreed business costs; never tune on monitoring/test outcomes.
7. Require Credit Risk and Model Risk approval before production. Version the
   full fitted pipeline and evidence, shadow-score, then canary a limited share.
8. Record approved model version, activation time, reviewer and rollback target.
   Production artifact activation must be later than all training/selection data.

## Rollback

Keep the last approved artifact and metadata immutable. Pause scheduled scoring
on schema failures or severe instability, restore the prior approved registry
pointer after compatibility checks, replay a small known batch and compare
scores, then resume. Never overwrite prior gold rows with a different model
version under the same model ID. Log incident, reasons, affected cohorts and
resolution. Rebuild corrupt outputs from immutable inputs and the pinned model.

## Deployment choices

- Submitted option: local Compose batch scoring, file model bank and SQLite
  datamart; appropriate for lecturer execution and a small demonstration.
- Production batch: separately supervised Airflow scheduler/webserver/workers,
  managed relational metadata, object-store versioned artifacts, transactional
  warehouse gold tables, secret manager, CI validation and resource isolation.
- Online service: an authenticated API loads the same fitted pipeline and schema,
  obtains features from an application-time feature service, logs model/version
  and request IDs, and feeds delayed outcomes back into the batch monitor.

The latter choices are documented options, not provisioned services. Demo
credentials are local-only defaults; rotate credentials and configure proper
authentication/TLS before any remote deployment.
