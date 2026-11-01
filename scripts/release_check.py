"""Verify a candidate, package its evidence, then verify the exact final ZIP."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, time, zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.package import build


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--final-only',action='store_true',help='Repackage and verify once after candidate acceptance passed')
    args=parser.parse_args()
    last=None
    for phase in (['final_archive_integration'] if args.final_only else ['candidate_integration','final_archive_integration']):
        archive=build(ROOT)
        extract=ROOT/'acceptance_extract'/f'{phase}_{time.time_ns()}'
        extract.mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            z.extractall(extract)
        manifest=json.loads((extract/'evidence/artifact_manifest.json').read_text())
        for rel,m in manifest.items():
            assert hashlib.sha256((extract/rel).read_bytes()).hexdigest()==m['sha256'],rel
        print(f'{phase}: extracted {archive.name} to {extract}',flush=True)
        out=ROOT/f'evidence/{phase}.log'
        with out.open('w',encoding='utf8') as handle:
            result=subprocess.run([sys.executable,'-X','utf8',str(extract/'scripts/docker_acceptance.py'),'--root',str(extract)],
                cwd=extract,stdout=handle,stderr=subprocess.STDOUT)
        report=json.loads((extract/'evidence/docker_acceptance.json').read_text())
        shutil.copy2(extract/'evidence/docker_acceptance.json',ROOT/'evidence/docker_acceptance.json')
        if result.returncode or report['status']!='PASS':
            raise RuntimeError(f'{phase} failed; see {out} and {extract}/evidence')
        for name in ['docker_build.log','docker_up.log','docker_info.txt','compose_version.txt','container_outputs.json','cli_backfill.log']:
            source=extract/'evidence'/name
            if source.exists():shutil.copy2(source,ROOT/'evidence'/name)
        last=dict(status='PASS',phase=phase,zip=str(archive),
            zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            extraction=str(extract),gates=report['gates'],
            evidence=str(extract/'evidence/docker_acceptance.json'))
        print(f'{phase}: all Docker/Airflow gates PASS',flush=True)
    (ROOT/'evidence/final_archive_acceptance.json').write_text(json.dumps(last,indent=2))
    print(json.dumps(last,indent=2),flush=True)


if __name__=='__main__':main()
