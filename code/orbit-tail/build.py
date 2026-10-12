"""Synchronous single-job build and exact runtime readiness receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

here=Path(__file__).resolve().parent
root=Path('/home/ubuntu/ns-3.48')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
patch=here/'ns3.patch'
actual=subprocess.check_output(['git','-c','core.autocrlf=false','diff','--binary'],cwd=root)
if actual!=patch.read_bytes(): raise ValueError('Source does not match final patch')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,default=here/'build-ready.json')
a=p.parse_args()
ready=a.out
if ready.exists(): raise ValueError('Readiness receipt already exists')
start=time.monotonic()
with Path('/tmp/orbit-tail-build.log').open('w') as log:
    subprocess.run(['./ns3','build','-j','1'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
files=[root/'build/scratch/main_satnet/ns3.48-main_satnet',
       root/'build/scratch/study_micro/ns3.48-study_micro',*sorted((root/'build/lib').glob('*.so'))]
record=dict(patch_sha256=sha(patch),runtime_files={str(p.relative_to(root/'build')):sha(p) for p in files},
            build_log_sha256=sha(Path('/tmp/orbit-tail-build.log')),wall_seconds=time.monotonic()-start,
            build_command=['./ns3','build','-j','1'],build_status='success',tool_sha256=sha(Path(__file__)))
ready.parent.mkdir(parents=True,exist_ok=True)
ready.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'build_status':'success','wall_seconds':record['wall_seconds'],
                  'patch_sha256':record['patch_sha256']}))
