"""Seven predeclared selective-loss cases; execute inside the dedicated image."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NS3=Path('/home/ubuntu/ns-3.48')
STATE=Path('/home/ubuntu/lab/data/seoul_london/state')
FORWARD=REPO/'code/orbit-geometry/forward-hints.csv'
spec=importlib.util.spec_from_file_location('forecast_runner',REPO/'code/predict-loss/run.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
sha,git=base.sha,base.git
CASES={
 'micro-base':dict(kind='micro',mode='base',loss_seq=1),
 'micro-selective':dict(kind='micro',mode='selective',loss_seq=1),
 'leo10-base':dict(kind='leo',mode='base',rate=10,queue=100,duration=200),
 'leo10-bounded20':dict(kind='leo',mode='bounded',rate=10,queue=100,duration=200),
 'leo10-selective':dict(kind='leo',mode='selective',rate=10,queue=100,duration=200),
 'leo10-drop-base':dict(kind='leo',mode='base',rate=10,queue=100,duration=200,actual_drop=True),
 'leo10-drop-selective':dict(kind='leo',mode='selective',rate=10,queue=100,duration=200,actual_drop=True),
}


def hints(case):
    out=[]
    for row in csv.DictReader(FORWARD.open()):
        delta=int(row['old_fwd_ns'])-int(row['new_fwd_ns'])
        if row['fwd_changed']!='1' or delta<1000000: continue
        start=int(row['event_ns'])
        horizon=2*max(int(row['old_fwd_ns'])+int(row['old_rev_ns']),
                      int(row['new_fwd_ns'])+int(row['new_rev_ns']))
        rate=case.get('rate',100)*1000000
        budget=3+(rate*delta+8*1380*10**9-1)//(8*1380*10**9)
        out.append(dict(start_ns=start,end_ns=start+horizon,wait_ns=max(10**6,min(20*10**6,2*delta)),
                        packet_budget=budget,forward_drop_ns=delta,declared_link_rate_bps=rate,
                        old_forward_ns=int(row['old_fwd_ns']),MSS_bytes=1380))
    if case['kind']=='micro':
        e=out[0]
        return [dict(e,start_ns=150000000,end_ns=350000000,
                     note='Deliberately wrong positive geometry hint on stable 50/50ms path')]
    return out


def parameters(case):
    if case['mode']=='base': return '',[]
    if case['mode']=='bounded': return base.parameters(case)
    events=hints(case)
    return 'study_selective_epochs='+'|'.join(
        f"{e['start_ns']}:{e['end_ns']}:{e['wait_ns']}:{e['packet_budget']}" for e in events),events


def runtime():
    return {str(p.relative_to(NS3/'build')):sha(p) for p in
            [NS3/'build/scratch/main_satnet/ns3.48-main_satnet',
             NS3/'build/scratch/study_micro/ns3.48-study_micro',
             *sorted((NS3/'build/lib').glob('*.so'))]}


def execute(name,root,timeout,readiness):
    for process in ['cc1plus','ninja','cmake','make']:
        if subprocess.run(['pgrep','-x',process],stdout=subprocess.DEVNULL).returncode==0:
            raise ValueError('Pending build process: '+process)
    patch=HERE/'ns3.patch'
    ready=json.loads(readiness.read_text())
    source=git('diff','--binary','HEAD',cwd=NS3)
    if source!=patch.read_bytes().strip() or ready['patch_sha256']!=sha(patch):
        raise ValueError('Installed source/patch/readiness mismatch')
    before=runtime()
    if before!=ready['runtime_files']: raise ValueError('Runtime differs from completed build')
    case=CASES[name]
    run=root/name
    run.mkdir(parents=True,exist_ok=False)
    (run/'logs_ns3').mkdir()
    additional,events=parameters(case)
    if case['kind']=='leo':
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),
            'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
        (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n')
        argv=[str(NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}']
    else:
        argv=[str(NS3/'build/scratch/study_micro/ns3.48-study_micro'),f'--run_dir={run}',
              '--cc=TcpCubic','--duration=4','--rate=100','--queue_pkts=2000',
              '--before_ms=50','--after_ms=50','--event_s=2',
              '--initial_ssthresh_pkts=900','--max_bytes=27600','--loss_seq=1']
        if additional: argv.append('--parameters='+additional)
    env=dict(os.environ,CS30401_STUDY_TRACE='1',CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),
             LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_ORBIT_ACTUAL_DROP='1' if case.get('actual_drop') else '0')
    dynamic=STATE/'dynamic_state_100ms_for_200s'
    record=dict(case=name,definition=case,command=argv,status='running',
        repo_commit=git('rev-parse','HEAD').decode(),repo_dirty=bool(git('status','--porcelain')),
        runner_sha256=sha(Path(__file__)),patch_sha256=sha(patch),runtime_files=before,
        build_ready_sha256=sha(readiness),installed_diff_sha256=hashlib.sha256(source+b'\n').hexdigest(),
        ns3_head=git('rev-parse','HEAD',cwd=NS3).decode(),declared_image_digest=base.IMAGE,
        state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()}
                            if case['kind']=='leo' else None,
        forecast_source_sha256=sha(FORWARD),forecast_source=str(FORWARD),hints=events,
        additional_parameters=additional,timeout_s=timeout,
        expected_finite_bytes=27600 if case['kind']=='micro' else None,
        declared_event_windows_s=[[25.7,28.2],[74.5,77.0]] if case['kind']=='leo' else [[1.5,4.0]],
        actual_drop_rule='First original flow0 data received at node1585 at/afterT26.2 with TX in [T-48847704ns,T)' if case.get('actual_drop') else None,
        source_files={str(p.relative_to(REPO)):sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.h')},
        dependencies={str(p.relative_to(REPO)):sha(p) for p in [REPO/'code/predict-loss/run.py',
                        REPO/'code/kim-study/analyze_study.py',REPO/'code/predict-loss/summarize.py']},
        environment={k:env[k] for k in ['CS30401_STUDY_TRACE','CS30401_STUDY_TRACE_DIR',
                                     'LD_LIBRARY_PATH','CS30401_ORBIT_ACTUAL_DROP']})
    manifest=run/'manifest.json'
    manifest.write_text(json.dumps(record,indent=2)+'\n')
    start=time.monotonic()
    with (run/'console.txt').open('w') as f:
        try:
            result=subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired: record.update(status='timeout',exit_code=None)
    record['wall_seconds']=time.monotonic()-start
    record['runtime_unchanged']=runtime()==before
    if not record['runtime_unchanged']: record['audit_exclude']='Runtime changed during simulation'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p))
         for p in sorted(run.rglob('*')) if p.is_file() and p.name!='manifest.json'
         and p.suffix in ('.csv','.txt','.properties')}
    manifest.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds','runtime_unchanged']}),flush=True)
    if record['status']!='success' or not record['runtime_unchanged']:
        raise SystemExit('Incomplete or excluded case; batch stopped')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-loss'))
    p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--ready',type=Path,default=HERE/'build-ready.json')
    a=p.parse_args()
    for case in a.cases: execute(case,a.root,a.timeout,a.ready)
