from pathlib import Path
import json
import sqlite3
import shutil
import ast

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from src import pipeline as p


@pytest.fixture(scope='session')
def raw():
    return p.read_inputs(p.ROOT)


@pytest.fixture(scope='session')
def features(raw):
    return p.attach_clicks(p.make_labels(raw['lms_loan_daily']),raw['feature_clickstream'])


def test_original_hashes_and_schemas(raw):
    p.validate_frames(raw)
    import hashlib
    for name,path in p.input_paths(p.ROOT).items():
        original=p.ROOT/'inputs'/path.name
        if original.exists():
            assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest()
    assert len(raw['lms_loan_daily'])==137500


def test_duplicate_contract_rejected(raw):
    broken=dict(raw)
    broken['feature_clickstream']=pd.concat([raw['feature_clickstream'],raw['feature_clickstream'].iloc[:1]])
    with pytest.raises(ValueError,match='duplicate'):
        p.validate_frames(broken)


def test_malformed_numeric_cleaning():
    x=p.numeric(pd.Series(['52312.68_','_','1_2','-100','inf',None,' 42 ']),lower=0,upper=1e7)
    assert x.iloc[0]==52312.68 and x.iloc[-1]==42
    assert x.iloc[1:6].isna().all()


def test_labels_independent_of_late_snapshots(raw):
    lms=raw['lms_loan_daily'].copy()
    before=p.make_labels(lms).set_index('loan_id')[p.TARGET]
    lms.loc[lms.installment_num>6,'overdue_amt']=999999
    after=p.make_labels(lms).set_index('loan_id')[p.TARGET]
    pd.testing.assert_series_equal(before,after)


def test_label_threshold_maturity_and_incomplete_window(raw):
    sample=raw['lms_loan_daily'].iloc[:11].copy()
    sample['overdue_amt']=0
    sample.loc[sample.installment_num==4,'overdue_amt']=3000
    assert p.make_labels(sample)[p.TARGET].iloc[0]==1
    assert p.make_labels(sample).label_available_date.iloc[0]==pd.Timestamp('2023-11-02')
    sample.loc[sample.installment_num==4,'overdue_amt']=2999
    assert p.make_labels(sample)[p.TARGET].iloc[0]==0
    assert p.make_labels(sample[sample.installment_num!=5])[p.TARGET].isna().all()


def test_join_and_feature_cutoff(features):
    assert len(features)==12500 and features.loan_id.is_unique
    known=features.feature_snapshot_date.notna()
    assert (features.loc[known,'feature_snapshot_date']<=features.loc[known,'feature_cutoff']).all()
    assert features.loc[~known,p.FEATURES[:-1]].isna().all().all()
    assert features.loc[features.application_date=='2023-01-01','click_missing'].eq(1).all()
    assert not set(p.FEATURES)&{'Customer_ID','loan_id','SSN','Name','overdue_amt','balance',p.TARGET}


def test_future_click_perturbation_has_no_effect(raw):
    loans=p.make_labels(raw['lms_loan_daily'])
    loans=loans[loans.application_date=='2024-07-01']
    before=p.attach_clicks(loans,raw['feature_clickstream'])
    c=raw['feature_clickstream'].copy()
    c.loc[c.snapshot_date>='2024-07-01',p.FEATURES[:-1]]=99999
    after=p.attach_clicks(loans,c)
    pd.testing.assert_frame_equal(before,after)


def test_no_same_day_fallback(raw):
    loans=p.make_labels(raw['lms_loan_daily']).iloc[:1]
    c=raw['feature_clickstream'].iloc[:1].copy()
    c['Customer_ID']=loans.Customer_ID.iloc[0]
    c['snapshot_date']=str(loans.application_date.iloc[0].date())
    assert p.attach_clicks(loans,c).click_missing.iloc[0]==1


def test_temporal_isolation_and_label_availability(features):
    train,valid=p.split_development(features)
    assert train.label_available_date.max()<valid.application_date.min()
    assert valid.label_available_date.max()<=p.CUTOFF<p.AVAILABLE
    test=features[features.application_date>=p.AVAILABLE]
    assert set(test.Customer_ID).isdisjoint(set(train.Customer_ID)|set(valid.Customer_ID))


def test_immature_training_rejected(features):
    d=features.copy()
    d.loc[d.application_date<'2023-03-01','label_available_date']=p.CUTOFF+pd.Timedelta(days=1)
    with pytest.raises(ValueError,match='immature'):
        p.split_development(d)


def test_preprocessing_fits_only_train_and_serializes(features,tmp_path):
    train,_=p.split_development(features)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        model=p.build_model('logistic').fit(train[p.FEATURES],train[p.TARGET])
    np.testing.assert_allclose(model['imputer'].statistics_,train[p.FEATURES].median().to_numpy())
    artifact=tmp_path/'model.joblib';joblib.dump(model,artifact)
    np.testing.assert_array_equal(model.predict_proba(train[p.FEATURES]),joblib.load(artifact).predict_proba(train[p.FEATURES]))


