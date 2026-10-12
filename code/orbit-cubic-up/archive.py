"""Archive one immutable attempt and verify every decompressed member hash."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

def digest(stream):
    h=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def sha(p):
    with p.open('rb') as f:return digest(f)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or a.inventory.exists():raise ValueError('Outputs must be new')
    manifest=json.loads((a.run/'manifest.json').read_text())
    if manifest['status']=='running':raise ValueError('Attempt still running')
    files=[]
    for f in sorted(a.run.rglob('*')):
        if not f.is_file():continue
        relative=str(f.relative_to(a.run))
        actual={'path':a.run.name+'/'+relative,'bytes':f.stat().st_size,'sha256':sha(f)}
        if f.name!='manifest.json':
            expected=manifest['output_files'][relative]
            if actual['bytes']!=expected['bytes'] or actual['sha256']!=expected['sha256']:raise ValueError('Attempt output changed: '+relative)
        files.append(actual)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(a.out,'w:gz',compresslevel=1) as t:
        for row in files:t.add(a.run.parent/row['path'],arcname=row['path'],recursive=False)
    with tarfile.open(a.out,'r:gz') as t:
        members=t.getmembers()
        if len(members)!=len(files):raise ValueError('Archive count differs')
        for member,expected in zip(members,files):
            with t.extractfile(member) as stream:actual=digest(stream)
            if member.name!=expected['path'] or member.size!=expected['bytes'] or actual!=expected['sha256']:raise ValueError('Archive content differs')
    record={'case':manifest['case'],'execution_status':manifest['status'],'eligible_for_performance_analysis':manifest['status']=='success' and manifest['exit_code']==0,'archive_path':str(a.out),'archive_bytes':a.out.stat().st_size,'archive_sha256':sha(a.out),'file_count':len(files),'uncompressed_bytes':sum(x['bytes'] for x in files),'every_decompressed_member_verified':True,'files':files,'exclusions':['No generated constellation state, ns-3 source, runtime binaries or build directories.'],'limits':['A preserved timeout archive is a failed attempt, not a completed 200-second result.','No independently repeated simulation was performed by this archive operation.']}
    a.inventory.parent.mkdir(parents=True,exist_ok=True);a.inventory.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['case','execution_status','archive_bytes','archive_sha256','file_count','uncompressed_bytes']}))
if __name__=='__main__':main()
