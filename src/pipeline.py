"""Persistent, task-sized ML stages; also runnable without Airflow for QA.

All historical availability dates are simulated information cutoffs. Artifact
creation timestamps retain the actual execution time and never masquerade as
historical deployment evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import platform
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (average_precision_score, roc_auc_score,
    precision_score, recall_score, f1_score, brier_score_loss, confusion_matrix)
from threadpoolctl import threadpool_limits

ROOT = Path(os.environ.get('PROJECT_ROOT', Path(__file__).resolve().parents[1]))
FEATURES = [f'fe_{i}' for i in range(1, 21)] + ['click_missing']
TARGET = 'severe_arrears_6m_proxy'
CUTOFF = pd.Timestamp('2024-04-30')
AVAILABLE = pd.Timestamp('2024-05-01')
POLICY = 'strict_prior_month_severe_arrears_6m_v1'


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf8')
    temp.replace(path)


def paths(root=ROOT):
    root = Path(root)
    for folder in ['work', 'model_bank', 'datamart', 'datamart/charts', 'evidence']:
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def input_paths(root):
    folder = root / 'data' if (root / 'data/lms_loan_daily.csv').exists() else root / 'inputs'
    found = {}
    for name in ['lms_loan_daily', 'feature_clickstream', 'features_attributes', 'features_financials']:
        candidates = [p for p in folder.glob(f'{name}*.csv')]
        if len(candidates) != 1:
            raise ValueError(f'Expected exactly one {name} CSV, found {candidates}')
        found[name] = candidates[0]
    return found


def numeric(series, lower=None, upper=None):
    """Strip surrounding underscore artifacts; reject embedded corruption/inf."""
    x = pd.to_numeric(series.astype('string').str.strip().str.strip('_'), errors='coerce')
    x = x.astype(float).replace([np.inf, -np.inf], np.nan)
    if lower is not None:
        x = x.where(x >= lower)
    if upper is not None:
        x = x.where(x <= upper)
    return x


def read_inputs(root):
    return {name: pd.read_csv(p, low_memory=False) for name, p in input_paths(root).items()}


def validate_frames(frames):
    schemas = {
        'lms_loan_daily': ['loan_id', 'Customer_ID', 'loan_start_date', 'tenure', 'installment_num', 'loan_amt', 'due_amt', 'paid_amt', 'overdue_amt', 'balance', 'snapshot_date'],
        'feature_clickstream': ['Customer_ID', 'snapshot_date'] + FEATURES[:-1],
        'features_attributes': ['Customer_ID', 'Name', 'SSN', 'Age', 'Occupation', 'snapshot_date'],
        'features_financials': ['Customer_ID', 'snapshot_date', 'Annual_Income', 'Monthly_Inhand_Salary', 'Num_of_Loan', 'Outstanding_Debt'],
    }
    for name, required in schemas.items():
        d = frames[name]
        if not set(required).issubset(d.columns):
            raise ValueError(f'{name}: missing columns {set(required)-set(d.columns)}')
        key = ['loan_id','snapshot_date'] if name == 'lms_loan_daily' else ['Customer_ID','snapshot_date']
        if d[key].isna().any().any() or d.duplicated(key).any():
            raise ValueError(f'{name}: null or duplicate keys')
        pd.to_datetime(d.snapshot_date, errors='raise', format='%Y-%m-%d')
    lms = frames['lms_loan_daily']
    for c in ['tenure','installment_num','loan_amt','due_amt','paid_amt','overdue_amt','balance']:
        x = numeric(lms[c], lower=0)
        if x.isna().any():
            raise ValueError(f'Invalid loan numeric: {c}')
    if (lms.tenure <= 0).any() or (lms.loan_amt <= 0).any():
        raise ValueError('Invalid loan terms')
    for c in ['loan_start_date','Customer_ID','loan_amt','tenure']:
        if lms.groupby('loan_id')[c].nunique().max() != 1:
            raise ValueError(f'Inconsistent loan metadata: {c}')
    if lms.duplicated(['loan_id','installment_num']).any():
        raise ValueError('Duplicate installment')
    actual = pd.to_datetime(lms.snapshot_date)
    expected = pd.Series([pd.Timestamp(s) + pd.DateOffset(months=int(n))
                          for s,n in zip(lms.loan_start_date,lms.installment_num)], index=lms.index)
    if not actual.equals(expected):
        raise ValueError('Installment dates do not follow monthly schedule')
    initial = lms[lms.installment_num == 0]
    if initial.loan_id.nunique() != lms.loan_id.nunique():
        raise ValueError('Missing origination row')
    if initial.Customer_ID.duplicated().any():
        raise ValueError('Repeated borrowers require grouped temporal isolation policy')
    for name in ['features_attributes','features_financials']:
        if not set(frames[name].Customer_ID).issubset(set(initial.Customer_ID)):
            raise ValueError(f'{name}: orphan customers')


def validate_inputs(root=ROOT, **kwargs):
    root = paths(root)
    data = read_inputs(root)
    validate_frames(data)
    summary = {}
    for name,d in data.items():
        p = input_paths(root)[name]
        summary[name] = dict(rows=len(d), customers=int(d.Customer_ID.nunique()),
            columns=list(d), nulls=d.isna().sum().astype(int).to_dict(),
            start=str(d.snapshot_date.min()), end=str(d.snapshot_date.max()),
            sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    # Profile malformed values without promoting same-day data into features.
    bounds = {'Age':(18,100), 'Annual_Income':(0,1e7), 'Num_of_Loan':(0,100),
              'Outstanding_Debt':(0,1e8), 'Monthly_Inhand_Salary':(0,1e6)}
    for name in ['features_attributes','features_financials']:
        summary[name]['cleaning_null_counts'] = {c:int(numeric(data[name][c],*b).isna().sum())
                                                 for c,b in bounds.items() if c in data[name]}
    summary['policy'] = POLICY
    dump(root/'evidence/input_contract.json', summary)
    return 'evidence/input_contract.json'


def make_labels(lms):
    origin = lms[lms.installment_num == 0][['loan_id','Customer_ID','loan_start_date','loan_amt','tenure']].copy()
    origin['application_date'] = pd.to_datetime(origin.pop('loan_start_date'))
    obs = lms[lms.installment_num.between(1,6)].copy()
    obs['breach'] = obs.overdue_amt >= 3 * obs.loan_amt / obs.tenure - 1e-8
    aggregated = obs.groupby('loan_id').agg(observations=('installment_num','nunique'), breach=('breach','max'))
    out = origin.merge(aggregated, on='loan_id', how='left', validate='one_to_one')
    out[TARGET] = np.where(out.observations.eq(6), out.breach.astype(float), np.nan)
    out['label_available_date'] = out.application_date.map(lambda x: x + pd.DateOffset(months=6) + pd.Timedelta(days=1))
    return out.drop(columns=['observations','breach'])


def attach_clicks(loans, clicks):
    c = clicks.copy()
    c['feature_snapshot_date'] = pd.to_datetime(c.pop('snapshot_date'))
    for col in FEATURES[:-1]:
        c[col] = numeric(c[col])
    left = loans.copy()
    left['feature_cutoff'] = left.application_date.map(lambda x:x-pd.DateOffset(months=1))
    out = pd.merge_asof(left.sort_values('feature_cutoff'), c.sort_values('feature_snapshot_date'),
        left_on='feature_cutoff', right_on='feature_snapshot_date', by='Customer_ID',
        direction='backward', tolerance=pd.Timedelta(days=32))
    out['click_missing'] = out.feature_snapshot_date.isna().astype(int)
    if len(out) != len(loans) or out.loan_id.duplicated().any():
        raise ValueError('Join multiplied loans')
    if (out.feature_snapshot_date > out.feature_cutoff).any():
        raise ValueError('Feature time leakage')
    return out.sort_values(['application_date','loan_id']).reset_index(drop=True)


def prepare_features(root=ROOT, **kwargs):
    root = paths(root)
    data = read_inputs(root)
    loans = attach_clicks(make_labels(data['lms_loan_daily']), data['feature_clickstream'])
    loans.to_pickle(root/'work/features.pkl')
    # A schema-only external artifact avoids exposing direct identifiers.
    dump(root/'evidence/feature_contract.json', dict(rows=len(loans), features=FEATURES,
        target=TARGET, policy=POLICY, click_missing=int(loans.click_missing.sum()),
        labels_known=int(loans[TARGET].notna().sum()), proxy_rate=float(loans[TARGET].mean()),
        feature_nulls=loans[FEATURES].isna().sum().astype(int).to_dict()))
    return 'work/features.pkl'


def split_development(d):
    train = d[d.application_date < '2023-03-01'].copy()
    valid = d[d.application_date.between('2023-09-01','2023-10-31')].copy()
    for x in [train, valid]:
        if x.empty or x[TARGET].isna().any() or (x.label_available_date > CUTOFF).any():
            raise ValueError('Empty/immature development set')
        if x[TARGET].nunique() != 2:
            raise ValueError('Development window must contain both classes')
    if set(train.Customer_ID) & set(valid.Customer_ID):
        raise ValueError('Borrower overlap')
    if train.label_available_date.max() >= valid.application_date.min():
        raise ValueError('Training labels not mature before validation origin')
    return train, valid


def metrics(y, p, threshold=0.5, minimum=30):
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    keep = pd.notna(y)
    y, p = y[keep].astype(int), p[keep]
    result = dict(n=int(len(y)), positives=int(y.sum()), proxy_rate=float(y.mean()) if len(y) else None,
                  status='ok', pr_auc=None, roc_auc=None, precision=None, recall=None,
                  f1=None, brier=None, tn=None, fp=None, fn=None, tp=None)
    if len(y) < minimum:
        result['status'] = 'insufficient_labels'
        return result
    pred = p >= threshold
    result.update(brier=float(brier_score_loss(y,p)), precision=float(precision_score(y,pred,zero_division=0)),
        recall=float(recall_score(y,pred,zero_division=0)), f1=float(f1_score(y,pred,zero_division=0)))
    result.update(zip(['tn','fp','fn','tp'], [int(x) for x in confusion_matrix(y,pred,labels=[0,1]).ravel()]))
    if len(np.unique(y)) < 2:
        result['status'] = 'one_class'
    else:
        result.update(pr_auc=float(average_precision_score(y,p)), roc_auc=float(roc_auc_score(y,p)))
    return result


def build_model(name):
    estimator = (LogisticRegression(C=1.0, max_iter=1500, random_state=611)
        if name == 'logistic' else HistGradientBoostingClassifier(max_iter=120,
        max_leaf_nodes=15, learning_rate=.06, l2_regularization=5, early_stopping=False, random_state=611))
    return Pipeline([('imputer',SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)),
                     ('scale',StandardScaler()), ('model',estimator)])


def train_models(root=ROOT, **kwargs):
    root = paths(root)
    train, valid = split_development(pd.read_pickle(root/'work/features.pkl'))
    rows = []
    # Natural prevalence preserves probability calibration. PR-AUC addresses
    # imbalance in selection; weights are deliberately not applied blindly.
    with threadpool_limits(limits=1):
        for name in ['logistic','hist_gradient_boosting']:
            model = build_model(name)
            model.fit(train[FEATURES], train[TARGET].astype(int))
            p = model.predict_proba(valid[FEATURES])[:,1]
            m = metrics(valid[TARGET],p)
            cohort_metrics = [metrics(g[TARGET],model.predict_proba(g[FEATURES])[:,1])
                              for _,g in valid.groupby('application_date')]
            m.update(name=name, monthly_pr_auc_min=min(v['pr_auc'] for v in cohort_metrics),
                     parameters=model.get_params()['model'].get_params())
            rows.append(m)
            joblib.dump(model,root/f'work/{name}.joblib')
    dump(root/'work/candidates.json', rows)
    return 'work/candidates.json'


def choose_champion(rows):
    # Challenger must improve AP materially without materially degrading
    # calibration or worst-month AP. Otherwise retain the simpler baseline.
    baseline = next(r for r in rows if r['name']=='logistic')
    challenger = next(r for r in rows if r['name']=='hist_gradient_boosting')
    promote = (challenger['pr_auc'] >= baseline['pr_auc']+.01 and
               challenger['brier'] <= baseline['brier']+.01 and
               challenger['monthly_pr_auc_min'] >= baseline['monthly_pr_auc_min']-.02)
    return challenger if promote else baseline


def register_model(root=ROOT, **kwargs):
    root = paths(root)
    rows = json.loads((root/'work/candidates.json').read_text())
    best = choose_champion(rows)
    lineage = json.loads((root/'evidence/input_contract.json').read_text())
    signature = dict(policy=POLICY, features=FEATURES, cutoff=str(CUTOFF.date()),
                     inputs={k:v['sha256'] for k,v in lineage.items() if isinstance(v,dict)},
                     selected=best['name'], sklearn=sklearn.__version__, parameters=best['parameters'],
                     source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    version = 'credit_' + hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:16]
    folder = root/'model_bank'/version
    folder.mkdir(exist_ok=True)
    model = joblib.load(root/f"work/{best['name']}.joblib")
    joblib.dump(model,folder/'pipeline.joblib')
    train, valid = split_development(pd.read_pickle(root/'work/features.pkl'))
    reference = train[FEATURES].copy()
    reference['score'] = model.predict_proba(reference)[:,1]
    reference.to_pickle(folder/'reference.pkl')
    metadata = dict(version=version, **signature, target=TARGET,
        actual_created_at=datetime.now(timezone.utc).isoformat(),
        simulated_available_from=str(AVAILABLE.date()),
        training_rows=len(train), validation_rows=len(valid),
        training_range=[str(train.application_date.min().date()), str(train.application_date.max().date())],
        validation_range=[str(valid.application_date.min().date()), str(valid.application_date.max().date())],
        max_training_label_available=str(train.label_available_date.max().date()),
        max_selection_label_available=str(valid.label_available_date.max().date()),
        threshold=.5, threshold_policy='fixed 0.5 demonstration; no economic cost optimisation',
        selection_policy='Promote HGB only if AP +0.01, Brier degradation <=0.01 and worst-month AP degradation <=0.02; otherwise Logistic.',
        candidates=rows,
        runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__),
        artifact_sha256=hashlib.sha256((folder/'pipeline.joblib').read_bytes()).hexdigest())
    # Preserve the original creation timestamp for deterministic reruns.
    if (folder/'metadata.json').exists():
        metadata['actual_created_at']=json.loads((folder/'metadata.json').read_text())['actual_created_at']
    dump(folder/'metadata.json',metadata)
    dump(root/'model_bank/registry.json',dict(version=version, path=f'model_bank/{version}', available_from=str(AVAILABLE.date())))
    dump(root/'evidence/model_comparison.json',metadata)
    return version


def load_champion(root, scoring_date):
    reg = json.loads((root/'model_bank/registry.json').read_text())
    if pd.Timestamp(reg['available_from']) > pd.Timestamp(scoring_date):
        raise ValueError('No historically available model for this scoring date')
    folder = root/reg['path']
    meta = json.loads((folder/'metadata.json').read_text())
    if pd.Timestamp(meta['max_selection_label_available']) > pd.Timestamp(meta['cutoff']):
        raise ValueError('Immature selection labels')
    if meta['features'] != FEATURES or meta['policy'] != POLICY:
        raise ValueError('Model schema/policy mismatch')
    if hashlib.sha256((folder/'pipeline.joblib').read_bytes()).hexdigest() != meta['artifact_sha256']:
        raise ValueError('Artifact checksum mismatch')
    return joblib.load(folder/'pipeline.joblib'),meta,folder


def historical_inference(root=ROOT, run_id='local', cohort=None, **kwargs):
    root = paths(root)
    d = pd.read_pickle(root/'work/features.pkl')
    d = d[d.application_date >= AVAILABLE].copy()
    if cohort:
        start = pd.Timestamp(cohort)
        if start.day != 1 or start < AVAILABLE or start not in set(d.application_date):
            raise ValueError('Backfill cohort must be an available month-start application date >= 2024-05-01')
        d = d[d.application_date == start]
    predictions = []
    with threadpool_limits(limits=1):
        for date,g in d.groupby('application_date'):
            model,meta,_ = load_champion(root,date)
            p = model.predict_proba(g[FEATURES])[:,1]
            out = pd.DataFrame(dict(loan_id=g.loan_id.values, application_cohort=str(date.date()),
                scoring_date=str(date.date()), probability=p, threshold=meta['threshold'],
                predicted_class=(p>=meta['threshold']).astype(int), model_version=meta['version'],
                pipeline_run_id=run_id, information_cutoff=meta['cutoff'], target=TARGET,
                feature_snapshot_date=g.feature_snapshot_date.dt.strftime('%Y-%m-%d').values,
                feature_policy=POLICY, historical_mode='simulated_point_in_time'))
            predictions.append(out)
    if not predictions:
        raise ValueError('No scoring cohorts')
    pd.concat(predictions,ignore_index=True).to_pickle(root/'work/predictions.pkl')
    return 'work/predictions.pkl'


def upsert(root, table, data, keys):
    if data.duplicated(keys).any():
        raise ValueError(f'Duplicate {table} keys')
    with sqlite3.connect(root/'datamart/gold.sqlite') as con:
        exists=con.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone()
        if exists:
            old=pd.read_sql_query(f'SELECT * FROM "{table}"',con)
            data=pd.concat([old,data],ignore_index=True).drop_duplicates(keys,keep='last')
        data=data.sort_values(keys).reset_index(drop=True)
        # Prepare staging, then swap and index it in one transaction.
        # DAG max_active_runs=1 also prevents concurrent lost updates.
        staging=f'_staging_{table}'
        data.to_sql(staging,con,if_exists='replace',index=False)
        columns=','.join(f'"{k}"' for k in keys)
        con.execute('BEGIN IMMEDIATE')
        con.execute(f'DROP TABLE IF EXISTS "{table}"')
        con.execute(f'ALTER TABLE "{staging}" RENAME TO "{table}"')
        con.execute(f'CREATE UNIQUE INDEX "uq_{table}" ON "{table}" ({columns})')
    temp=root/f'datamart/{table}.csv.tmp'
    data.to_csv(temp,index=False,float_format='%.12g')
    temp.replace(root/f'datamart/{table}.csv')
    return len(data)


def publish_predictions(root=ROOT, **kwargs):
    root=paths(root)
    return upsert(root,'gold_predictions',pd.read_pickle(root/'work/predictions.pkl'),['loan_id','model_version','scoring_date'])


def psi(reference, current, bins=10):
    """Training quantile bins with explicit missing bin and epsilon smoothing."""
    r,c=np.asarray(reference,dtype=float),np.asarray(current,dtype=float)
    finite=r[np.isfinite(r)]
    inner=np.unique(np.quantile(finite,np.linspace(0,1,bins+1)[1:-1])) if len(finite) else np.array([])
    edges=np.r_[-np.inf,inner,np.inf]
    def distribution(x):
        counts=np.r_[np.histogram(x[np.isfinite(x)],edges)[0],np.isnan(x).sum()].astype(float)+.5
        return counts/counts.sum()
    a,b=distribution(r),distribution(c)
    return float(np.sum((b-a)*np.log(b/a)))


def compute_monitoring(root=ROOT, **kwargs):
    root=paths(root)
    with sqlite3.connect(root/'datamart/gold.sqlite') as con:
        pred=pd.read_sql_query('SELECT * FROM gold_predictions',con)
    d=pd.read_pickle(root/'work/features.pkl')
    joined=pred.merge(d,on='loan_id',validate='many_to_one',suffixes=('','_feature'))
    immediate,drift,delayed=[],[],[]
    last_snapshot=pd.to_datetime(read_inputs(root)['lms_loan_daily'].snapshot_date).max()
    final_asof=last_snapshot+pd.Timedelta(days=1)
    snapshots=list(pd.date_range(AVAILABLE,final_asof,freq='M'))+[final_asof]
    for (cohort,version),g in joined.groupby(['application_cohort','model_version']):
        _,meta,folder=load_champion(root,pd.Timestamp(cohort))
        ref=pd.read_pickle(folder/'reference.pkl')
        key=dict(application_cohort=cohort,model_version=version)
        score_psi=psi(ref.score,g.probability)
        values=[]
        for feature in FEATURES:
            value=psi(ref[feature],g[feature]); values.append(value)
            drift.append(dict(**key,feature=feature,psi=value,missing_rate=float(g[feature].isna().mean()),
                              reference_missing_rate=float(ref[feature].isna().mean())))
        immediate.append(dict(**key,scoring_date=cohort,volume=len(g),mean_score=float(g.probability.mean()),
            score_p10=float(g.probability.quantile(.1)),score_p50=float(g.probability.median()),score_p90=float(g.probability.quantile(.9)),
            click_missing_rate=float(g.click_missing.mean()),input_missing_rate=float(g[FEATURES].isna().mean().mean()),
            score_psi=score_psi,max_feature_psi=max(values),
            alert='red' if max(score_psi,max(values))>=.25 else 'amber' if max(score_psi,max(values))>=.10 else 'green'))
        for asof in snapshots:
            if asof < pd.Timestamp(cohort):
                continue
            known=g[TARGET].notna() & (g.label_available_date<=asof)
            m=metrics(g.loc[known,TARGET],g.loc[known,'probability'],float(g.threshold.iloc[0]))
            if not known.any():
                m['status']='pending_maturity'
            delayed.append(dict(**key,monitoring_asof=str(asof.date()),volume=len(g),
                mature_count=int(known.sum()),immature_count=int((~known).sum()),
                **m))
    pd.DataFrame(immediate).to_pickle(root/'work/immediate.pkl')
    pd.DataFrame(drift).to_pickle(root/'work/drift.pkl')
    pd.DataFrame(delayed).to_pickle(root/'work/delayed.pkl')
    dump(root/'evidence/monitoring_policy.json',dict(final_asof=str(final_asof.date()),minimum_labels=30,
        psi_reference='training population; quantile bins; missing bin; 0.5 pseudocount',
        alert_thresholds='PSI >=0.10 amber; >=0.25 red. Proposed governance choices.'))
    return 'work/delayed.pkl'


def publish_monitoring(root=ROOT, **kwargs):
    root=paths(root)
    counts={}
    for stage,table,keys in [('immediate','gold_monitoring_immediate',['application_cohort','model_version']),
        ('drift','gold_feature_drift',['application_cohort','model_version','feature']),
        ('delayed','gold_monitoring_delayed',['application_cohort','model_version','monitoring_asof'])]:
        counts[table]=upsert(root,table,pd.read_pickle(root/f'work/{stage}.pkl'),keys)
    draw_charts(root)
    dump(root/'evidence/monitoring_counts.json',counts)
    return counts


def draw_charts(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with sqlite3.connect(root/'datamart/gold.sqlite') as con:
        immediate=pd.read_sql_query('SELECT * FROM gold_monitoring_immediate ORDER BY application_cohort',con)
        delayed=pd.read_sql_query('SELECT * FROM gold_monitoring_delayed ORDER BY application_cohort, monitoring_asof',con)
        drift=pd.read_sql_query('SELECT * FROM gold_feature_drift',con)
    latest=delayed.groupby(['application_cohort','model_version']).tail(1)
    plt.style.use('seaborn-v0_8-whitegrid')
    x=pd.to_datetime(immediate.application_cohort)
    fig,axes=plt.subplots(3,1,figsize=(12,10),sharex=True)
    axes[0].bar(x,immediate.volume,width=18,color='#2563eb',label='Scored loans')
    axes[0].set_ylabel('Loans');axes[0].legend()
    axes[1].plot(x,immediate.mean_score,'o-',label='Mean predicted proxy risk')
    axes[1].plot(pd.to_datetime(latest.application_cohort),latest.proxy_rate,'s--',label='Mature observed proxy rate')
    axes[1].set_ylabel('Probability / rate');axes[1].legend()
    axes[2].plot(x,immediate.score_psi,'o-',label='Score PSI')
    axes[2].plot(x,immediate.max_feature_psi,'s-',label='Largest input PSI')
    axes[2].axhline(.10,color='#d97706',linestyle='--',label='Proposed amber .10')
    axes[2].axhline(.25,color='#dc2626',linestyle='--',label='Proposed red .25')
    axes[2].set_ylabel('PSI vs training');axes[2].legend(ncol=2)
    fig.suptitle('Monthly historical scoring and population stability',fontsize=16)
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(root/'datamart/charts/stability.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    x=pd.to_datetime(latest.application_cohort)
    for col,label in [('pr_auc','PR-AUC (average precision)'),('roc_auc','ROC-AUC')]:
        axes[0].plot(x,latest[col],'o-',label=label)
    axes[0].plot(x,latest.proxy_rate,'--',label='Prevalence / random AP reference')
    axes[0].set_ylabel('Discrimination');axes[0].set_ylim(0,1);axes[0].legend()
    for col in ['precision','recall','brier']:
        axes[1].plot(x,latest[col],'o-',label=col)
    axes[1].set_ylabel('Metric at fixed threshold 0.5');axes[1].set_ylim(0,1);axes[1].legend()
    fig.suptitle('Delayed mature-cohort severe-arrears proxy performance',fontsize=16)
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(root/'datamart/charts/performance.png',dpi=150);plt.close(fig)
    timeline=delayed.groupby('monitoring_asof')[['mature_count','immature_count']].sum()
    fig,ax=plt.subplots(figsize=(12,5))
    ax.stackplot(pd.to_datetime(timeline.index),timeline.mature_count,timeline.immature_count,
        labels=['Mature outcomes','Pending six-month horizon + ingestion lag'],colors=['#16a34a','#cbd5e1'])
    ax.set_title('Outcome availability in historical monitoring snapshots');ax.set_ylabel('Scored loans');ax.legend(loc='upper left')
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(root/'datamart/charts/maturity.png',dpi=150);plt.close(fig)
    matrix=drift.pivot(index='feature',columns='application_cohort',values='psi').reindex(FEATURES)
    fig,ax=plt.subplots(figsize=(12,8));im=ax.imshow(matrix.values,aspect='auto',cmap='YlOrRd',vmin=0,vmax=max(.25,float(matrix.max().max())))
    ax.set_xticks(range(len(matrix.columns)),[s[:7] for s in matrix.columns],rotation=45,ha='right')
    ax.set_yticks(range(len(matrix.index)),matrix.index);ax.set_title('Input drift vs training reference (PSI)')
    fig.colorbar(im,ax=ax,label='PSI');fig.tight_layout();fig.savefig(root/'datamart/charts/feature_drift.png',dpi=150);plt.close(fig)


def validate_outputs(root=ROOT, **kwargs):
    root=paths(root)
    with sqlite3.connect(root/'datamart/gold.sqlite') as con:
        pred=pd.read_sql_query('SELECT * FROM gold_predictions',con)
        delayed=pd.read_sql_query('SELECT * FROM gold_monitoring_delayed',con)
        counts={table:con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
            ['gold_predictions','gold_monitoring_immediate','gold_monitoring_delayed','gold_feature_drift']}
    assert len(pred)>0 and not pred.duplicated(['loan_id','model_version','scoring_date']).any()
    assert pred.probability.between(0,1).all() and pred.probability.notna().all()
    assert (pd.to_datetime(pred.information_cutoff)<pd.to_datetime(pred.scoring_date)).all()
    assert delayed.loc[delayed.status=='pending_maturity',['pr_auc','roc_auc','brier']].isna().all().all()
    model,meta,_=load_champion(root,AVAILABLE)
    d=pd.read_pickle(root/'work/features.pkl')
    held=d[d.application_date.between('2024-05-01','2024-07-31')]
    with threadpool_limits(limits=1):
        test_metrics=metrics(held[TARGET],model.predict_proba(held[FEATURES])[:,1])
    for name in ['stability','performance','maturity','feature_drift']:
        assert (root/f'datamart/charts/{name}.png').stat().st_size>5000
    report=dict(status='PASS_DIRECT_PYTHON',counts=counts,heldout_metrics=test_metrics,
        model_version=meta['version'], champion=meta['selected'],
        note='Direct output validation is not evidence of Docker or Airflow integration acceptance.')
    dump(root/'evidence/output_validation.json',report)
    print(json.dumps(report,indent=2))
    return report


STAGES=[validate_inputs,prepare_features,train_models,register_model,historical_inference,
        publish_predictions,compute_monitoring,publish_monitoring,validate_outputs]


def run(root=ROOT,run_id='local',cohort=None):
    with threadpool_limits(limits=1):
        for stage in STAGES:
            print(f'RUN {stage.__name__}',flush=True)
            stage(root=Path(root),run_id=run_id,cohort=cohort)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--run-id',default='local')
    parser.add_argument('--cohort')
    parser.add_argument('--stage',choices=[f.__name__ for f in STAGES])
    args=parser.parse_args()
    if args.stage:
        globals()[args.stage](root=args.root,run_id=args.run_id,cohort=args.cohort)
    else:
        run(args.root,args.run_id,args.cohort)
