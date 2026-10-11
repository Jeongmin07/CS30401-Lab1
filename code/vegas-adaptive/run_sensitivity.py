"""Declared 10-case renewal timing/capacity follow-up; preserve all attempts."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--image-digest', required=True)
p.add_argument('--root', type=Path, default=Path('/tmp/vegas-sensitivity'))
p.add_argument('--out', type=Path, required=True)
p.add_argument('--source-manifest', type=Path)
a = p.parse_args()
assert not a.out.exists(), 'Refuse existing matrix record'
here = Path(__file__).resolve().parent
tasks = []
for family in ('leo', 'fixed-comp', 'rate50'):
    for rounds in ((0, 10, 20, 40) if family == 'rate50' else (10, 20, 40)):
        name = f's1-{family}-' + (f'r{rounds}' if rounds else 'base')
        cmd = [sys.executable, str(here / 'run_case.py'), name,
               '--image-digest', a.image_digest, '--root', str(a.root)]
        cmd += (['--after-ms', '45', '--competitor'] if family == 'fixed-comp'
                else ['--kind', 'leo'])
        if a.source_manifest:
            cmd += ['--source-manifest', str(a.source_manifest)]
        if family == 'rate50':
            cmd += ['--rate', '50']
        if rounds:
            cmd += ['--renewal', '--rounds', str(rounds)]
        analysis = [sys.executable, str(here / 'analyze_vegas.py'), str(a.root / name),
                    '--out', str(a.root / 'analysis' / name)]
        analysis += (['--window', 'common:80:200'] if family == 'fixed-comp' else
                     ['--event-s', '121.6', '--event-s', '187.4'])
        tasks.append(dict(case=name, family=family, rounds=rounds,
                          command=cmd, analysis_command=analysis))
record = dict(tasks=tasks, results=[], workers=2, status='running', start_unix=time.time())
a.out.parent.mkdir(parents=True, exist_ok=True)
def save():
    a.out.write_text(json.dumps(record, indent=2) + '\n')
def run(task):
    start = time.monotonic()
    sim = subprocess.run(task['command'], capture_output=True, text=True)
    result = dict(task, exit_code=sim.returncode, simulation_output=sim.stdout+sim.stderr)
    print(result['simulation_output'], flush=True)
    if sim.returncode == 0:
        analysis = subprocess.run(task['analysis_command'], capture_output=True, text=True)
        result.update(analysis_exit_code=analysis.returncode,
                      analysis_output=analysis.stdout+analysis.stderr)
        print(result['analysis_output'], flush=True)
    result['wall_s'] = time.monotonic()-start
    return result
save()
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(run, task) for task in tasks]):
        record['results'].append(future.result())
        save()
record['status'] = ('complete' if all(r['exit_code'] == 0 and
                     r.get('analysis_exit_code') == 0 for r in record['results']) else 'failed')
record['end_unix'] = time.time()
save()
sys.exit(0 if record['status'] == 'complete' else 1)
