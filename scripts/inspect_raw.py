import csv, collections, json
from pathlib import Path
result={}
for p in (Path(__file__).resolve().parents[1] / 'data').glob('*.csv'):
    with p.open(newline='',encoding='utf8') as f:
        rows=list(csv.DictReader(f))
    dates=collections.Counter(r['snapshot_date'] for r in rows)
    info={'rows':len(rows),'customers':len({r['Customer_ID'] for r in rows}),'dates':dict(sorted(dates.items()))}
    if 'loan_id' in rows[0]:
        loans={r['loan_id']:r for r in rows}
        info['loans']=len(loans)
        info['loan_start_counts']=dict(sorted(collections.Counter(r['loan_start_date'] for r in loans.values()).items()))
        info['max_installment']=dict(sorted(collections.Counter(r['installment_num'] for r in loans.values()).items()))
        info['overdue_positive']=sum(float(r['overdue_amt'])>0 for r in rows)
        info['loan_counts_per_customer']=dict(collections.Counter(collections.Counter(r['Customer_ID'] for r in loans.values()).values()))
    result[p.name]=info
Path('evidence/raw_summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
