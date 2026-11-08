# Validation evidence

Original repository baseline: 9763c04da2fbfa8183c60091c98a23369990e7d2.
The evidence/historical directory preserves earlier records unchanged. They
apply to earlier local/ZIP executions, not the final GitHub revision.

Current direct execution and pytest records have the finalization_ prefix.
Fresh GitHub Actions evidence is published as a workflow artifact keyed to the
tested Git SHA. It includes the exact commit, dependency checks, full/repeat/
cohort/CLI backfill task states, Docker logs and output exports. Each acceptance
record also binds a release_identity hash to code, configuration, documentation
and immutable data parts. Check the run conclusion and tested SHA before relying
on a PASS. A failed or unavailable runtime is an unpassed acceptance gate.

Run python scripts/bootstrap_data.py for local Python use. Docker performs the
same step automatically. All four reconstructed files must match data/SHA256.json.
Run the full pipeline before pytest to exercise the existing integration tests.
The added regression preserves two model versions and deliberately changes one
reference distribution to detect use of the wrong version's reference.

The drift defect was not duplicate business keys: legitimate distinct model
versions shared a feature/cohort. A pivot that omitted model_version failed.
Charts now retain separate version/cohort columns. Monitoring reads the stored
version's reference rather than the latest registry pointer. Existing unique
indexes and deterministic upserts remain in force.

Docker acceptance uses docker compose, checks login HTTP 200, healthy metadata
and scheduler, zero import errors, successful nine-task DAGs, deterministic
prediction content and generated artifacts. The workflow repeats acceptance from
the exact extracted archive. No historical evidence can satisfy packaging's
current content-identity gate.
