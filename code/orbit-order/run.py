"""Predeclared forecast new-data hold cases. Run inside the official image."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NS3 = Path('/home/ubuntu/ns-3.48')
STATE = Path('/home/ubuntu/lab/data/seoul_london/state')
TRUTH = REPO / 'code/kim-study/path_truth_200s.csv'
IMAGE = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CASES = {
    'leo10-base': dict(kind='leo', mode='base', rate=10, queue=100, duration=200),
    'leo10-hold1': dict(kind='leo', mode='hold', factor=1, rate=10, queue=100, duration=200),
    'leo10-hold2': dict(kind='leo', mode='hold', factor=2, rate=10, queue=100, duration=200),
    'loss-first-base': dict(kind='micro', mode='base', loss_seq=1),
    'loss-first-hold': dict(kind='micro', mode='hold', loss_seq=1),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git(*args, cwd=REPO):
    return subprocess.check_output(['git', '-c', f'safe.directory={cwd}', *args], cwd=cwd).strip()


def forecasts(duration, factor):
    rows = list(csv.DictReader(TRUTH.open(newline='')))
    hints = []
    for old, new in zip(rows, rows[1:]):
        old_rtt, new_rtt = Decimal(old['rtt_prop_ms']), Decimal(new['rtt_prop_ms'])
        t = Decimal(new['t_s'])
        if new['path_changed'] != '1' or new_rtt >= old_rtt or t >= duration:
            continue
        delta = (old_rtt-new_rtt)/2
        half = int(Decimal(factor)*delta*10**6)
        marker = int(t*10**9)
        if marker-half < 0 or marker+half >= duration*10**9:
            raise ValueError('Hold outside run')
        hints.append(dict(event_ns=marker,start_ns=marker-half,end_ns=marker+half,
                          one_way_delta_approx_ms=float(delta),factor=factor))
    return hints


def parameters(case):
    if case['mode']=='base': return '',[]
    hints = ([dict(start_ns=198366000,end_ns=211634000,
                   note='False hint overlapping real-loss feedback on stable micro path')]
             if case['kind']=='micro' else forecasts(case['duration'],case['factor']))
    windows = '|'.join(f"{h['start_ns']}:{h['end_ns']}" for h in hints)
    return 'orbit_hold_windows='+windows,hints


def execute(name, root, timeout):
    case = CASES[name]
    run = root / name
    run.mkdir(parents=True, exist_ok=False)
    (run/'logs_ns3').mkdir()
    additional, hints = parameters(case)
    if case['kind'] == 'leo':
        subprocess.run(['bash','/home/ubuntu/lab/scripts/make_run.sh',str(run),str(STATE),
                        'TcpCubic',str(case['rate']),str(case['queue']),str(case['duration']),
                        '1584','1585'],check=True,capture_output=True)
        (run/'schedule.csv').write_text(f'0,1584,1585,100000000000,0,{additional},\n')
        binary = NS3/'build/scratch/main_satnet/ns3.48-main_satnet'
        argv = [str(binary),f'--run_dir={run}']
    else:
        binary = NS3/'build/scratch/study_micro/ns3.48-study_micro'
        argv = [str(binary), f'--run_dir={run}', '--cc=TcpCubic','--duration=4',
                '--rate=100','--queue_pkts=2000','--before_ms=50','--after_ms=50',
                '--event_s=2','--initial_ssthresh_pkts=900',f"--max_bytes={case.get('max_bytes',27600)}",
                f"--loss_seq={case['loss_seq']}"]
        if additional:
            argv.append('--parameters='+additional)
    source = git('diff','--binary','HEAD',cwd=NS3)
    patch = HERE/'ns3.patch'
    # .strip() removes diff final newline, so compare stripped bytes consistently.
    if source != patch.read_bytes().strip():
        raise ValueError('Installed source diff does not match declared combined patch')
    env = dict(os.environ, CS30401_STUDY_TRACE='1',
               CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'),
               LD_LIBRARY_PATH=str(NS3/'build/lib'))
    dynamic = STATE/'dynamic_state_100ms_for_200s'
    record = dict(case=name, definition=case, command=argv, status='running',
                  repo_commit=git('rev-parse','HEAD').decode(),
                  repo_dirty=bool(git('status','--porcelain')),
                  runner_sha256=RUNNER_SHA256, patch_sha256=sha(patch),
                  installed_diff_sha256=hashlib.sha256(source+b'\n').hexdigest(),
                  ns3_head=git('rev-parse','HEAD',cwd=NS3).decode(), declared_image_digest=IMAGE,
                  runtime_files={str(p.relative_to(NS3/'build')):sha(p)
                                 for p in [binary,*sorted((NS3/'build/lib').glob('*.so'))]},
                  state_static_sha256={p.name:sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
                  dynamic_input_sha256={p.name:sha(p) for p in sorted(dynamic.iterdir()) if p.is_file()}
                  if case['kind']=='leo' else None,
                  forecast_source_sha256=sha(TRUTH), forecast_rule='hold [T-factor*D,T+factor*D), D=propagation RTT decrease/2',
                  hints=hints, additional_parameters=additional,
                  environment={k:env[k] for k in ('CS30401_STUDY_TRACE','CS30401_STUDY_TRACE_DIR','LD_LIBRARY_PATH')},
                  declared_event_windows_s=([w for w in [[25.7,28.2],[74.5,77.0]]
                                            if w[1] <= case['duration']]
                                           if case['kind']=='leo' else [[1.5,4.0]]),
                  timeout_s=timeout, expected_finite_bytes=case.get('max_bytes',27600)
                  if case['kind']=='micro' else None)
    (run/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    start = time.monotonic()
    with (run/'console.txt').open('w') as log:
        try:
            result = subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            record.update(status='success' if result.returncode==0 else 'failed',exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            record.update(status='timeout',exit_code=None)
    record['wall_seconds'] = time.monotonic()-start
    record['output_files'] = {str(p.relative_to(run)):dict(bytes=p.stat().st_size,sha256=sha(p))
                             for p in sorted(run.rglob('*')) if p.is_file() and p.name!='manifest.json'
                             and p.suffix in ('.csv','.txt','.properties')}
    (run/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(case=name,status=record['status'],wall_seconds=record['wall_seconds'])),flush=True)
    if record['status']!='success':
        raise SystemExit(f"Incomplete case {name}; batch stopped")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases',nargs='+',choices=CASES)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-order'))
    p.add_argument('--timeout',type=int,default=240)
    a=p.parse_args()
    for name in a.cases:
        execute(name,a.root,a.timeout)


if __name__=='__main__':
    main()
