"""Run an explicitly versioned independent case inside the course container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('name')
p.add_argument('--kind', choices=['leo', 'micro'], default='leo')
p.add_argument('--cc', default='TcpCubic')
p.add_argument('--rate', type=float, default=10)
p.add_argument('--queue', type=int, default=100)
p.add_argument('--duration', type=int, default=200)
p.add_argument('--parameters', default='')
p.add_argument('--trace', type=int, choices=[0, 1], default=1)
p.add_argument('--before-ms', type=float, default=50)
p.add_argument('--after-ms', type=float, default=45)
p.add_argument('--event-s', type=float, default=10)
p.add_argument('--loss-s', type=float, default=-1)
p.add_argument('--initial-ssthresh-pkts', type=int, default=900)
p.add_argument('--max-bytes', type=int, default=100000000000)
p.add_argument('--state', default='/home/ubuntu/lab/data/seoul_london/state')
p.add_argument('--patch', default=str(Path(__file__).resolve().with_name('ns3.patch')))
a = p.parse_args()
if not a.name.replace('-', '').replace('_', '').isalnum():
    raise SystemExit('Use an alphanumeric case name with hyphens/underscores.')
run = Path('/tmp/cs30401-study') / a.name
if run.exists():
    raise SystemExit(f'Refusing to overwrite existing case {run}')
run.mkdir(parents=True)
(run/'logs_ns3').mkdir()
state = a.state
if a.kind == 'leo':
    subprocess.run(['bash', '/home/ubuntu/lab/scripts/make_run.sh', str(run), state,
                    a.cc, str(a.rate), str(a.queue), str(a.duration), '1584', '1585'], check=True)
    schedule = run/'schedule.csv'
    schedule.write_text(f'0,1584,1585,100000000000,0,{a.parameters},\n')
    binary = '/home/ubuntu/ns-3.48/build/scratch/main_satnet/ns3.48-main_satnet'
    command = [binary, '--run_dir='+str(run)]
else:
    binary = '/home/ubuntu/ns-3.48/build/scratch/study_micro/ns3.48-study_micro'
    command = [binary, '--run_dir='+str(run),
               '--cc='+a.cc, '--duration='+str(a.duration), '--rate='+str(a.rate),
               '--queue_pkts='+str(a.queue), '--before_ms='+str(a.before_ms),
               '--after_ms='+str(a.after_ms), '--event_s='+str(a.event_s),
               '--loss_s='+str(a.loss_s), '--initial_ssthresh_pkts='+str(a.initial_ssthresh_pkts)]
    # The v4 benchmark has the same default but does not expose this v5 option.
    if a.max_bytes != 100000000000:
        command.append('--max_bytes='+str(a.max_bytes))
    if a.parameters:
        command.append('--parameters='+a.parameters)
env = dict(os.environ, CS30401_STUDY_TRACE=str(a.trace),
           CS30401_STUDY_TRACE_DIR=str(run/'logs_ns3'))
digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest = {'case': a.name, 'parameters': vars(a), 'command': command,
            'trace_environment': {k: env[k] for k in ('CS30401_STUDY_TRACE', 'CS30401_STUDY_TRACE_DIR')},
            'official_image': 'ghcr.io/yeonjong21/cs30401-lab1:2026f-v1',
            'official_image_digest': 'sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4',
            'patch_sha256': digest(a.patch),
            'binary_sha256': digest(binary), 'state': state if a.kind=='leo' else None,
            'start_time_unix': time.time(), 'status': 'running'}
for file in ('config_ns3.properties', 'schedule.csv'):
    if (run/file).exists(): manifest[file+'_sha256'] = digest(run/file)
(run/'case.json').write_text(json.dumps(manifest, indent=2)+'\n')
start = time.monotonic()
with (run/'console.log').open('w') as log:
    result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
manifest.update(exit_code=result.returncode, wall_time_s=round(time.monotonic()-start, 3),
                status='complete' if result.returncode == 0 else 'failed')
(run/'case.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({k: manifest[k] for k in ('case','status','exit_code','wall_time_s','patch_sha256')}, indent=2), flush=True)
if result.returncode:
    print((run/'console.log').read_text()[-5000:])
raise SystemExit(result.returncode)
