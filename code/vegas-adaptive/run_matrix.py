"""Launch declared matched cases and retain every exit result, no retries."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--families', nargs='+', choices=['leo', 'fixed-comp', 'step', 'fixed', 'step-comp'], default=['leo', 'fixed-comp'])
p.add_argument('--prefix', default='a1')
p.add_argument('--image-digest', required=True)
p.add_argument('--root', default='/tmp/cs30401-vegas')
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
assert not a.out.exists(), 'Refuse an existing execution record'
families = {'leo': ['--kind', 'leo'], 'fixed-comp': ['--after-ms', '45', '--competitor'],
            'step': [], 'fixed': ['--after-ms', '45'], 'step-comp': ['--competitor']}
tasks = []
for family in a.families:
    for adaptive in (False, True):
        name = f'{a.prefix}-{family}-' + ('adaptive' if adaptive else 'base')
        cmd = [sys.executable, str(Path(__file__).with_name('run_case.py')), name,
               '--image-digest', a.image_digest, '--root', a.root, *families[family]]
        if adaptive: cmd.append('--adaptive')
        tasks.append({'case': name, 'family': family, 'adaptive': adaptive, 'command': cmd})
record = {'declared_tasks_before_launch': tasks, 'results': [], 'start_unix': time.time(), 'status': 'running', 'workers': 2}
a.out.parent.mkdir(parents=True, exist_ok=True)
def save(): a.out.write_text(json.dumps(record, indent=2) + '\n')
def run(task):
    start = time.monotonic()
    result = subprocess.run(task['command'], capture_output=True, text=True)
    return {**task, 'exit_code': result.returncode, 'wall_s': time.monotonic()-start,
            'output': result.stdout+result.stderr}
save()
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(run, task) for task in tasks]):
        result = future.result()
        record['results'].append(result)
        save()
        print(result['output'], flush=True)
record['status'] = 'complete' if all(r['exit_code'] == 0 for r in record['results']) else 'failed'
record['end_unix'] = time.time()
save()
sys.exit(0 if record['status'] == 'complete' else 1)