def test_metric_correctness():
    y=np.array([0,1,0,1]*20);score=np.array([.1,.8,.6,.3]*20)
    m=p.metrics(y,score)
    assert m['pr_auc']==pytest.approx(average_precision_score(y,score))
    assert m['roc_auc']==pytest.approx(roc_auc_score(y,score))
    assert m['brier']==pytest.approx(brier_score_loss(y,score))
    assert (m['tn'],m['fp'],m['fn'],m['tp'])==(20,20,20,20)


def test_one_class_and_insufficient_labels():
    assert p.metrics([],[])['status']=='insufficient_labels'
    assert p.metrics([1]*10,[.2]*10)['pr_auc'] is None
    m=p.metrics([0]*40,[.1]*40)
    assert m['status']=='one_class' and m['roc_auc'] is None and m['pr_auc'] is None
    assert m['brier']==pytest.approx(.01)


def test_psi_identical_shifted_missing_and_constant():
    x=np.arange(100,dtype=float)
    assert p.psi(x,x)==pytest.approx(0)
    assert p.psi(x,x+500)>p.psi(x,x)
    assert p.psi(x,np.full(100,np.nan))>0
    assert np.isfinite(p.psi(np.zeros(100),np.zeros(20)))


def test_promotion_policy():
    b=dict(name='logistic',pr_auc=.3,brier=.17,monthly_pr_auc_min=.25)
    c=dict(name='hist_gradient_boosting',pr_auc=.32,brier=.18,monthly_pr_auc_min=.24)
    assert p.choose_champion([b,c])==c
    c['brier']=.20
    assert p.choose_champion([b,c])==b


def test_upsert_idempotency_and_unique_index(tmp_path):
    p.paths(tmp_path)
    d=pd.DataFrame({'key':['a','b'],'value':[1,2]})
    assert p.upsert(tmp_path,'test_gold',d,['key'])==2
    assert p.upsert(tmp_path,'test_gold',d,['key'])==2
    assert p.upsert(tmp_path,'test_gold',pd.DataFrame({'key':['b'],'value':[3]}),['key'])==2
    with sqlite3.connect(tmp_path/'datamart/gold.sqlite') as con:
        assert con.execute('SELECT value FROM test_gold WHERE key=?',('b',)).fetchone()[0]==3
        with pytest.raises(sqlite3.IntegrityError):
            con.execute('INSERT INTO test_gold VALUES (?,?)',('a',9))


def test_portable_source_and_dag_structure():
    source=(p.ROOT/'src/pipeline.py').read_text()
    assert 'C:\\Users' not in source and 'C:/Users' not in source
    tree=ast.parse((p.ROOT/'dags/cs611_task1.py').read_text())
    assert tree and len(p.STAGES)==9
    assert len({s.__name__ for s in p.STAGES})==9


@pytest.mark.integration
def test_generated_outputs_and_pending_outcomes():
    if not (p.ROOT/'datamart/gold.sqlite').exists():
        pytest.skip('Run pipeline first')
    with sqlite3.connect(p.ROOT/'datamart/gold.sqlite') as con:
        pred=pd.read_sql_query('SELECT * FROM gold_predictions',con)
        delay=pd.read_sql_query('SELECT * FROM gold_monitoring_delayed',con)
    assert pred.application_cohort.nunique()==9
    assert pred.model_version.nunique()==1
    assert not pred.duplicated(['loan_id','model_version','scoring_date']).any()
    assert (delay.status=='pending_maturity').any()
    assert delay.loc[delay.status=='pending_maturity',['pr_auc','roc_auc','brier','proxy_rate']].isna().all().all()
    assert (delay.mature_count+delay.immature_count==delay.volume).all()
    model,meta,_=p.load_champion(p.ROOT,p.AVAILABLE)
    assert meta['training_rows']==1031
    with pytest.raises(ValueError,match='historically'):
        p.load_champion(p.ROOT,'2024-04-01')


@pytest.mark.integration
def test_historical_backfill_probability_identity(tmp_path):
    if not (p.ROOT/'model_bank/registry.json').exists():
        pytest.skip('Run pipeline first')
    p.paths(tmp_path)
    shutil.copytree(p.ROOT/'model_bank',tmp_path/'model_bank',dirs_exist_ok=True)
    shutil.copy2(p.ROOT/'work/features.pkl',tmp_path/'work/features.pkl')
    p.historical_inference(root=tmp_path,run_id='backfill-test',cohort='2024-09-01')
    actual=pd.read_pickle(tmp_path/'work/predictions.pkl').sort_values('loan_id')
    with sqlite3.connect(p.ROOT/'datamart/gold.sqlite') as con:
        expected=pd.read_sql_query("SELECT * FROM gold_predictions WHERE application_cohort='2024-09-01'",con).sort_values('loan_id')
    assert actual.loan_id.to_list()==expected.loan_id.to_list()
    np.testing.assert_allclose(actual.probability,expected.probability,atol=0,rtol=0)
    p.publish_predictions(root=tmp_path)
    p.publish_predictions(root=tmp_path)
    with sqlite3.connect(tmp_path/'datamart/gold.sqlite') as con:
        assert con.execute('SELECT COUNT(*) FROM gold_predictions').fetchone()[0]==len(actual)
    with pytest.raises(ValueError,match='Backfill'):
        p.historical_inference(root=tmp_path,cohort='2024-04-01')
