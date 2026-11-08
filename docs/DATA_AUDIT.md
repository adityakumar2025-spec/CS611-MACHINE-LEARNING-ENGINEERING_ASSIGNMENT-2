# Dataset forensic audit

Historical dataset_audit.json and raw_summary.json are preserved under
evidence/historical/. Current runs generate input_contract.json and
feature_contract.json under evidence/ (also exported by CI). Original CSV bytes
are unchanged; data/parts reconstructs them with checksums for the required layout.

| Source | Rows | Customers | Key | Observed dates |
|---|---:|---:|---|---|
| attributes | 12,500 | 12,500 | Customer_ID, snapshot_date | Jan 2023-Jan 2025 |
| financials | 12,500 | 12,500 | Customer_ID, snapshot_date | Jan 2023-Jan 2025 |
| clickstream | 215,376 | 8,974 | Customer_ID, snapshot_date | Jan 2023-Dec 2024 |
| LMS | 137,500 | 12,500 | loan_id, snapshot_date | Jan 2023-Nov 2025 |

No duplicated rows or keys in any source. All 12,500 customers have exactly one
loan. Each loan has installment numbers 0..10 at one-calendar-month intervals,
with no missing periods. Loan amount is always 10,000 and tenure always 10.
Every origin has a complete six-month outcome window in the supplied final
extract. This does not make the label available at historical scoring time.

Clickstream has 8,974 observations in each of its 24 months, with signed integer
fe_1..fe_20 and no raw nulls. Customers originating July 2024-Jan 2025 are absent
from this source. A strict lagged join leaves 4,056 application histories missing
(including January 2023 with no earlier snapshot). Do not inner-join away those
customers: missingness is an important monitored event. Application datasets
retain one row per loan; joins cannot multiply rows.

Attribute and financial snapshots coincide with origination for every customer.
Both are structurally one-to-one with origin, but same-day timestamps do not
establish availability before the application decision. They are audited and
excluded from model inputs. Joining by customer alone would silently discard
this unresolved availability issue.

## Fields and quality

| Family | Observed fields / interpretation | Treatment |
|---|---|---|
| Identity | Customer_ID, loan_id; Name, SSN | Join keys only; names/SSNs never enter feature artifacts |
| Attributes | Age, Occupation | Same-day exclusion; ages parse numerically with 18..100 audit bounds; underscore occupation sentinel is invalid |
| Financial income | Annual_Income, Monthly_Inhand_Salary | Trailing underscore artifacts; audit strips outer underscores, coerces invalids, rejects nonfinite/out-of-range values |
| Accounts/loans | Num_Bank_Accounts, Num_Credit_Card, Num_of_Loan, Type_of_Loan | Negative sentinel -100 and underscore artifacts exist; loan-type nulls 1,426 |
| Credit/repayment | Interest_Rate, Delay_from_due_date, Num_of_Delayed_Payment, Changed_Credit_Limit, Num_Credit_Inquiries, Credit_Mix, Outstanding_Debt, Credit_Utilization_Ratio, Credit_History_Age | Credit mix '_' and changed-limit '_' are missing sentinels; possible repayment-derived leakage further supports exclusion |
| Payment/wealth | Payment_of_Min_Amount, Total_EMI_per_month, Amount_invested_monthly, Payment_Behaviour, Monthly_Balance | Invalid category !@9#%8; malformed/implausible values; excluded |
| Clickstream | fe_1..fe_20 | Anonymous features without business definitions; lagged numeric values, signed negatives preserved, median imputation fitted on train only |
| LMS origin | loan_start_date, loan_amt, tenure, installment_num=0 | loan_start_date is application-date proxy; amount/tenure constant, excluded |
| LMS repayment | snapshot_date, due_amt, paid_amt, overdue_amt, balance, installment_num=1..10 | Target construction only, never model features |

These field meanings are inferred from names and observed sequences; there is
no authoritative data dictionary supplied. In particular, overdue amount is not
days past due. Repayment examples show skipped installments and catch-up payments;
the proxy records any in-window amount breach even after a cure. The overall
six-month severe-arrears proxy rate is 23.728% (2,966 / 12,500). It must not be
reported as a contractual default rate.

No native raw nulls appear outside Type_of_Loan, but sentinel/malformed values
exist. Cleaning-null counts are reported separately from raw-null counts. Audit
bounds are heuristic quality choices; no excluded financial variable is cleaned
and silently introduced into the model. No original values are overwritten.

## Temporal and selection limitations

The final train window contains 1,031 loans, validation contains Sep-Oct 2023
applications, and scoring covers May 2024-Jan 2025. Source snapshot completeness
does not prove historical warehouse ingestion. Prior-month availability and a
one-day label lag are explicit assumptions. The covered population changes
sharply; later missing-history scores may collapse to a constant. This is a data
incident and a production blocker, not a reason to leak same-day information.
