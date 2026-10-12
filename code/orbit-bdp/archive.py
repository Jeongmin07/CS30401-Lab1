"""Preserve the four completed raw runs, plus compact manifest/state evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

HERE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-bdp'))
    p.add_argument('--archive',type=Path,default=Path('/tmp/orbit-bdp-20261012.tar.gz'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.archive.exists() or a.out.exists():raise ValueError('Outputs must be new')
    a.out.mkdir(parents=True)
    entries=[];cases=[];comparisons=[]
    with tarfile.open(a.archive,'w:gz') as tar:
        for rate in (100,10):
            for mode in ('base','orbit'):
                name=f'bbr{rate}-{mode}40';run=a.root/name
                manifest=json.loads((run/'manifest.json').read_text())
                if manifest['status']!='success' or manifest['returncode']!=0:raise ValueError('Incomplete raw case')
                target=a.out/name;target.mkdir()
                for filename in ['manifest.json','config_ns3.properties','schedule.csv']:
                    shutil.copy2(run/filename,target/filename)
                for filename in ['bbr_state.csv','orbit_bdp_state.csv']:
                    shutil.copy2(run/'logs_ns3'/filename,target/filename)
                cases.append({'case':name,'execution_manifest_sha256':sha(run/'manifest.json'),
                              'wall_seconds':manifest['wall_seconds'],
                              'launch_sources':manifest['policy_sources'],'runner_sha256':manifest['runner_sha256']})
                for file in sorted(run.rglob('*')):
                    if not file.is_file():continue
                    if file.suffix not in ('.csv','.json','.txt','.properties'):raise ValueError('Unexpected archive member')
                    relative=str(file.relative_to(a.root));tar.add(file,arcname=relative,recursive=False)
                    entries.append({'path':relative,'bytes':file.stat().st_size,'sha256':sha(file)})
            left=a.root/f'bbr{rate}-base40/logs_ns3';right=a.root/f'bbr{rate}-orbit40/logs_ns3'
            for file in sorted(left.glob('*.csv')):
                if file.name in ('timing_results.csv','orbit_bdp_state.csv'):continue
                other=right/file.name
                comparisons.append({'rate_mbps':rate,'file':file.name,'baseline_sha256':sha(file),
                                    'policy_sha256':sha(other),'equal':sha(file)==sha(other)})
    with tarfile.open(a.archive,'r:gz') as tar:
        members={m.name:m for m in tar.getmembers()}
        if set(members)!={x['path'] for x in entries}:raise ValueError('Archive member set mismatch')
        for entry in entries:
            if members[entry['path']].size!=entry['bytes']:raise ValueError('Archive size mismatch')
            h=hashlib.sha256()
            with tar.extractfile(entry['path']) as f:
                for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
            if h.hexdigest()!=entry['sha256']:raise ValueError('Archive hash mismatch')
    record={'archive':str(a.archive),'archive_bytes':a.archive.stat().st_size,'archive_sha256':sha(a.archive),
            'member_count':len(entries),'uncompressed_bytes':sum(x['bytes'] for x in entries),
            'all_members_stream_verified':True,'members':entries,'cases':cases,
            'baseline_policy_measurement_comparison':comparisons,'archiver_sha256':sha(__file__),
            'contains_build_or_constellation_state':False}
    (a.out/'raw-inventory.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['archive','archive_bytes','archive_sha256','member_count','uncompressed_bytes','all_members_stream_verified']},indent=2))

if __name__=='__main__':main()
