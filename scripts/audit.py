from pathlib import Path
import hashlib, json
import pandas as pd

root = Path(__file__).resolve().parents[1]
result = {}
for p in sorted((root / 'inputs').glob('*.csv')):
    d = pd.read_csv(p, low_memory=False)
    key = ['loan_id','snapshot_date'] if 'loan_id' in d else ['Customer_ID','snapshot_date']
    info = dict(rows=len(d), columns=list(d), dtypes=d.dtypes.astype(str).to_dict(),
                nulls=d.isna().sum().to_dict(), duplicates=int(d.duplicated().sum()),
                duplicate_keys=int(d.duplicated(key).sum()), customers=d.Customer_ID.nunique(),
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    for c in ['snapshot_date','loan_start_date','installment_num','tenure','loan_amt','overdue_amt']:
        if c in d:
            info[c] = dict(min=str(d[c].min()), max=str(d[c].max()), unique=int(d[c].nunique()))
    if 'loan_id' in d:
        info['loans']=d.loan_id.nunique()
        info['monthly_rows']=d.groupby('snapshot_date').size().to_dict()
        info['installments']=d.groupby('installment_num').size().to_dict()
        info['origination_months']=d.drop_duplicates('loan_id').groupby('loan_start_date').size().to_dict()
        info['customer_loan_counts']=d.groupby('Customer_ID').loan_id.nunique().value_counts().to_dict()
    else:
        info['monthly_rows']=d.groupby('snapshot_date').size().to_dict()
        categorical=['Age','Occupation','Type_of_Loan','Credit_Mix','Payment_of_Min_Amount','Payment_Behaviour']
        info['categories']={c:d[c].value_counts(dropna=False).head(15).to_dict() for c in categorical if c in d}
    result[p.name]=info
(root/'evidence/dataset_audit.json').write_text(json.dumps(result,indent=2,default=int),encoding='utf8')
print(json.dumps(result,indent=2,default=int))
