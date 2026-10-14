"""Build already-applied, checkpointed source; never edit the prior runtime."""
import argparse
import os
from pathlib import Path
import subprocess
import time
import common as c

p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
assert not a.out.exists()
source=c.source_files();patch=c.HERE/'ns3.patch';diff=c.git('diff','--binary','HEAD')
assert diff==patch.read_bytes() and c.git('rev-parse','HEAD').decode().strip()==c.BASE
log=a.out.with_suffix('.build.log');export=a.out.with_suffix('.official.patch')
assert not log.exists() and not export.exists()
record=dict(build_status='preparing',patch_sha256=c.sha(patch),source_files=source,
    image_ref=c.IMAGE,ns3_head=c.BASE,build_command=['./ns3','build','-j','2'])
c.write(a.out,record);start=time.monotonic()
try:
    with export.with_suffix('.export.log').open('w') as f:
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_patch.sh',str(export)],cwd=c.NS3,
            env=dict(os.environ,NS3_DIR=str(c.NS3)),stdout=f,stderr=subprocess.STDOUT,check=True)
    assert export.read_bytes()==patch.read_bytes()
    record.update(build_status='running',official_export_byte_equal=True,official_export_sha256=c.sha(export))
    c.write(a.out,record)
    with log.open('w') as f:
        r=subprocess.run(record['build_command'],cwd=c.NS3,stdout=f,stderr=subprocess.STDOUT)
    record.update(build_status='success' if r.returncode==0 else 'failed',exit_code=r.returncode,
        source_files_unchanged=source==c.source_files(),build_log_sha256=c.sha(log))
    assert c.git('diff','--binary','HEAD')==patch.read_bytes()
    assert record['source_files_unchanged']
    if r.returncode==0:record['runtime_files']=c.runtime()
except Exception as e:
    record.update(build_status='failed',error=f'{type(e).__name__}: {e}')
    c.write(a.out,record);raise
record['wall_seconds']=time.monotonic()-start;c.write(a.out,record)
print(__import__('json').dumps({k:record[k] for k in ('build_status','wall_seconds','patch_sha256')}),flush=True)
if record['build_status']!='success':raise SystemExit('Build failed; preserve attempt')
