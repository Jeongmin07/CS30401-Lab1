"""Recreate recorded configurations, without overwriting local runs."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('cases', nargs='*')
parser.add_argument('--workers', type=int, default=3, choices=range(1, 4))
parser.add_argument('--patch', default=str(Path(__file__).with_name('ns3.patch')))
args = parser.parse_args()
root = Path(__file__).resolve().parent
case_dirs = sorted((root/'evidence'/'cases').iterdir())
if args.cases:
    requested = set(args.cases)
    case_dirs = [p for p in case_dirs if p.name in requested]
    if {p.name for p in case_dirs} != requested:
        parser.error('Unknown case name')

def replay(case_dir):
    manifest = json.loads((case_dir/'case.json').read_text())
    parameters = manifest['parameters']
    command = [sys.executable, str(root/'run_study.py'), case_dir.name, '--patch', args.patch]
    for key, value in parameters.items():
        if key not in ('name', 'patch') and value is not None:
            command += ['--'+key.replace('_', '-'), str(value)]
    result = subprocess.run(command, text=True, capture_output=True)
    record = {'case': case_dir.name, 'command': command, 'exit_code': result.returncode,
              'stdout': result.stdout, 'stderr': result.stderr}
    print(json.dumps(record), flush=True)
    return record

start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
    records = list(pool.map(replay, case_dirs))
(root/'replay_execution.json').write_text(json.dumps({'cases': records, 'elapsed_s': round(time.monotonic()-start,3)}, indent=2)+'\n')
raise SystemExit(any(row['exit_code'] for row in records))
