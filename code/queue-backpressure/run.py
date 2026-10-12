"""Three predeclared native queue controls; simulation requires checkpoint."""
import argparse
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
TAIL_SHA='5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29'
spec=importlib.util.spec_from_file_location('unchanged_tail',REPO/'code/orbit-tail/run.py')
tail=importlib.util.module_from_spec(spec);spec.loader.exec_module(tail)
CASES={'control100':('off',100,0),'fifo4-96':('fifo',4,96),'codel4-96':('codel',4,96)}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def git(*args,cwd=REPO):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}','-c','core.autocrlf=false',*args],cwd=cwd)


def runtime():
    return {str(p.relative_to(NS3/'build')):sha(p) for p in
            [NS3/'build/scratch/main_satnet/ns3.48-main_satnet',NS3/'build/scratch/study_micro/ns3.48-study_micro',
             *sorted((NS3/'build/lib').glob('*.so'))]}


def execute(name,args):
    for process in ['cc1plus','ninja','cmake','make']:
        if subprocess.run(['pgrep','-x',process],stdout=subprocess.DEVNULL).returncode==0:raise ValueError('Build active')
    patch=HERE/'ns3.patch';ready=json.loads(args.ready.read_text());diff=git('diff','--binary','HEAD',cwd=NS3)
    assert diff==patch.read_bytes() and ready['patch_sha256']==sha(patch),'Source/artifact/readiness mismatch'
    assert sha(REPO/'code/orbit-tail/ns3.patch')==TAIL_SHA,'Tail base changed'
    before=runtime();assert before==ready['runtime_files'],'Runtime differs from completed build'
    mode,device_max,qd_max=CASES[name]
    case=dict(kind='leo',mode='selective',rate=10,queue=100,duration=200,tail=True)
    actual_name=name+('-first-seq1-loss' if args.drop_first_seq1 else '')
    run=args.root/actual_name;run.mkdir(parents=True,exist_ok=False)
    additional,hints=tail.parameters(case)
    subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
    (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n',newline='\n')
    config=dict(line.split('=',1) for line in (run/'config_ns3.properties').read_text().splitlines() if '=' in line)
    assert config['tcp_socket_type']=='TcpCubic' and config['tcp_enable_pacing']=='false'
    argv=[str(NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}','--ns3::TcpSocketBase::OrbitTailAdmission=true']
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_STUDY_TRACE='1',CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),
        CS30401_ORBIT_ACTUAL_DROP='0',CS30401_ORBIT_QUEUE_TRACE='1',CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
        CS30401_ORBIT_SERVICE_TRACE='1',CS30401_QUEUE_FLOW_TRACE='1',CS30401_BACKPRESSURE_MODE=mode,
        CS30401_BACKPRESSURE_DROP_FIRST_SEQ1='1' if args.drop_first_seq1 else '0')
    record=dict(case=actual_name,status='running',definition=case,queue_mode=mode,tail_admission=True,
        source_device_max_packets=device_max,source_qdisc_max_packets=qd_max,nominal_queue_budget_packets=100,
        requeued_and_serializing_excluded_from_nominal_max=True,
        codel_defaults=dict(target_ns=5000000,interval_ns=100000000,min_bytes=1500,use_ecn=False,use_l4s=False) if mode=='codel' else None,
        policy_changed=False,forwarding_input_changed=False,physical_drop_first_original_seq1=bool(args.drop_first_seq1),
        command=argv,cwd=str(NS3),environment={k:v for k,v in env.items() if k.startswith('CS30401_') or k=='LD_LIBRARY_PATH'},
        source_checkpoint=args.checkpoint,launch_commit=git('rev-parse','HEAD').decode().strip(),repo_dirty=bool(git('status','--porcelain')),
        source_files={str(p.relative_to(REPO)):sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.h')},
        dependencies={str(p.relative_to(REPO)):sha(p) for p in [REPO/'code/orbit-tail/run.py',REPO/'code/orbit-tail/ns3.patch',
            REPO/'code/predict-loss/run.py',REPO/'code/orbit-geometry/forward-hints.csv']},
        tail_base_patch_sha256=TAIL_SHA,patch_sha256=sha(patch),installed_diff_sha256=hashlib.sha256(diff).hexdigest(),
        ns3_head=git('rev-parse','HEAD',cwd=NS3).decode().strip(),runtime_files=before,build_ready_sha256=sha(args.ready),image_ref=IMAGE,
        hints=hints,additional_parameters=additional,input_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [run/'config_ns3.properties',run/'schedule.csv']},
        state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:sha(p) for p in sorted((STATE/'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()},
        timeout_s=args.timeout,windows_ns={'whole':[0,200000000000],'post':[75000000000,75500000000],'focus':[74500000000,77500000000]},
        prospective_gates=dict(min_goodput_ratio=.995,max_post_queue_ratio=.5,max_post_served_wait_ratio=.5,max_focus_unique_tx_losses=5,
                              whole_queue_wait_unique_losses_not_worse=True))
    manifest=run/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n');start=time.monotonic()
    with (run/'console.txt').open('w') as log:
        try:
            result=subprocess.run(argv,cwd=NS3,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record['wall_seconds']=time.monotonic()-start
    record['runtime_unchanged']=runtime()==before;record['source_unchanged']=git('diff','--binary','HEAD',cwd=NS3)==diff
    if not record['runtime_unchanged'] or not record['source_unchanged']:record['status']='invalid_mutation'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds','runtime_unchanged','source_unchanged']}),flush=True)
    if record['status']!='success':raise SystemExit('Incomplete attempt preserved; batch stopped')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/queue-backpressure'));p.add_argument('--ready',type=Path,default=HERE/'build-ready.json')
    p.add_argument('--checkpoint',required=True);p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--drop-first-seq1',action='store_true',help='Prepared later control; not enabled in initial three conditions')
    args=p.parse_args()
    for case in args.cases:execute(case,args)
