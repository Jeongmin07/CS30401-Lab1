"""The 19 predeclared, independently executed ELT comparison conditions."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import common as c

def execute(name,a):
    d=c.CASES[name];ready,diff=c.ready_check(a.ready);before=c.runtime();sources=c.source_files()
    run=a.root/name;assert not run.exists(),'Refuse to overwrite attempts'
    run.mkdir(parents=True);(run/'logs_ns3').mkdir()
    additional,hints=c.deps.tail.parameters(d)
    if d['kind']=='leo':
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(c.STATE),
            'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
        (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n',newline='\n')
        argv=[str(c.NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}']
    else:
        argv=[str(c.NS3/'build/scratch/study_micro/ns3.48-study_micro'),f'--run_dir={run}',
            '--cc=TcpCubic','--duration=4','--rate=100','--queue_pkts=2000','--before_ms=50',
            '--after_ms=50','--event_s=2','--initial_ssthresh_pkts=900',
            f"--max_bytes={d['bytes']}",'--loss_seq=1','--enable_pacing=false']
        if additional:argv.append('--parameters='+additional)
    argv += [f"--ns3::TcpSocketBase::OrbitEltMode={d['elt_mode']}",
             '--ns3::TcpSocketBase::OrbitTailAdmission='+str(d['tail']).lower(),
             '--ns3::TcpSocketState::EnablePacing=false']
    env=dict(os.environ,LD_LIBRARY_PATH=str(c.NS3/'build/lib'),CS30401_STUDY_TRACE='1',
        CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),CS30401_ORBIT_ACTUAL_DROP='0',
        CS30401_ORBIT_QUEUE_TRACE='1',CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
        CS30401_ORBIT_SERVICE_TRACE='1',CS30401_QUEUE_FLOW_TRACE='1',
        CS30401_QUEUE_PACING_RATE_TRACE='1',CS30401_QUEUE_PACING_FIRST_LOSS='0')
    ns3=c.NS3;repo=c.HERE.parents[1]
    try:
        base=['git','-c',f'safe.directory={repo}']
        call=lambda *parts:subprocess.check_output(base+list(parts),cwd=repo,stderr=subprocess.DEVNULL)
        package_git=dict(commit=call('rev-parse','HEAD').decode().strip(),dirty=bool(call('status','--porcelain')))
    except subprocess.CalledProcessError:
        package_git=dict(commit=None,dirty=None,qualification=
            'Windows worktree Git metadata is inaccessible from this bind mount. Source checkpoint is host-declared; exact source files, installed patch and runtime are independently hashed.')
    record=dict(case=name,status='running',definition=d,profile='elt',tail_admission=d['tail'],
        expected_finite_bytes=d.get('bytes'),command=argv,cwd=str(ns3),
        source_checkpoint=a.checkpoint,declared_source_checkpoint=a.checkpoint,
        repo_commit=package_git['commit'],repo_dirty=package_git['dirty'],package_git=package_git,
        source_files=sources,runtime_files=before,patch_sha256=c.sha(c.HERE/'ns3.patch'),
        installed_diff_sha256=__import__('hashlib').sha256(diff).hexdigest(),
        runner_sha256=c.sha(Path(__file__)),build_ready_sha256=c.sha(a.ready),
        ns3_head=c.BASE,image_ref=c.IMAGE,hints=hints,additional_parameters=additional,
        forecast_source_sha256=c.sha(c.deps.tail.FORWARD),
        input_files={p.name:dict(bytes=p.stat().st_size,sha256=c.sha(p)) for p in
            [run/'config_ns3.properties',run/'schedule.csv'] if p.exists()},
        state_static_sha256={p.name:c.sha(p) for p in sorted(c.STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256=None,timeout_s=a.timeout,
        declared_event_windows_s=[[25.7,28.2],[74.5,77.5]] if d['kind']=='leo' else [],
        environment={k:v for k,v in env.items() if k.startswith('CS30401_') or k=='LD_LIBRARY_PATH'},
        interpretation='RFC-inspired short orbit-gated ELT adaptation, not full TCP-NCR; single-flow bounded exploration.')
    # Hash existing routing inputs without parsing any forwarding-table contents.
    if d['kind']=='leo':
        dynamic=c.STATE/'dynamic_state_100ms_for_200s'
        record['dynamic_input_sha256']={p.name:c.sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()}
    manifest=run/'manifest.json';c.write(manifest,record);start=time.monotonic()
    with (run/'console.txt').open('w') as f:
        try:
            r=subprocess.run(argv,cwd=ns3,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=a.timeout)
            record.update(status='success' if r.returncode==0 else 'failed',exit_code=r.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record.update(wall_seconds=time.monotonic()-start,runtime_unchanged=before==c.runtime(),
        source_unchanged=c.git('diff','--binary','HEAD')==diff,
        launch_source_files_unchanged=sources==c.source_files())
    record['input_files_unchanged']=all(c.sha(run/n)==v['sha256'] for n,v in record['input_files'].items())
    record['state_inputs_unchanged']=record['state_static_sha256']=={
        p.name:c.sha(p) for p in sorted(c.STATE.iterdir()) if p.is_file()}
    if d['kind']=='leo':
        record['state_inputs_unchanged'] &= record['dynamic_input_sha256']=={
            p.name:c.sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()}
    if not all(record[k] for k in ('runtime_unchanged','source_unchanged','launch_source_files_unchanged',
                                  'input_files_unchanged','state_inputs_unchanged')):
        record['audit_exclude']='Source/runtime/runner/input changed during simulation'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=c.sha(p))
        for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    c.write(manifest,record)
    print(json.dumps({k:record[k] for k in ('case','status','wall_seconds','runtime_unchanged','source_unchanged')}),flush=True)
    assert record['status']=='success' and not record.get('audit_exclude'), 'Preserved failed/excluded run; batch stopped'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',nargs='+',choices=c.CASES);p.add_argument('--root',type=Path,default=Path('/tmp/orbit-elt'))
    p.add_argument('--ready',type=Path,default=Path('/tmp/orbit-elt-ready.json'))
    p.add_argument('--checkpoint',required=True);p.add_argument('--timeout',type=int,default=600)
    a=p.parse_args();names=a.cases or list(c.CASES);assert len(names)==len(set(names))
    for name in names:execute(name,a)
