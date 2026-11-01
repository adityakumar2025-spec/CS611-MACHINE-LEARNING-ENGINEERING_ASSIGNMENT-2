# Prediction and temporal correctness policy

The observed data contain repayment snapshots, not a contractual default flag,
charge-off event, days-past-due field, or a default definition. The target is
`severe_arrears_6m_proxy`: at any of installments 1 through 6, outstanding
overdue amount is at least three scheduled installments (loan amount / tenure).
This is an amount-based severe delinquency proxy, NOT a verified 90-DPD/default
event. A cured delinquency still counts if it breached the threshold in-window.
Each loan needs all six monthly observations, even when an early breach occurs.
Label available time is the sixth snapshot plus one day (assumed ingestion lag).
Incomplete windows remain unknown and are never negatives.

Application is represented by loan_start_date; there is no separate application
timestamp. All snapshots are monthly, despite the LMS filename saying daily.
Features must be from a snapshot at least one calendar month before origination;
this assumes monthly aggregates are final and available by the next month.
There are no ingestion timestamps or upstream feature definitions. The lag is a
conservative availability assumption, not proof of operational availability.

Attributes and financials each contain exactly one record per customer, dated
on origination. Without within-day availability they are excluded from modelling.
Name, SSN and customer/loan identifiers are never model features. All repayment
fields are target-only. Constant loan amount and tenure provide no predictive
variation and are excluded. Lagged fe_1..fe_20 are anonymous clickstream inputs;
negative values are valid signed values until a source dictionary says otherwise.
An explicit missing-clickstream indicator is included; missing histories are not
filled from future snapshots. No scaling/imputation is fitted before splitting.

Training: applications Jan-Feb 2023; preprocessing fitted only on these loans.
Validation: Sep-Oct 2023; labels mature by Apr 2 2024. Training labels mature
by Aug 2 2023, before the first validation application. The six-month embargo
Mar-Aug 2023 prevents training-label overlap with validation applications.
Candidate fitting/selection is replayed at Apr 30 2024 after validation matures.
Selection uses only these historical validation labels. Validation predictions
are diagnostic development outputs, not published historical scores.

Model is available from May 1 2024 (information cutoff Apr 30 2024).
Score May 2024-Jan 2025 applications with this frozen historical champion.
Nov 2023-Apr 2024 loans are intentionally unused: selection-label maturity separation.
Held-out May-Jul 2024 performance is reported only after selection, never used
to choose features, parameters, model or threshold. All subsequent cohorts are
out-of-time monitoring, not independent development validation.

Monitoring replays month-end as-of dates; outcomes are exposed only once the
entire six-month horizon and one-day lag have elapsed. The final observation
cutoff is the last LMS snapshot + one day. No frozen-later-model retrospective
mode is used. Historical model availability is enforced on every scored row.
