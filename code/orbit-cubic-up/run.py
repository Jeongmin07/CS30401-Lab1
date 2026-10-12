"""Declared passive CUBIC baseline runs; no active scale-up policy is implemented."""
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
CASES={'cubic10-observed200':dict(rate=10,observe=True),
       'cubic100-observed200':dict(rate=100,observe=True),
       'cubic10-off200':dict(rate=10,observe=False)}
EVENTS=[26.2,75.0,121.6,187.4]

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def git(*args,cwd=REPO):return subprocess.check_output(['git','-c',f'safe.directory={cwd}',*args],cwd=cwd)
def identities():
    binary=NS3/'build/scratch/main_satnet/ns3.48-main_satnet'
    return {str(p.relative_to(NS3/'build')):sha(p) for p in [binary,*sorted((NS3/'build/lib').glob('*.so'))]}

def execute(name,root,timeout):
    d=CASES[name];run=root/name;run.mkdir(parents=True,exist_ok=False)
    subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),'TcpCubic',str(d['rate']),'100','200','1584','1585'],check=True,capture_output=True)
    schedule=run/'schedule.csv';schedule.write_text('0,1584,1585,100000000000,0,,\n',newline='\n')
    config=run/'config_ns3.properties'
    if 'tcp_enable_pacing=false' not in config.read_text():raise ValueError('Expected CUBIC pacing off')
    patch=HERE/'ns3.patch';diff=git('diff','--binary','HEAD',cwd=NS3)
    if diff!=patch.read_bytes():raise ValueError('Installed source differs from complete patch')
    binary=NS3/'build/scratch/main_satnet/ns3.48-main_satnet'
    build=jread(HERE/'build-receipt.json')
    before_runtime=identities()
    if before_runtime!=build['runtime_files'] or build['patch_sha256']!=sha(patch):raise ValueError('Current runtime does not match completed build')
    env=dict(os.environ,LD_LIBRARY_PATH=str(NS3/'build/lib'),CS30401_STUDY_TRACE='1',
             CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),
             CS30401_ORBIT_WINDOW_TRACE=str(int(d['observe'])),
             CS30401_ORBIT_QUEUE_TRACE=str(int(d['observe'])),
             CS30401_ORBIT_QUEUE_TRACE_DIR=str(run/'logs_ns3'),
             CS30401_ORBIT_SERVICE_TRACE=str(int(d['observe'])))
    command=[str(binary),f'--run_dir={run}']
    record=dict(case=name,definition=dict(kind='leo',cc='TcpCubic',rate=d['rate'],queue=100,duration=200,max_bytes=100000000000,start_s=0,observe=d['observe'],scale_up=False),status='running',
      repo_commit=git('rev-parse','HEAD').decode().strip(),repo_dirty=bool(git('status','--porcelain')),
      runner_sha256=sha(__file__),patch_sha256=sha(patch),installed_diff_sha256=hashlib.sha256(diff).hexdigest(),
      source_files={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file()},
      ns3_head=git('rev-parse','HEAD',cwd=NS3).decode().strip(),image_ref=IMAGE,build_receipt_sha256=sha(HERE/'build-receipt.json'),runtime_files=before_runtime,
      command=command,environment={k:env[k] for k in ['LD_LIBRARY_PATH','CS30401_STUDY_TRACE','CS30401_STUDY_TRACE_DIR','CS30401_ORBIT_WINDOW_TRACE','CS30401_ORBIT_QUEUE_TRACE','CS30401_ORBIT_QUEUE_TRACE_DIR','CS30401_ORBIT_SERVICE_TRACE']},
      config_sha256=sha(config),schedule_sha256=sha(schedule),path_truth_sha256=sha(REPO/'code/kim-study/path_truth_200s.csv'),
      state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
      dynamic_input_sha256={p.name:sha(p) for p in sorted((STATE/'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()},
      declared_windows_s={'whole':[0,200],**{f'{t}:{kind}':window for t in EVENTS for kind,window in [('pre',[t-.5,t]),('post',[t,t+.5]),('legacy',[t-.5,t+2])] }},
      timeout_s=timeout)
    manifest=run/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    start=time.monotonic()
    with (run/'console.txt').open('w') as f:
        try:
            done=subprocess.run(command,cwd=NS3,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            record.update(status='success' if done.returncode==0 else 'failed',exit_code=done.returncode)
        except subprocess.TimeoutExpired:record.update(status='timeout',exit_code=None)
    record['wall_seconds']=time.monotonic()-start
    record['runtime_unchanged_after_run']=identities()==before_runtime
    if not record['runtime_unchanged_after_run']:record['status']='invalid_runtime_changed'
    record['output_files']={str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(run.rglob('*')) if p.is_file() and p!=manifest}
    manifest.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({k:record[k] for k in ['case','status','wall_seconds']}),flush=True)
    if record['status']!='success':raise SystemExit('Incomplete attempt preserved; stop: '+str(run))

def jread(p):return json.loads(Path(p).read_text())
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-cubic-up'));p.add_argument('--timeout',type=int,default=240)
    a=p.parse_args()
    for case in a.cases:execute(case,a.root,a.timeout)
if __name__=='__main__':main()
