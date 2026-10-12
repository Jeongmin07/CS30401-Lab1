"""Three native pacing controls, followed only by a prospectively selected safety stage."""
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
spec=importlib.util.spec_from_file_location('frozen_tail_runner',REPO/'code/orbit-tail/run.py')
tail=importlib.util.module_from_spec(spec);spec.loader.exec_module(tail)
INITIAL=['off','native','capacity']
SAFETY=['micro-original','micro-current','micro-selected','loss-current','loss-selected']
DEFAULT_MAX=4000000000
CAP10=10000000*1380//1434
CASES={
 'off':dict(kind='leo',mode='selective',tail=True,rate=10,queue=100,duration=200,pacing=False),
 'native':dict(kind='leo',mode='selective',tail=True,rate=10,queue=100,duration=200,pacing=True),
 'capacity':dict(kind='leo',mode='selective',tail=True,rate=10,queue=100,duration=200,pacing=True,capacity=True),
 'micro-original':dict(kind='micro',mode='base',tail=False,pacing=False,loss_seq=1),
 'micro-current':dict(kind='micro',mode='selective',tail=True,pacing=False,loss_seq=1),
 'micro-selected':dict(kind='micro',mode='selective',tail=True,pacing=True,loss_seq=1,selected=True),
 'loss-current':dict(kind='leo',mode='selective',tail=True,rate=10,queue=100,duration=200,pacing=False,first_loss=True),
 'loss-selected':dict(kind='leo',mode='selective',tail=True,rate=10,queue=100,duration=200,pacing=True,first_loss=True,selected=True),
}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def git(*args,cwd=REPO):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}','-c','core.autocrlf=false',*args],cwd=cwd)


def runtime():
    return {str(p.relative_to(NS3/'build')):sha(p) for p in
        [NS3/'build/scratch/main_satnet/ns3.48-main_satnet',NS3/'build/scratch/study_micro/ns3.48-study_micro',
         *sorted((NS3/'build/lib').glob('*.so'))]}


def definition(name,winner=None):
    case=dict(CASES[name])
    if case.get('selected'):
        if winner not in ['native','capacity']:raise ValueError('No prospectively eligible winner')
        case['capacity']=winner=='capacity'
        case['selected_setting']=winner
    return case


