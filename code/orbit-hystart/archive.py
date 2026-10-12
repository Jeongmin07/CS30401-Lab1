"""Archive the six completed raw cases and independently verify every member."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time

CASES=['near-on','near-off','stable-on','stable-off','near-on-unobserved','near-forecast']


def digest(stream):
    h=hashlib.sha256()
    for b in iter(lambda:stream.read(1048576),b''): h.update(b)
    return h.hexdigest()


def sha(p):
    with p.open('rb') as f: return digest(f)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-hystart'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or a.receipt.exists(): raise ValueError('Refusing existing archive or receipt')
    inputs=[]
    for case in CASES:
        r=a.root/case
        m=json.loads((r/'manifest.json').read_text())
        assert m['status']=='success' and m['exit_code']==0
        for rel,item in m['output_files'].items():
            f=r/rel
            assert f.stat().st_size==item['bytes'] and sha(f)==item['sha256']
        for f in sorted(r.rglob('*')):
            if f.is_symlink(): raise ValueError('Archive input must not be a symlink')
            if f.is_file(): inputs.append((f,str(f.relative_to(a.root))))
    members={name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f,name in inputs}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with tarfile.open(a.out,'w:gz',compresslevel=6) as archive:
        for f,name in inputs: archive.add(f,arcname=name,recursive=False)
    with tarfile.open(a.out,'r:gz') as archive:
        actual=archive.getmembers()
        assert {m.name for m in actual}==set(members) and len(actual)==len(members)
        for m in actual:
            assert m.isfile() and m.size==members[m.name]['bytes']
            with archive.extractfile(m) as stream: assert digest(stream)==members[m.name]['sha256']
    record=dict(archive_path=str(a.out),archive_bytes=a.out.stat().st_size,archive_sha256=sha(a.out),
        member_count=len(members),uncompressed_member_bytes=sum(r['bytes'] for r in members.values()),
        all_members_stream_verified=True,cases=CASES,wall_seconds=time.monotonic()-start,
        helper_sha256=sha(Path(__file__)),members=members,
        limits='Local archive verification only. Root records the shared prerelease URL/digest. No independent simulation replay or statistical replication is claimed.')
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({k:record[k] for k in ['archive_path','archive_bytes','archive_sha256',
         'member_count','uncompressed_member_bytes','all_members_stream_verified','wall_seconds']},indent=2))


if __name__=='__main__': main()
