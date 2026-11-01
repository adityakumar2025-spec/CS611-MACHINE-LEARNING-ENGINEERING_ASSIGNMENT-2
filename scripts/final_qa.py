"""Direct replay, deterministic repeat, backfill, tests and candidate extraction."""
from pathlib import Path
import hashlib, json, os, shutil, sqlite3, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src import pipeline as p
from scripts.package import build


def fingerprint(root):
    with sqlite3.connect(root/'datamart/gold.sqlite') as con:
        tables={table:con.execute(f'SELECT * FROM {table} ORDER BY 1,2,3').fetchall() for table in
            ['gold_predictions','gold_monitoring_immediate','gold_monitoring_delayed','gold_feature_drift']}
        # Run identifiers are expected to update; all score content must match.
        tables['gold_predictions']=con.execute('SELECT loan_id,application_cohort,scoring_date,probability,threshold,predicted_class,model_version FROM gold_predictions ORDER BY loan_id').fetchall()
    return {table:dict(rows=len(rows),sha256=hashlib.sha256(json.dumps(rows).encode()).hexdigest()) for table,rows in tables.items()}


def main():
    os.environ['LOKY_MAX_CPU_COUNT']='2'
    # Archive earlier generated experiments instead of mixing model versions.
    if (ROOT/'datamart/gold.sqlite').exists():
        stamp=ROOT/'milestones'/('pre_final_'+str(__import__('time').time_ns()))
        stamp.mkdir(parents=True)
        for folder in ['datamart','model_bank']:
            shutil.move(str(ROOT/folder),str(stamp/folder))
    log=ROOT/'evidence/direct_execution.log'
    with log.open('w',encoding='utf8') as output:
        for rid,cohort in [('full-replay-1',None),('repeat-replay-2',None),('historical-backfill-3','2024-09-01')]:
            argv=[sys.executable,'-X','utf8','-m','src.pipeline','--run-id',rid]
            if cohort:argv+=['--cohort',cohort]
            print('Executing',rid,flush=True)
            subprocess.run(argv,cwd=ROOT,check=True,stdout=output,stderr=subprocess.STDOUT,env=os.environ)
            current=fingerprint(ROOT)
            if rid=='full-replay-1':first=current
            else:assert current==first,(rid,current,first)
    (ROOT/'evidence/repeat_backfill.json').write_text(json.dumps(dict(status='PASS',runs=3,fingerprints=first),indent=2))
    test=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml=evidence/pytest.xml'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
    (ROOT/'evidence/test_results.txt').write_text(test.stdout,encoding='utf8')
    print(test.stdout,flush=True)
    if test.returncode:raise RuntimeError('Automated tests failed')
    archive=build(ROOT)
    extract=ROOT/'acceptance_extract'/('run_'+str(__import__('time').time_ns()))
    extract.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:z.extractall(extract)
    # Integrity check and actual lecturer commands attempted from extracted ZIP.
    manifest=json.loads((extract/'evidence/artifact_manifest.json').read_text())
    for rel,meta in manifest.items():
        assert hashlib.sha256((extract/rel).read_bytes()).hexdigest()==meta['sha256']
    accept=subprocess.run([sys.executable,str(extract/'scripts/docker_acceptance.py'),'--root',str(extract)],cwd=extract,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
    (ROOT/'evidence/clean_extraction_acceptance.txt').write_text(accept.stdout,encoding='utf8')
    shutil.copy2(extract/'evidence/docker_acceptance.json',ROOT/'evidence/docker_acceptance.json')
    # Prove the extracted project works without the developer checkout imports.
    env=dict(os.environ);env['PROJECT_ROOT']=str(extract);env['PYTHONPATH']=str(extract)
    # The extracted ZIP carries sample artifacts. Move them aside to force fresh generation.
    for folder in ['datamart','model_bank']:
        shutil.move(str(extract/folder),str(extract/f'packaged_{folder}'))
    with (ROOT/'evidence/clean_extraction_python.log').open('w',encoding='utf8') as out:
        subprocess.run([sys.executable,'-X','utf8','-m','src.pipeline','--run-id','fresh-extraction'],cwd=extract,env=env,check=True,stdout=out,stderr=subprocess.STDOUT)
    assert fingerprint(extract)==first,'Fresh extraction differs from source checkout'
    (ROOT/'evidence/clean_extraction_python.json').write_text(json.dumps(dict(status='PASS',source_zip=str(archive),
        extracted_path=str(extract),generated_from_empty_outputs=True,fingerprints=first,
        runtime='project .venv reused; application source and datasets came exclusively from ZIP'),indent=2))
    # Evidence is now complete for this attempt; publish an updated candidate ZIP.
    build(ROOT)
    print('Direct tests/repeat/backfill/extraction PASS. Docker acceptance exit:',accept.returncode,flush=True)


if __name__=='__main__':main()
