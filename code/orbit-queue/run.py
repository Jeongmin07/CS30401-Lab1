"""Run the two predeclared pure observers after the shared source checkpoint."""
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
IMAGE='ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
spec=importlib.util.spec_from_file_location('unchanged_v2_runner',REPO/'code/orbit-loss/run.py')
v2=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2)
CASES={'base-natural':dict(kind='leo',mode='base',rate=10,queue=100,duration=200),
       'selective-natural':dict(kind='leo',mode='selective',rate=10,queue=100,duration=200)}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def git(*args,cwd=REPO):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}','-c','core.autocrlf=false',*args],cwd=cwd)


def runtime():
    return {str(p.relative_to(NS3/'build')):sha(p) for p in
            [NS3/'build/scratch/main_satnet/ns3.48-main_satnet',
             NS3/'build/scratch/study_micro/ns3.48-study_micro',*sorted((NS3/'build/lib').glob('*.so'))]}


def execute(name,root,timeout,readiness,checkpoint):
    for process in ['cc1plus','ninja','cmake','make']:
        if subprocess.run(['pgrep','-x',process],stdout=subprocess.DEVNULL).returncode==0:
            raise ValueError('Build still active: '+process)
    patch=HERE/'ns3.patch';ready=json.loads(readiness.read_text());diff=git('diff','--binary','HEAD',cwd=NS3)
    if diff!=patch.read_bytes() or ready['patch_sha256']!=sha(patch):raise ValueError('Source/readiness mismatch')
    before=runtime()
    if before!=ready['runtime_files']:raise ValueError('Runtime differs from completed build')
    case=CASES[name];run=root/name;run.mkdir(parents=True,exist_ok=False)
    additional,hints=v2.parameters(case)
    subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
    (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n',newline='\n')
    config=dict(line.split('=',1) for line in (run/'config_ns3.properties').read_text().splitlines() if '=' in line)
    if config['tcp_socket_type']!='TcpCubic' or config['tcp_enable_pacing']!='false':raise ValueError('Wrong original TCP settings')
    argv=[str(NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}']
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_STUDY_TRACE='1',
             CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),CS30401_ORBIT_ACTUAL_DROP='0',
             CS30401_ORBIT_QUEUE_TRACE='1',CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
             CS30401_ORBIT_SERVICE_TRACE='1',CS30401_QUEUE_FLOW_TRACE='1')
    dependencies=[REPO/'code/orbit-loss/run.py',REPO/'code/predict-loss/run.py',REPO/'code/orbit-geometry/forward-hints.csv',REPO/'code/orbit-loss/ns3.patch']
    record=dict(case=name,status='running',definition=case,command=argv,cwd=str(NS3),
        declared_source_checkpoint=checkpoint,launch_commit=git('rev-parse','HEAD').decode().strip(),repo_dirty=bool(git('status','--porcelain')),
        source_files={str(p.relative_to(REPO)):sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.h')},
        dependency_files={str(p.relative_to(REPO)):sha(p) for p in dependencies},
        patch_sha256=sha(patch),installed_diff_sha256=hashlib.sha256(diff).hexdigest(),ns3_head=git('rev-parse','HEAD',cwd=NS3).decode().strip(),
        runtime_files=before,build_ready_sha256=sha(readiness),image_ref=IMAGE,timeout_s=timeout,
        hints=hints,additional_parameters=additional,environment={k:env[k] for k in ['LD_LIBRARY_PATH','CS30401_STUDY_TRACE','CS30401_STUDY_TRACE_DIR','CS30401_ORBIT_ACTUAL_DROP','CS30401_ORBIT_QUEUE_TRACE','CS30401_ORBIT_QUEUE_TRACE_DIR','CS30401_ORBIT_SERVICE_TRACE','CS30401_QUEUE_FLOW_TRACE']},
        input_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [run/'config_ns3.properties',run/'schedule.csv']},
        state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:sha(p) for p in sorted((STATE/'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()},
        windows_ns={'pre':[74500000000,75000000000],'post':[75000000000,75500000000],
                    'legacy':[74500000000,77000000000],'focus':[74500000000,77500000000]},
        policy_changed=False,observer_only=True)
    manifest=run/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    start=time.monotonic()
    with (run/'console.txt').open('w') as log:
        try:
            result=subprocess.run(argv,cwd=NS3,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record['wall_seconds']=time.monotonic()-start
    record['runtime_unchanged']=runtime()==before
    record['source_unchanged']=git('diff','--binary','HEAD',cwd=NS3)==diff
    if not record['runtime_unchanged'] or not record['source_unchanged']:record['status']='invalid_source_or_runtime_changed'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds','runtime_unchanged','source_unchanged']}),flush=True)
    if record['status']!='success':raise SystemExit('Incomplete attempt preserved; stop batch')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-queue'))
    p.add_argument('--timeout',type=int,default=600);p.add_argument('--ready',type=Path,default=HERE/'build-ready.json')
    p.add_argument('--checkpoint',required=True,help='Parent-shared source/declaration Git checkpoint')
    a=p.parse_args()
    for case in a.cases:execute(case,a.root,a.timeout,a.ready,a.checkpoint)
