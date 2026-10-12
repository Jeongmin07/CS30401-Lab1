"""Four declared matched orbit-BDP cases, inside the dedicated official container."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NS3=Path('/home/ubuntu/ns-3.48')
STATE=Path('/home/ubuntu/lab/data/seoul_london/state')
IMAGE='ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
CASES={f'bbr{rate}-{mode}40':{'rate':rate,'enabled':mode=='orbit'}
       for rate in (100,10) for mode in ('base','orbit')}
WINDOWS={'whole':[0,40],'steady':[10,40],'shortening':[25.7,28.2]}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def git(*args,cwd=REPO):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}',*args],cwd=cwd)

def prepare():
    source=Path('/tmp/orbit-bdp-path-truth.csv')
    if not source.exists():raise ValueError('Regenerate supplied state with official path_truth.py first')
    rows=list(csv.DictReader(source.open(newline='')))
    historical=list(csv.DictReader((REPO/'code/kim-study/path_truth_200s.csv').open(newline='')))
    if rows!=historical:raise ValueError('Regenerated supplied geometry differs from declared study geometry')
    out=HERE/'geometry.csv'
    if out.exists():raise ValueError('Refusing geometry overwrite')
    converted=[]
    for i,r in enumerate(rows):
        t=int(Decimal(r['t_s'])*10**9);rt=int(Decimal(r['rtt_prop_ms'])*10**6)
        if t!=i*100000000 or rt<=0:raise ValueError('Malformed provided geometry sequence')
        converted.append((t,rt))
    if len(converted)!=2000:raise ValueError('Expected complete 200s/100ms geometry')
    with out.open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['time_ns','prop_rtt_ns']);w.writerows(converted)
    receipt={'official_regenerated_truth_sha256':sha(source),'geometry_sha256':sha(out),
             'historical_truth_sha256':sha(REPO/'code/kim-study/path_truth_200s.csv'),
             'all_2000_rows_equal':True,'rows':len(rows),'kind':'two-direction propagation RTT, no queue/serialization',
             'command':['python3','/home/ubuntu/lab/scripts/path_truth.py',str(STATE),
                        'dynamic_state_100ms_for_200s','1584','1585',str(source)]}
    (HERE/'geometry-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

def execute(name,root,timeout):
    d=CASES[name];run=root/name;run.mkdir(parents=True,exist_ok=False)
    subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),
                    'TcpBbr',str(d['rate']),'100','40','1584','1585'],check=True,capture_output=True)
    config=run/'config_ns3.properties';schedule=run/'schedule.csv'
    schedule.write_text('0,1584,1585,100000000000,0,,\n')
    if 'tcp_enable_pacing=true' not in config.read_text():raise ValueError('Expected BBR pacing on')
    patch=HERE/'ns3.patch';diff=git('diff','--binary','HEAD',cwd=NS3)
    if diff.strip()!=patch.read_bytes().strip():raise ValueError('Installed source differs from declared full patch')
    binary=NS3/'build/scratch/main_satnet/ns3.48-main_satnet'
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_BBR_OBSERVE='1',
             CS30401_BBR_OBSERVE_DIR=str(run/'logs_ns3'),CS30401_ORBIT_BDP='1' if d['enabled'] else '0',
             CS30401_ORBIT_BDP_CSV=str(HERE/'geometry.csv'))
    argv=[str(binary),f'--run_dir={run}']
    record={'case':name,'definition':{'observe':True,'starts':[0],**d},'status':'running',
            'repo_commit':git('rev-parse','HEAD').decode().strip(),'repo_dirty':bool(git('status','--porcelain')),
            'runner_sha256':sha(__file__),'policy_sources':{p.name:sha(p) for p in HERE.glob('*') if p.is_file()},
            'ns3_head':git('rev-parse','HEAD',cwd=NS3).decode().strip(),
            'effective_build_diff_sha256':hashlib.sha256(diff).hexdigest(),'patch_sha256':sha(patch),
            'observer_patch_sha256':sha(REPO/'code/bbr-route/ns3-observe.patch'),
            'command':argv,'config_sha256':sha(config),'schedule_sha256':sha(schedule),
            'environment':{k:env[k] for k in ['LD_LIBRARY_PATH','CS30401_BBR_OBSERVE',
                 'CS30401_BBR_OBSERVE_DIR','CS30401_ORBIT_BDP','CS30401_ORBIT_BDP_CSV']},
            'runtime_files':{str(p.relative_to(NS3/'build')):sha(p) for p in
                              [binary,*sorted((NS3/'build/lib').glob('*.so'))]},
            'state_static_sha256':{p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
            'dynamic_input_sha256':{p.name:sha(p) for p in sorted((STATE/'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()},
            'declared_image_digest':IMAGE,'sim_seconds':40,'rate_mbps':d['rate'],'queue_packets':100,
            'seed':123456789,'windows':WINDOWS,'timeout_seconds':timeout,
            'policy':'ProbeBW cwnd target BDP RTT only; lookup now+current geometry RTT; stock BWestimate/gain',
            'geometry_sha256':sha(HERE/'geometry.csv')}
    manifest=run/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n')
    start=time.monotonic()
    try:
        with (run/'out.txt').open('w') as log:
            r=subprocess.run(argv,env=env,cwd=NS3,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        record.update(returncode=r.returncode,status='success' if r.returncode==0 else 'failed')
    except subprocess.TimeoutExpired:record.update(status='timeout',returncode=None)
    record['wall_seconds']=time.monotonic()-start
    record['outputs']={str(p.relative_to(run)):{'bytes':p.stat().st_size,'sha256':sha(p)}
                       for p in sorted((run/'logs_ns3').glob('*')) if p.is_file()}
    manifest.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds']}),flush=True)
    if record['status']!='success':raise RuntimeError(f'Incomplete {name}: {run}/out.txt')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases',nargs='*',choices=list(CASES))
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-bdp'))
    p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--prepare',action='store_true')
    a=p.parse_args()
    if a.prepare:prepare()
    else:
        if not a.cases:raise ValueError('Select at least one declared case')
        for name in a.cases:execute(name,a.root,a.timeout)

if __name__=='__main__':main()
