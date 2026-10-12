"""Declared finite LEO HyStart cases; launch only in the dedicated official container."""
import argparse
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
CASES={
    'near-on':dict(start_s='121.2',hystart=True,observe=True),
    'near-off':dict(start_s='121.2',hystart=False,observe=True),
    'near-on-unobserved':dict(start_s='121.2',hystart=True,observe=False),
    'stable-on':dict(start_s='119.2',hystart=True,observe=True),
    'stable-off':dict(start_s='119.2',hystart=False,observe=True),
    'near-forecast':dict(start_s='121.2',hystart=True,observe=True,forecast=True),
}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()


def git(*args,cwd=REPO):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}',*args],cwd=cwd).strip()


def execute(name,root,timeout,patch):
    case=CASES[name]
    run=root/name
    run.mkdir(parents=True,exist_ok=False)
    subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),
                    'TcpCubic','100','1000','140','1584','1585'],check=True,capture_output=True)
    start_ns=int(case['start_s'].replace('.',''))*100000000
    (run/'schedule.csv').write_text(f'0,1584,1585,8388608,{start_ns},,\n',newline='\n')
    binary=NS3/'build/scratch/main_satnet/ns3.48-main_satnet'
    command=[str(binary),f'--run_dir={run}',f"--hystart={int(case['hystart'])}"]
    if case.get('forecast'):
        command.append('--hystart_forecast_windows=121600000000:121781136000')
    source=git('diff','--binary','HEAD',cwd=NS3)
    if source!=patch.read_bytes().strip():
        raise ValueError('Installed source differs from selected combined patch')
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),
             CS30401_STUDY_TRACE='1',CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),
             CS30401_HYSTART_TRACE=str(int(case['observe'])),
             CS30401_ORBIT_QUEUE_TRACE=str(int(case['observe'])),
             CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
             CS30401_HYSTART_EXPECTED=str(int(case['hystart'])))
    env['CS30401_HYSTART_FORECAST_EXPECTED']=('121600000000:121781136000' if case.get('forecast') else '')
    dynamic=STATE/'dynamic_state_100ms_for_200s'
    manifest=dict(case=name,definition=case,command=command,status='running',
        flow=dict(bytes=8388608,start_ns=start_ns,duration_ns=140000000000,
                  from_node=1584,to_node=1585,rate_mbps=100,queue_packets=1000),
        repo_commit=git('rev-parse','HEAD').decode(),repo_dirty=bool(git('status','--porcelain')),
        runner_sha256=sha(Path(__file__)),patch_sha256=sha(patch),patch_path=str(patch),
        ns3_head=git('rev-parse','HEAD',cwd=NS3).decode(),image_ref=IMAGE,
        runtime_files={str(p.relative_to(NS3/'build')):sha(p) for p in
                       [binary,*sorted((NS3/'build/lib').glob('*.so'))]},
        input_files={p.name:sha(p) for p in [run/'config_ns3.properties',run/'schedule.csv']},
        state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
        dynamic_input_sha256={p.name:sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()},
        path_truth_sha256=sha(REPO/'code/kim-study/path_truth_200s.csv'),
        environment={k:env[k] for k in ['LD_LIBRARY_PATH','CS30401_STUDY_TRACE',
            'CS30401_STUDY_TRACE_DIR','CS30401_HYSTART_TRACE','CS30401_HYSTART_EXPECTED',
            'CS30401_ORBIT_QUEUE_TRACE','CS30401_ORBIT_QUEUE_TRACE_DIR',
            'CS30401_HYSTART_FORECAST_EXPECTED']},
        timeout_s=timeout)
    target=run/'manifest.json'
    target.write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
    before=time.monotonic()
    with (run/'console.txt').open('w') as stream:
        try:
            outcome=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
            manifest.update(status='success' if outcome.returncode==0 else 'failed',exit_code=outcome.returncode)
        except subprocess.TimeoutExpired:
            manifest.update(status='timeout',exit_code=None)
    manifest['wall_seconds']=time.monotonic()-before
    manifest['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p))
         for p in sorted(run.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    target.write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
    print(json.dumps({k:manifest[k] for k in ['case','status','wall_seconds']}),flush=True)
    if manifest['status']!='success':
        raise SystemExit('Incomplete case preserved; stop and inspect '+str(run))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-hystart'))
    p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--patch',type=Path,default=HERE/'observed.patch')
    a=p.parse_args()
    for name in a.cases: execute(name,a.root,a.timeout,a.patch)


if __name__=='__main__': main()
