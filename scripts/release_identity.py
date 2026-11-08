"""Content identity independent of Git metadata and generated runtime files."""
import hashlib,json
from pathlib import Path

def identity(root):
    root=Path(root)
    files=[]
    for name in ['src','dags','scripts','tests','data','.github','docs']:
        files.extend(p for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.csv'])
    files.extend(root/name for name in ['Dockerfile','docker-compose.yaml','requirements.txt','README.md','Readme.txt','pytest.ini','.dockerignore','.gitignore','.gitattributes'])
    hashes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.exists()}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
