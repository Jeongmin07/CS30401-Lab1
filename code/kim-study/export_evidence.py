"""Publish compact summaries and input hashes; never copy raw traces or state."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs-root', type=Path, default=Path('/tmp/cs30401-study'))
parser.add_argument('--execution-record', type=Path, default=root/'matrix_execution.json')
parser.add_argument('--out', type=Path, default=root/'evidence-export')
args = parser.parse_args()
runs = args.runs_root
evidence = args.out
if evidence.exists(): raise SystemExit(f'Refusing to overwrite exported evidence {evidence}')
evidence.mkdir(exist_ok=True)
matrix = json.loads(args.execution_record.read_text())
assert all(row['exit_code'] == 0 for row in matrix['cases'])
names = [r['case'] for r in matrix['cases']]
names = list(dict.fromkeys(names + ['micro-tail-base-v5', 'micro-tail-guard20-v5', 'leo-delay26-base-v5']))

def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def selected_samples(rows):
    chosen, counts = [], {}
    for row in rows:
        group = str(row.get('classification', row.get('drop_layer', 'other')))
        critical = row.get('seq') == 29734861 or 'PhyRxDrop' in json.dumps(row)
        if counts.get(group, 0) < 3 or critical:
            chosen.append(row)
            counts[group] = counts.get(group, 0)+1
    return chosen

table = []
for name in names:
    run = runs/name
    target = evidence/'cases'/name
    target.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((run/'case.json').read_text())
    assert manifest['status'] == 'complete' and manifest['exit_code'] == 0
    for filename in ('case.json', 'config_ns3.properties', 'schedule.csv'):
        if (run/filename).is_file(): shutil.copy2(run/filename, target/filename)
    data = json.loads((run/'study_analysis.json').read_text())
    full_sha = digest(run/'study_analysis.json')
    for flow in data['flows'].values():
        bins = flow.pop('receiver_application_bins', [])
        flow['receiver_application_bins_omitted_from_export'] = len(bins)
        for key in ('gap_case_samples', 'drop_case_samples'):
            rows = flow.get(key, [])
            flow[key] = selected_samples(rows)
            flow[key+'_additional_export_omissions'] = len(rows)-len(flow[key])
        periods = flow.get('recovery_periods', [])
        flow['recovery_periods'] = periods[:5]
        flow['recovery_periods_additional_export_omissions'] = len(periods)-len(flow['recovery_periods'])
    for window in data.get('path_event_windows', []):
        window.pop('gap_case_samples', None)
    data['publication_export'] = {
        'full_analysis_sha256': full_sha,
        'omissions': '0.1s bins; bounded case samples; recovery periods after first five; per-window gap samples. Aggregate metrics retained.',
        'raw_inputs': [{'kind': item['kind'], 'path': item['path'],
                        'sha256': digest(item['path']), 'bytes': Path(item['path']).stat().st_size}
                       for item in data['inputs']],
        'legacy_inputs': [{'kind':'legacy_'+kind, 'path':str(run/'logs_ns3'/f'tcp_flow_0_{kind}.csv'),
                           'sha256':digest(run/'logs_ns3'/f'tcp_flow_0_{kind}.csv'),
                           'bytes':(run/'logs_ns3'/f'tcp_flow_0_{kind}.csv').stat().st_size}
                          for kind in ('cwnd','rtt','progress')],
        'raw_trace_location': str(run/'logs_ns3'),
        'raw_traces_published': False}
    (target/'summary.json').write_text(json.dumps(data, indent=2)+'\n')
    f = data['flows']['0']
    table.append({'case':name, 'duration_s':data['duration_s'],
                  'receiver_goodput_mbps':f['receiver_application_goodput_mbps'],
                  'distinct_tagged_drops':f['distinct_tagged_transmissions_dropped'],
                  'retransmissions':f['counts'].get('official_retransmission_rows',0),
                  'patch_sha256':manifest['patch_sha256'], 'wall_time_s':manifest['wall_time_s']})
    print(name, flush=True)
with (evidence/'results.csv').open('w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=list(table[0]))
    writer.writeheader()
    writer.writerows(table)
(evidence/'publication_manifest.json').write_text(json.dumps({
    'distinct_configurations':len(table), 'independent_random_seed_repetitions':False,
    'author':'kim-seongchan with GPT assistance', 'uses_teammate_results':False,
    'execution_record':str(args.execution_record), 'execution_record_sha256':digest(args.execution_record),
    'execution_elapsed_s':matrix.get('elapsed_s'), 'execution_case_count':len(matrix['cases']), 'cases':names,
    'excluded':'raw traces, state, compiled ns-3 tree, earlier confounded prototypes'}, indent=2)+'\n')
