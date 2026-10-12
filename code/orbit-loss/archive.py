"""Archive completed raw cases and stream-verify every member hash."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def digest(stream):
    h=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-loss'))
    p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or a.inventory.exists(): raise ValueError('Output exists')
    members=[]
    with tarfile.open(a.out,'w:gz',compresslevel=6) as archive:
        for name in a.cases:
            run=a.root/name
            m=json.loads((run/'manifest.json').read_text())
            if m['status']!='success' or not m['runtime_unchanged']: raise ValueError('Incomplete case')
            for f in sorted(run.rglob('*')):
                if not f.is_file(): continue
                key=str(f.relative_to(a.root))
                with f.open('rb') as s: sha=digest(s)
                members.append(dict(path=key,bytes=f.stat().st_size,sha256=sha))
                archive.add(f,arcname=key,recursive=False)
    expected={m['path']:m for m in members}
    verified=0
    with tarfile.open(a.out,'r|gz') as archive:
        for m in archive:
            if not m.isfile(): raise ValueError('Non-file member')
            e=expected[m.name]
            if m.size!=e['bytes'] or digest(archive.extractfile(m))!=e['sha256']:
                raise ValueError('Archive mismatch '+m.name)
            verified+=1
    if verified!=len(members): raise ValueError('Member count mismatch')
    with a.out.open('rb') as stream: sha=digest(stream)
    a.inventory.parent.mkdir(parents=True,exist_ok=True)
    a.inventory.write_text(json.dumps(dict(archive=a.out.name,bytes=a.out.stat().st_size,sha256=sha,
        file_count=verified,uncompressed_bytes=sum(m['bytes'] for m in members),
        every_member_verified=True,files=members),indent=2)+'\n')
    print(json.dumps(dict(bytes=a.out.stat().st_size,sha256=sha,members=verified)))
