"""Apply an exact frozen runtime, build once, and export with official make_patch.sh."""
import argparse
import os
from pathlib import Path
import subprocess
import time
import common as c


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=c.PATCHES,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.parent.mkdir(parents=True,exist_ok=True)
    assert not a.out.resolve().is_relative_to(c.HERE),'Keep readiness/logs outside package source'
    patch=c.HERE/'runtimes'/(a.profile+'.patch');source=c.source_files();start=time.monotonic();log=a.out.with_suffix('.build.log')
    export=a.out.with_suffix('.official.patch');assert not log.exists() and not export.exists()
    record=dict(profile=a.profile,build_status='preparing',patch_sha256=c.sha(patch),source_files=source,
        ns3_head=c.BASE,image_ref=c.IMAGE,package_git=c.identity(),build_command=['./ns3','build','-j','1'])
    c.write(a.out,record)
    try:
        assert c.sha(patch)==c.PATCHES[a.profile]
        assert c.git('rev-parse','HEAD').decode().strip()==c.BASE
        assert c.git('rev-parse','cs30401-base').decode().strip()==c.BASE
        assert not c.git('status','--porcelain').strip(),'Require a fresh official source volume'
        subprocess.run(['git','-c','core.autocrlf=false','apply','--check',str(patch)],cwd=c.NS3,check=True)
        subprocess.run(['git','-c','core.autocrlf=false','apply',str(patch)],cwd=c.NS3,check=True)
        # Official helper stages every new file. It changes index state, not source.
        with export.with_suffix('.export.log').open('w') as f:
            subprocess.run(['bash','/home/ubuntu/lab/scripts/make_patch.sh',str(export)],cwd=c.NS3,
                env=dict(os.environ,NS3_DIR=str(c.NS3)),stdout=f,stderr=subprocess.STDOUT,check=True)
        assert export.read_bytes()==patch.read_bytes(),'Official patch differs byte-for-byte from frozen source'
        record.update(build_status='running',official_export=c.receipt(export),official_export_byte_equal=True,
            official_helper=c.receipt(Path('/home/ubuntu/lab/scripts/make_patch.sh')))
        c.write(a.out,record)
        with log.open('w') as f:
            result=subprocess.run(['./ns3','build','-j','1'],cwd=c.NS3,stdout=f,stderr=subprocess.STDOUT)
        record.update(build_status='success' if result.returncode==0 else 'failed',exit_code=result.returncode,
            build_log=c.receipt(log),source_files_unchanged=source==c.source_files())
        assert c.git('diff','--binary','HEAD')==patch.read_bytes(),'Source changed during build'
        assert record['source_files_unchanged'],'Package helper/input changed during build'
        if result.returncode==0:record['runtime_files']=c.runtime()
    except Exception as error:
        record.update(build_status='failed',error=type(error).__name__+': '+str(error))
        if log.exists():record['build_log']=c.receipt(log)
        if export.exists():record['official_export']=c.receipt(export)
        record['wall_seconds']=time.monotonic()-start;c.write(a.out,record)
        raise
    record['wall_seconds']=time.monotonic()-start;c.write(a.out,record)
    print(__import__('json').dumps({k:record[k] for k in ['profile','build_status','wall_seconds','patch_sha256']}))
    if result.returncode:raise SystemExit('Failed build preserved; no simulation authorized')
