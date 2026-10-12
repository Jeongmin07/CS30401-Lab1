"""Synchronous single-job build of the observation-only complete artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=Path('/home/ubuntu/ns-3.48')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=HERE/'build-ready.json')
a=p.parse_args()
if a.out.exists():raise ValueError('Readiness output already exists')
patch=HERE/'ns3.patch';diff=subprocess.check_output(['git','-c','core.autocrlf=false','diff','--binary'],cwd=ROOT)
if diff!=patch.read_bytes():raise ValueError('Source differs from combined artifact')
log=Path('/tmp/queue-pacing-build.log');start=time.monotonic()
with log.open('w') as f:
    subprocess.run(['./ns3','build','-j','1'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
files=[ROOT/'build/scratch/main_satnet/ns3.48-main_satnet',ROOT/'build/scratch/study_micro/ns3.48-study_micro',*sorted((ROOT/'build/lib').glob('*.so'))]
record=dict(build_status='success',build_command=['./ns3','build','-j','1'],wall_seconds=time.monotonic()-start,
    patch_sha256=sha(patch),installed_diff_sha256=hashlib.sha256(diff).hexdigest(),tool_sha256=sha(__file__),
    runtime_files={str(x.relative_to(ROOT/'build')):sha(x) for x in files},build_log=dict(path=str(log),bytes=log.stat().st_size,sha256=sha(log)))
a.out.write_text(json.dumps(record,indent=2)+'\n',newline='\n');print(json.dumps({k:record[k] for k in ['build_status','wall_seconds','patch_sha256']}))
