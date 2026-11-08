"""Reconstruct original assignment CSVs from checked-in gzip parts, verifying SHA256."""
from pathlib import Path
import gzip,hashlib,json

def bootstrap(root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    data=root/'data'
    expected=json.loads((data/'SHA256.json').read_text())
    for name,digest in expected.items():
        dest=data/name
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:
                raise ValueError(f'Existing input checksum mismatch: {name}')
            continue
        parts=sorted((data/'parts').glob(name+'.gz.part*'))
        if not parts:
            raise FileNotFoundError(f'Missing input parts: {name}')
        content=gzip.decompress(b''.join(p.read_bytes() for p in parts))
        if hashlib.sha256(content).hexdigest()!=digest:
            raise ValueError(f'Reconstructed input checksum mismatch: {name}')
        temp=dest.with_suffix('.csv.tmp');temp.write_bytes(content);temp.replace(dest)
    print('All four original assignment CSV checksums verified.')

if __name__=='__main__':
    bootstrap()
