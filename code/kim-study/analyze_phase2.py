"""Analyze completed v6 controls, including finite-flow completion time."""
import concurrent.futures
import csv
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
execution = json.loads((root/'phase2_execution.json').read_text())
assert all(r['exit_code']==0 for r in execution['cases'])

def analyze(row):
    name = row['case']
    run = Path('/tmp/cs30401-study')/name
    command = [sys.executable,'-B',str(root/'analyze_study.py'),str(run),'--include-bins',
               '--output',str(run/'study_analysis.json')]
    if row['question']['family'] in ('bulk_leo','notification_error'):
        command += ['--path-truth',str(root/'path_truth_200s.csv')]
    else:
        command += ['--events',str(row['question'].get('event_s',0.15))]
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
    data = json.loads((run/'study_analysis.json').read_text())
    manifest = json.loads((run/'case.json').read_text())
    assert manifest['status']=='complete' and manifest['exit_code']==0
    flow = data['flows']['0']
    completion = flow['last_receiver_application_delivery_time_s']
    events = list(csv.DictReader((run/'logs_ns3'/'tcp_flow_0_study_events.csv').open()))
    bypass = any(r['event']=='SHORT_FLOW_GUARD_BYPASS' for r in events)
    value = {'case':name,**row['question'],'completed_application_bytes':None,
             'completion_time_s':completion-manifest['parameters'].get('flow_start_s',0) if completion is not None else None,
             'receiver_goodput_mbps':flow['receiver_application_goodput_mbps'],
             'distinct_tagged_drops':flow['distinct_tagged_transmissions_dropped'],
             'retransmissions':flow['counts'].get('official_retransmission_rows',0),
             'recovery_entries':sum(r['event']=='CONG' and r['new_value']=='3' for r in events),
             'loss_state_entries':sum(r['event']=='CONG' and r['new_value']=='4' for r in events),
             'short_flow_bypass':bypass,'patch_sha256':manifest['patch_sha256']}
    apps = list((run/'logs_ns3').glob('study_app_rx_*.csv'))
    value['completed_application_bytes'] = sum(int(r['payload_bytes']) for file in apps for r in csv.DictReader(file.open()))
    finite = row['question']['family'].startswith('finite_')
    value['expected_finite_bytes'] = manifest['parameters']['max_bytes'] if finite else None
    value['transfer_complete'] = value['completed_application_bytes']==value['expected_finite_bytes'] if finite else None
    if not value['transfer_complete']: value['completion_time_s'] = None
    print(json.dumps(value),flush=True)
    return value

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(analyze,execution['cases']))
(root/'phase2_results.json').write_text(json.dumps({'cases':results},indent=2)+'\n')
keys = list(dict.fromkeys(k for row in results for k in row))
with (root/'phase2_results.csv').open('w',newline='') as file:
    writer = csv.DictWriter(file,fieldnames=keys); writer.writeheader(); writer.writerows(results)
