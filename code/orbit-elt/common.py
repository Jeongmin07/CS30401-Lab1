"""Frozen experiment conditions and source/runtime receipts; stdlib only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
NS3 = Path('/home/ubuntu/ns-3.48')
STATE = Path('/home/ubuntu/lab/data/seoul_london/state')
BASE = '99bc6f733274475b7a6e804128651e17ee2a2536'
IMAGE = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
spec = importlib.util.spec_from_file_location('elt_frozen_deps', HERE/'deps/common.py')
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)

CASES = {}
for segments in (20, 21, 24):
    for variant in ('stock', 'selective', 'tail', 'eltA', 'eltC'):
        CASES[f'micro{segments}-{variant}'] = dict(kind='micro', duration=4,
            variant=variant, bytes=segments*1380, mode='base' if variant=='stock' else 'selective',
            tail=variant=='tail', elt_mode={'eltA':1,'eltC':2}.get(variant,0))
for variant in ('stock', 'tail', 'eltA', 'eltC'):
    CASES[f'leo200-{variant}'] = dict(kind='leo', duration=200, rate=10, queue=100,
        variant=variant, mode='base' if variant=='stock' else 'selective',
        tail=variant=='tail', elt_mode={'eltA':1,'eltC':2}.get(variant,0))

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def write(p, data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',newline='\n')

def git(*args,cwd=NS3):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}',
        '-c','core.autocrlf=false',*args],cwd=cwd)

def runtime(): return deps.runtime()

def source_files():
    paths=[HERE/n for n in ('common.py','run.py','implement.py','ns3.patch')]
    paths += [p for p in (HERE/'deps').rglob('*') if p.is_file() and p.suffix in ('.py','.csv','.json','.patch')]
    return {str(p.relative_to(HERE)):sha(p) for p in sorted(paths) if p.exists()}

def ready_check(path):
    for name in ('cc1plus','ninja','cmake','make'):
        assert subprocess.run(['pgrep','-x',name],stdout=subprocess.DEVNULL).returncode != 0, 'Build still active'
    ready=json.loads(Path(path).read_text());diff=git('diff','--binary','HEAD')
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert diff==(HERE/'ns3.patch').read_bytes()
    assert ready['build_status']=='success' and ready['patch_sha256']==sha(HERE/'ns3.patch')
    assert ready['official_export_byte_equal'] and ready['source_files_unchanged']
    assert runtime()==ready['runtime_files'] and source_files()==ready['source_files']
    return ready,diff
