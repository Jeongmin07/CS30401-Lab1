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
    source = json.loads((root/'evidence'/'cases'/name/'summary.json').read_text())
    manifest = json.loads((run/'case.json').read_text())
    if manifest['parameters']['kind'] == 'leo':
        command += ['--path-truth', str(root/('path_truth_delay26.csv' if name=='leo-delay26-base-v5' else 'path_truth_200s.csv'))]
    explicit = [str(window['time_s']) for window in source['path_event_windows']
                if window.get('marker_source') == 'explicit']
    if explicit: command += ['--events']+explicit
    parameters = source['analysis_parameters']
    for option, key in (('--bin-s','bin_s'),('--before-s','event_before_s'),
                        ('--after-s','event_after_s'),('--max-cases','maximum_case_samples'),
                        ('--max-evidence-rows','maximum_evidence_rows_per_sample'),
                        ('--tx-retention-s','tx_identity_retention_s')):
        command += [option,str(parameters[key])]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    print(name, flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(analyze, record['cases']))
