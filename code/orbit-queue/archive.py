"""Preserve completed queue conditions with exact per-file/member receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();assert not a.archive.exists() and not a.receipt.exists(),'Refuse overwrite'
    start=time.monotonic();files={};cases={}
    for name in a.cases:
        assert Path(name).name==name,'Case must be a direct child'
        run=a.root/name;m=json.loads((run/'manifest.json').read_text())
        assert m['status']=='success' and m['exit_code']==0 and m['source_unchanged'] and m['runtime_unchanged']
        actual={str(p.relative_to(run)) for p in run.rglob('*') if p.is_file()}
        assert actual==set(m['output_files'])|{'manifest.json'},'Unexpected run files'
        for rel in sorted(actual):
            path=run/rel;record=dict(bytes=path.stat().st_size,sha256=sha(path))
            if rel!='manifest.json':assert record==m['output_files'][rel],rel
            files[name+'/'+rel]=record
        cases[name]=dict(status=m['status'],exit_code=m['exit_code'],wall_seconds=m['wall_seconds'],
                        launch_commit=m['launch_commit'],source_checkpoint=m['declared_source_checkpoint'],
                        patch_sha256=m['patch_sha256'],runtime_files=m['runtime_files'],
                        manifest_sha256=sha(run/'manifest.json'))
    a.archive.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(a.archive,'w:gz',compresslevel=6) as tar:
        for name in files:tar.add(a.root/name,arcname=name,recursive=False)
    archived={}
    with tarfile.open(a.archive,'r:gz') as tar:
        for member in tar:
            assert member.isfile() and member.name in files
            stream=tar.extractfile(member);h=hashlib.sha256()
            for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
            archived[member.name]=dict(bytes=member.size,sha256=h.hexdigest())
    assert archived==files,'Archive bytes differ'
    assert all(sha(a.root/name)==record['sha256'] for name,record in files.items()),'Source changed during archive'
    repo=Path(__file__).resolve().parents[2]
    git=lambda *args:subprocess.check_output(['git','-c',f'safe.directory={repo}','-c','core.autocrlf=false',*args],cwd=repo).decode().strip()
    record=dict(schema=1,archive=dict(path=str(a.archive),bytes=a.archive.stat().st_size,sha256=sha(a.archive)),
        root=str(a.root),cases=cases,files=files,file_count=len(files),raw_bytes=sum(v['bytes'] for v in files.values()),
        archive_members_byte_verified=True,source_files_still_unchanged=True,
        helper_sha256=sha(Path(__file__)),posthoc_git_head=git('rev-parse','HEAD'),posthoc_repo_dirty=bool(git('status','--porcelain')),
        wall_seconds=time.monotonic()-start,scope='Completed run files only; no source volume or generated full routing state.',
        source_recipe='Launch source commits and full runtime hashes are recorded separately per case; posthoc archiver identity is distinct.')
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({'archive':record['archive'],'receipt':str(a.receipt),'file_count':len(files),
                      'raw_bytes':record['raw_bytes'],'wall_seconds':record['wall_seconds']}))


if __name__=='__main__':main()
