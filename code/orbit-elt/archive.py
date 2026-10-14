"""Archive successful raw runs, detailed analysis and preserved failed attempts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
assert not a.out.exists()
entries=['orbit-elt-v2','orbit-elt','orbit-elt-build-attempt1',
    'orbit-elt-ready.json','orbit-elt-ready.build.log','orbit-elt-ready.official.patch',
    'orbit-elt-ready-v2.json','orbit-elt-ready-v2.build.log','orbit-elt-ready-v2.official.patch',
    'orbit-elt-ready-v3.json','orbit-elt-ready-v3.build.log','orbit-elt-ready-v3.official.patch']
assert all((Path('/tmp')/n).exists() for n in entries)
subprocess.run(['tar','--use-compress-program=gzip -1','-cf',str(a.out),'-C','/tmp',*entries,
    '-C','/work/code/orbit-elt','results'],check=True)
subprocess.run(['tar','-tzf',str(a.out)],check=True,stdout=subprocess.DEVNULL)
h=hashlib.sha256()
with a.out.open('rb') as f:
    for b in iter(lambda:f.read(1048576),b''):h.update(b)
receipt=dict(path=str(a.out),bytes=a.out.stat().st_size,sha256=h.hexdigest(),
    scope='19 completed physical runs, detailed fresh analysis, unchanged-source build receipts and pre-simulation failed attempts',
    compression='tar + gzip -1',verified_readable=True)
Path(str(a.out)+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
