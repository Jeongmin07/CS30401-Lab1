"""The fixed 19 physical replays; three named aliases are never extra simulations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import common as c


def execute(name,args):
    entry=c.CASES[name];case=entry['definition'];profile=entry['profile']
    assert profile==args.profile
    ready=args.ready;diff,build=c.validate_build(profile,ready);before=c.runtime();sources=c.source_files()
    run=args.root/name;assert not run.exists(),'Refuse to overwrite an attempt';run.mkdir(parents=True);(run/'logs_ns3').mkdir()
    state=c.STATE;route_receipt=None
    if name==c.CF:
        natural=args.root/'leo10-selective';m=json.loads((natural/'manifest.json').read_text())
        assert m['status']=='success' and not m.get('audit_exclude') and m['runtime_files']==before
        assert m['runtime_unchanged'] and m['source_unchanged'] and m['launch_source_files_unchanged']
        state=Path('/tmp/lab1-final-route/state');receipt=Path('/tmp/lab1-final-route/input.json')
        assert not state.exists() and not receipt.exists()
        subprocess.run(['python3','-B',str(c.HERE/'code/orbit-queue/delay_route.py'),
            '--state',str(c.STATE),'--observed-logs',str(natural/'logs_ns3'),
            '--out-state',str(state),'--receipt',str(receipt)],check=True,capture_output=True)
        route_receipt=json.loads(receipt.read_text());assert all(route_receipt['checks'].values())
    additional,hints=c.tail.parameters(case)
    if case['kind']=='leo':
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(state),'TcpCubic','10','100','200','1584','1585'],check=True,capture_output=True)
        (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n',newline='\n')
        config=run/'config_ns3.properties';text=config.read_text();assert text.count('tcp_enable_pacing=false')==1
        enabled=case.get('pacing',False);config.write_text(text.replace('tcp_enable_pacing=false','tcp_enable_pacing='+str(enabled).lower()),newline='\n')
        argv=[str(c.NS3/'build/scratch/main_satnet/ns3.48-main_satnet'),f'--run_dir={run}']
    else:
        argv=[str(c.NS3/'build/scratch/study_micro/ns3.48-study_micro'),f'--run_dir={run}',
            '--cc=TcpCubic','--duration=4','--rate=100','--queue_pkts=2000','--before_ms=50',
            '--after_ms=50','--event_s=2','--initial_ssthresh_pkts=900',f"--max_bytes={case.get('bytes',27600)}",'--loss_seq=1',
            '--enable_pacing='+str(case.get('pacing',False)).lower()]
        if additional:argv.append('--parameters='+additional)
    settings=dict(case,tail=bool(case.get('tail')),pacing=bool(case.get('pacing')))
    if profile=='pace':argv+=c.pace.native_cli(settings)
    else:argv += ['--ns3::TcpSocketBase::OrbitTailAdmission=true','--ns3::TcpSocketState::EnablePacing=false']
    env=dict(os.environ,LD_LIBRARY_PATH=str(c.NS3/'build/lib'),CS30401_STUDY_TRACE='1',
        CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),CS30401_ORBIT_ACTUAL_DROP='1' if case.get('actual_drop') else '0',
        CS30401_ORBIT_QUEUE_TRACE='1',CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
        CS30401_ORBIT_SERVICE_TRACE='1',CS30401_QUEUE_FLOW_TRACE='1')
    if profile=='pace':env.update(CS30401_QUEUE_PACING_RATE_TRACE='1',
        CS30401_QUEUE_PACING_FIRST_LOSS='1' if case.get('first_loss') else '0')
    else:env.update(CS30401_BACKPRESSURE_MODE=entry['queue_mode'],CS30401_BACKPRESSURE_DROP_FIRST_SEQ1='0')
    git=c.identity();dynamic=state/'dynamic_state_100ms_for_200s'
    dependencies={str(p.relative_to(c.HERE)):c.sha(p) for p in (c.HERE/'code').rglob('*') if p.is_file()}
    native=dict(enabled=settings['pacing'],max_bps=c.pace.maximum(settings),ss_ratio=200,ca_ratio=120,
                pace_initial_window=False,payload_bytes=1380,assumed_serialized_data_bytes=1434)
    record=dict(case=name,status='running',profile=profile,definition=case,tail_admission=settings['tail'],
        command=argv,cwd=str(c.NS3),declared_source_checkpoint=args.checkpoint,source_checkpoint=args.checkpoint,
        launch_commit=git['commit'],repo_commit=git['commit'],repo_dirty=git['dirty'],package_git=git,
        source_files=sources,dependency_files=dependencies,dependencies=dependencies,
        runner_sha256=c.sha(Path(__file__)),patch_sha256=c.PATCHES[profile],installed_diff_sha256=c.PATCHES[profile],
        runtime_files=before,build_ready_sha256=c.sha(ready),ns3_head=c.BASE,image_ref=c.IMAGE,declared_image_digest=c.IMAGE,
        hints=hints,additional_parameters=additional,forecast_source=str(c.tail.FORWARD),forecast_source_sha256=c.sha(c.tail.FORWARD),
        state_static_sha256={p.name:c.sha(p) for p in sorted(state.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:c.sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()} if case['kind']=='leo' else None,
        input_files={p.name:dict(bytes=p.stat().st_size,sha256=c.sha(p)) for p in [run/'config_ns3.properties',run/'schedule.csv'] if p.exists()},
        expected_finite_bytes=case.get('bytes',27600) if case['kind']=='micro' else None,
        native_pacing=native,observer_only=not settings['pacing'] and not case.get('first_loss',False) and not case.get('actual_drop',False) and name!=c.CF,
        policy_changed=settings['pacing'],forwarding_input_changed=name==c.CF,routing_counterfactual=route_receipt,
        actual_drop_rule=('Existing frozen old-flight rule: first original received atT26.2, TX in[T-48847704ns,T)' if case.get('actual_drop') else
            'First original directed flow0 sequence1 payload1380 at receiver node1585, once' if case.get('first_loss') else None),
        timeout_s=args.timeout,environment={k:v for k,v in env.items() if k.startswith('CS30401_') or k=='LD_LIBRARY_PATH'},
        declared_event_windows_s=[[25.7,28.2],[74.5,77.0]] if case['kind']=='leo' else [[1.5,4.0]],
        aliases=[alias for alias,target in c.ALIASES.items() if target==name],
        interpretation='Frozen algorithms/configuration; portable dispatcher/provenance only. Counterfactual keeps original hints despite delayed actual routing.' if name==c.CF else 'Fresh replay of a fixed frozen condition.')
    if profile=='bp':record.update(queue_mode=entry['queue_mode'],source_device_max_packets=entry['device_max'],
        source_qdisc_max_packets=entry['qdisc_max'],nominal_queue_budget_packets=100,
        physical_drop_first_original_seq1=False,tail_base_patch_sha256='5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29',
        prospective_gates=dict(min_goodput_ratio=.995,max_post_queue_ratio=.5,max_post_served_wait_ratio=.5,
            max_focus_unique_tx_losses=5,whole_queue_wait_unique_losses_not_worse=True))
    manifest=run/'manifest.json';c.write(manifest,record);start=time.monotonic()
    with (run/'console.txt').open('w') as log:
        try:
            result=subprocess.run(argv,cwd=c.NS3,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record.update(wall_seconds=time.monotonic()-start,runtime_unchanged=c.runtime()==before,
        source_unchanged=c.git('diff','--binary','HEAD')==diff,launch_source_files_unchanged=c.source_files()==sources)
    if not record['runtime_unchanged'] or not record['source_unchanged'] or not record['launch_source_files_unchanged']:
        record['audit_exclude']='Source/runtime/package helper or input changed'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=c.sha(p)) for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    c.write(manifest,record);print(json.dumps({k:record[k] for k in ['case','status','wall_seconds','runtime_unchanged','source_unchanged']}),flush=True)
    if record['status']!='success' or record.get('audit_exclude'):raise SystemExit('Incomplete/excluded attempt preserved; batch stopped')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=c.PATCHES,required=True)
    p.add_argument('--cases',nargs='+',choices=c.CASES);p.add_argument('--root',type=Path)
    p.add_argument('--ready',required=True,type=Path);p.add_argument('--checkpoint',required=True)
    p.add_argument('--timeout',type=int,default=600);a=p.parse_args();a.root=a.root or c.ROOTS[a.profile]
    names=a.cases or [n for n,d in c.CASES.items() if d['profile']==a.profile]
    assert len(names)==len(set(names)) and all(c.CASES[n]['profile']==a.profile for n in names)
    for name in names:execute(name,a)
