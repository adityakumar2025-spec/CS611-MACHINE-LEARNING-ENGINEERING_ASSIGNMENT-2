"""Run ONLY in a fresh extraction. Records failed gates as faithfully as passes."""
import argparse, base64, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=ap.parse_args();root=args.root.resolve()
    evidence=root/'evidence';evidence.mkdir(exist_ok=True)
    report={'status':'NOT_PASSED','root':str(root),'gates':{},'note':'Only actual command/API results establish success.'}
    def save():
        (evidence/'docker_acceptance.json').write_text(json.dumps(report,indent=2))
    def command(argv,log):
        result=subprocess.run(argv,cwd=root,text=True,encoding='utf8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (evidence/log).write_text(result.stdout,encoding='utf8')
        if result.returncode:
            raise RuntimeError(f'{argv}: exit {result.returncode}; see {log}')
        return result.stdout
    # Do not silently substitute a different command for the lecturer's path.
    if not shutil.which('docker-compose'):
        report['gates']['docker-compose build']='BLOCKED: docker-compose executable missing'
        report['gates']['docker-compose up']='BLOCKED: docker-compose executable missing'
        report['gates']['Airflow UI and DAG']='NOT_EXECUTED'
        save();print(json.dumps(report,indent=2));return 77
    up=None
    try:
        command(['docker','info'],'docker_info.txt')
        command(['docker-compose','version'],'compose_version.txt')
        command(['docker-compose','config'],'compose_resolved.yaml')
        command(['docker-compose','build'],'docker_build.log')
        report['gates']['docker-compose build']='PASS';save()
        out=(evidence/'docker_up.log').open('w',encoding='utf8')
        up=subprocess.Popen(['docker-compose','up'],cwd=root,stdout=out,stderr=subprocess.STDOUT)
        auth='Basic '+base64.b64encode(b'lecturer:lecturer').decode()
        def api(path,body=None,method=None):
            headers={'Authorization':auth,'Content-Type':'application/json'}
            req=Request('http://localhost:18080'+path,headers=headers,
                data=json.dumps(body).encode() if body is not None else None,method=method)
            with urlopen(req,timeout=20) as response:
                return json.load(response)
        deadline=time.time()+600
        while time.time()<deadline:
            try:
                if up.poll() is not None:
                    raise RuntimeError('This docker-compose up process exited')
                # Probe this exact Compose service before trusting an HTTP port.
                probe=subprocess.run(['docker-compose','exec','-T','airflow','true'],cwd=root,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if probe.returncode:
                    raise RuntimeError('This Compose airflow service is not running')
                health=api('/health')
                if health['scheduler']['status']=='healthy' and health['metadatabase']['status']=='healthy':
                    with urlopen('http://localhost:18080/login/',timeout=20) as response:
                        assert response.status==200
                    report['health']=health;break
            except Exception:
                if up.poll() is not None:
                    raise RuntimeError('docker-compose up exited before UI became ready')
            time.sleep(5)
        else:
            raise TimeoutError('UI/scheduler not healthy within 10 minutes')
        report['gates']['docker-compose up']='PASS'
        report['gates']['Airflow UI']='PASS: HTTP 200 login and healthy database/scheduler'
        save()
        # DAG parsing can lag webserver readiness.
        for _ in range(60):
            try:
                api('/api/v1/dags/cs611_task1');break
            except Exception:
                time.sleep(5)
        api('/api/v1/dags/cs611_task1',{'is_paused':False},method='PATCH')
        def trigger(name,conf):
            rid=f'acceptance_{name}_{int(time.time())}'
            api('/api/v1/dags/cs611_task1/dagRuns',{'dag_run_id':rid,'conf':conf})
            until=time.time()+1200
            while time.time()<until:
                run=api(f'/api/v1/dags/cs611_task1/dagRuns/{rid}')
                if run['state'] in ['success','failed']:
                    tasks=api(f'/api/v1/dags/cs611_task1/dagRuns/{rid}/taskInstances')
                    report[name]={'run':run,'tasks':tasks};save()
                    if run['state']!='success' or len(tasks['task_instances'])!=9 or any(t['state']!='success' for t in tasks['task_instances']):
                        raise RuntimeError(f'DAG {name} failed or not all 9 tasks succeeded')
                    return
                time.sleep(5)
            raise TimeoutError(f'DAG {name} timed out')
        def fingerprint():
            code="import sqlite3,json,hashlib; c=sqlite3.connect('/opt/project/datamart/gold.sqlite'); r=c.execute('SELECT loan_id,model_version,scoring_date,probability FROM gold_predictions ORDER BY loan_id,model_version,scoring_date').fetchall(); print(json.dumps({'rows':len(r),'sha256':hashlib.sha256(json.dumps(r).encode()).hexdigest()}))"
            return command(['docker-compose','exec','-T','airflow','python','-c',code],'last_fingerprint.txt').strip()
        trigger('full_replay',{})
        initial=fingerprint()
        trigger('repeat_replay',{})
        assert fingerprint()==initial,'Repeat prediction content differs'
        trigger('historical_backfill',{'cohort':'2024-09-01'})
        assert fingerprint()==initial,'Backfill changed prediction content/row count'
        command(['docker-compose','exec','-T','airflow','airflow','dags','backfill',
                 'cs611_task1','-s','2024-09-01','-e','2024-09-01'],'cli_backfill.log')
        assert fingerprint()==initial,'CLI backfill changed prediction content/row count'
        report['gates']['DAG, repeat, cohort backfill and Airflow CLI backfill']='PASS'
        report['prediction_fingerprint']=initial
        command(['docker-compose','exec','-T','airflow','python','-m','src.pipeline','--stage','validate_outputs'],'container_outputs.json')
        for folder in ['datamart','model_bank','evidence']:
            dest=root/f'generated-{folder}'
            command(['docker-compose','cp',f'airflow:/opt/project/{folder}',str(dest)],f'export_{folder}.log')
        report['gates']['Runtime model/gold/charts generated and exported']='PASS'
        report['status']='PASS';save()
        print(json.dumps(report,indent=2));return 0
    except Exception as exc:
        report['error']=repr(exc);save();print(json.dumps(report,indent=2));return 1
    finally:
        if up:
            subprocess.run(['docker-compose','down'],cwd=root)
            try:up.wait(timeout=30)
            except subprocess.TimeoutExpired:up.terminate()


if __name__=='__main__':
    sys.exit(main())