def maximum(case):
    return (case.get('rate',100)*1000000*1380//1434) if case.get('capacity') else DEFAULT_MAX


def native_cli(case):
    return ['--ns3::TcpSocketBase::OrbitTailAdmission='+str(case['tail']).lower(),
        '--ns3::TcpSocketState::EnablePacing='+str(case['pacing']).lower(),
        '--ns3::TcpSocketState::MaxPacingRate='+str(maximum(case))+'bps',
        '--ns3::TcpSocketState::PacingSsRatio=200','--ns3::TcpSocketState::PacingCaRatio=120',
        '--ns3::TcpSocketState::PaceInitialWindow=false']


def execute(name,root,timeout,readiness,checkpoint,selection=None):
    for process in ['cc1plus','ninja','cmake','make']:
        if subprocess.run(['pgrep','-x',process],stdout=subprocess.DEVNULL).returncode==0:
            raise ValueError('Build still active: '+process)
    if name in SAFETY and (not selection or selection.get('winner') not in ['native','capacity']):
        raise ValueError('Safety stage requires a completed prospective winner receipt')
    patch=HERE/'ns3.patch';ready=json.loads(readiness.read_text());diff=git('diff','--binary','HEAD',cwd=NS3)
    if ready['build_status']!='success' or diff!=patch.read_bytes() or ready['patch_sha256']!=sha(patch):
        raise ValueError('Source/readiness mismatch')
    before=runtime()
    if before!=ready['runtime_files']:raise ValueError('Runtime differs from completed build')
    case=definition(name,selection.get('winner') if selection else None)
    run=root/name;run.mkdir(parents=True,exist_ok=False);(run/'logs_ns3').mkdir()
    additional,hints=tail.parameters(case)
    if case['kind']=='leo':
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
        (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n',newline='\n')
        config=run/'config_ns3.properties';text=config.read_text()
        if text.count('tcp_enable_pacing=false')!=1:raise ValueError('Unexpected provided pacing configuration')
        config.write_text(text.replace('tcp_enable_pacing=false','tcp_enable_pacing='+str(case['pacing']).lower()),newline='\n')
        argv=[str(NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}']
    else:
        argv=[str(NS3/'build/scratch/study_micro/ns3.48-study_micro'),f'--run_dir={run}',
            '--cc=TcpCubic','--duration=4','--rate=100','--queue_pkts=2000','--before_ms=50',
            '--after_ms=50','--event_s=2','--initial_ssthresh_pkts=900','--max_bytes=27600',
            '--loss_seq=1','--enable_pacing='+str(case['pacing']).lower()]
        if additional:argv.append('--parameters='+additional)
    argv+=native_cli(case)
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_STUDY_TRACE='1',
        CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),CS30401_ORBIT_ACTUAL_DROP='0',
        CS30401_ORBIT_QUEUE_TRACE='1',CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
        CS30401_ORBIT_SERVICE_TRACE='1',CS30401_QUEUE_FLOW_TRACE='1',CS30401_QUEUE_PACING_RATE_TRACE='1',
        CS30401_QUEUE_PACING_FIRST_LOSS='1' if case.get('first_loss') else '0')
    dependencies=[REPO/'code/orbit-tail/run.py',REPO/'code/predict-loss/run.py',REPO/'code/orbit-geometry/forward-hints.csv',
        REPO/'code/orbit-tail/ns3.patch',REPO/'code/queue-metrics/queue_area.h',REPO/'code/orbit-queue/analyze.py',
        REPO/'code/orbit-tail/analyze.py',REPO/'code/orbit-loss/analyze.py',REPO/'code/predict-loss/summarize.py',
        REPO/'code/kim-study/analyze_study.py']
    source_files={str(p.relative_to(REPO)):sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.h')}
    record=dict(case=name,status='running',definition=case,tail_admission=case['tail'],command=argv,cwd=str(NS3),
        declared_source_checkpoint=checkpoint,launch_commit=git('rev-parse','HEAD').decode().strip(),
        repo_commit=git('rev-parse','HEAD').decode().strip(),repo_dirty=bool(git('status','--porcelain')),
        runner_sha256=sha(__file__),source_files=source_files,dependency_files={str(p.relative_to(REPO)):sha(p) for p in dependencies},
        patch_sha256=sha(patch),installed_diff_sha256=hashlib.sha256(diff).hexdigest(),runtime_files=before,
        build_ready_sha256=sha(readiness),ns3_head=git('rev-parse','HEAD',cwd=NS3).decode().strip(),
        declared_image_digest=IMAGE,image_ref=IMAGE,timeout_s=timeout,hints=hints,additional_parameters=additional,
        forecast_source_sha256=sha(tail.FORWARD),forecast_source=str(tail.FORWARD),
        input_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [run/'config_ns3.properties',run/'schedule.csv'] if p.exists()},
        state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:sha(p) for p in sorted((STATE/'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()} if case['kind']=='leo' else None,
        expected_finite_bytes=27600 if case['kind']=='micro' else None,
        declared_event_windows_s=[[25.7,28.2],[74.5,77.0]] if case['kind']=='leo' else [[1.5,4.0]],
        windows_ns={'whole':[0,200000000000],'pre':[74500000000,75000000000],'post':[75000000000,75500000000],
                    'legacy':[74500000000,77000000000],'focus':[74500000000,77500000000]} if case['kind']=='leo' else {'whole':[0,4000000000]},
        native_pacing=dict(enabled=case['pacing'],max_bps=maximum(case),ss_ratio=200,ca_ratio=120,pace_initial_window=False,
                           payload_bytes=1380,assumed_serialized_data_bytes=1434),
        observer_only=not case['pacing'] and not case.get('first_loss',False),policy_changed=case['pacing'],selection_receipt=selection,
        actual_drop_rule='First original directed flow0 sequence1 payload1380 at receiver node1585, once; transmission times may differ' if case.get('first_loss') else None,
        environment={k:v for k,v in env.items() if k.startswith('CS30401_') or k=='LD_LIBRARY_PATH'})
    manifest=run/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    start=time.monotonic()
    with (run/'console.txt').open('w') as log:
        try:
            result=subprocess.run(argv,cwd=NS3,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record['wall_seconds']=time.monotonic()-start
    record['runtime_unchanged']=runtime()==before;record['source_unchanged']=git('diff','--binary','HEAD',cwd=NS3)==diff
    record['launch_source_files_unchanged']=source_files=={p:sha(REPO/p) for p in source_files}
    if not record['runtime_unchanged'] or not record['source_unchanged']:record['status']='invalid_source_or_runtime_changed'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds','runtime_unchanged','source_unchanged']}),flush=True)
    if record['status']!='success':raise SystemExit('Incomplete attempt preserved; stop batch')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/queue-pacing'));p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--ready',type=Path,default=HERE/'build-ready.json');p.add_argument('--checkpoint',required=True)
    p.add_argument('--selection',type=Path)
    a=p.parse_args();selection=json.loads(a.selection.read_text()) if a.selection else None
    if selection:
        assert selection['prospective_gates_passed'] and selection['patch_sha256']==sha(HERE/'ns3.patch')
        assert selection['runtime_files']==runtime()
        selection=dict(selection,receipt_path=str(a.selection),receipt_sha256=sha(a.selection))
    for name in a.cases:execute(name,a.root,a.timeout,a.ready,a.checkpoint,selection)
