"""Create a candidate ZIP; enforce true validated label only after all gates."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from release_identity import identity


def build(root,repo_url=None):
    root=Path(root).resolve()
    if repo_url:
        if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?',repo_url):
            raise ValueError('Expected a real supplied HTTPS GitHub repository URL')
        (root/'Readme.txt').write_text(repo_url.rstrip('/')+'\n',encoding='utf8')
    elif not (root/'Readme.txt').exists():
        (root/'Readme.txt').write_text('',encoding='utf8')
    readme=(root/'Readme.txt').read_text().splitlines()
    github_ok=len(readme)==1 and bool(re.fullmatch(r'https://github\.com/[^/]+/[^/]+/?',readme[0]))
    docker_path=root/'evidence/docker_acceptance.json'
    acceptance=json.loads(docker_path.read_text()) if docker_path.exists() else {}
    docker_ok=acceptance.get('status')=='PASS' and acceptance.get('release_identity')==identity(root)
    status=dict(status='VALIDATED' if github_ok and docker_ok else 'CANDIDATE_NOT_SUBMISSION_READY',
        github_readme='PASS' if github_ok else 'BLOCKED: real repository URL not supplied',
        docker_airflow='PASS' if docker_ok else 'BLOCKED: clean-extraction Docker/Airflow acceptance not passed',
        direct_python_evidence='evidence/output_validation.json',test_evidence='evidence/pytest.xml')
    (root/'evidence/acceptance_status.json').write_text(json.dumps(status,indent=2))
    folders=['src','dags','scripts','tests','docs','data','datamart','model_bank','evidence','.github']
    top=['Dockerfile','docker-compose.yaml','requirements.txt','README.md','Readme.txt','pytest.ini','.dockerignore','.gitignore','.gitattributes']
    files=[root/f for f in top]
    for folder in folders:
        files.extend(p for p in (root/folder).rglob('*') if p.is_file() and
            '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.tmp')) and p.name!='artifact_manifest.json')
    files=sorted(set(files))
    manifest={str(p.relative_to(root)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    manifest_path=root/'evidence/artifact_manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    files.append(manifest_path)
    dest=root/'dist';dest.mkdir(exist_ok=True)
    archive=dest/('CS611_Task1_VALIDATED.zip' if status['status']=='VALIDATED' else 'CS611_Task1_CANDIDATE.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:
            z.write(path,path.relative_to(root).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    print(json.dumps(dict(zip=str(archive),sha256=digest,files=len(files),**status),indent=2))
    return archive


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo-url');ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=ap.parse_args();build(args.root,args.repo_url)
