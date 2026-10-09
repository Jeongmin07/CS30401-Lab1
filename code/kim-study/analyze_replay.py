"""Analyze each successful replay using its recorded event definition."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
record = json.loads((root/'replay_execution.json').read_text())
assert all(row['exit_code'] == 0 for row in record['cases'])

def analyze(row):
    name = row['case']
    run = Path('/tmp/cs30401-study')/name
    command = [sys.executable, '-B', str(root/'analyze_study.py'), str(run),
               '--include-bins', '--output', str(run/'study_analysis.json')]
    if name.startswith('micro-'):
        command += ['--events', '0.15' if name.startswith('micro-tail-') else '10']
    else:
        command += ['--path-truth', str(root/('path_truth_delay26.csv' if name=='leo-delay26-base-v5' else 'path_truth_200s.csv'))]
        if name=='leo-delay26-base-v5': command += ['--events','26.2']
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    print(name, flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(analyze, record['cases']))
