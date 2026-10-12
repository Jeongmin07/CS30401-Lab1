"""Audit matched new-data holds and export their measured differences.

Uses summarize.py exports plus original traces; no simulations or policy changes.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def receipt(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def tx_window_counts(path, windows):
    result = [{'window_ns': w, 'new_tx_bytes': 0, 'retx_rows': 0} for w in windows]
    high = 1
    with path.open(newline='') as source:
        for row in csv.DictReader(source):
            if row['event'] != 'TX' or not row['seq'] or int(row['payload_bytes']) <= 0:
                continue
            seq, payload, t = int(row['seq']), int(row['payload_bytes']), int(row['time_ns'])
            new = max(0, seq + payload - max(seq, high))
            for data in result:
                if data['window_ns'][0] <= t < data['window_ns'][1]:
                    data['new_tx_bytes'] += new
                    data['retx_rows'] += new == 0
            high = max(high, seq + payload)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export', type=Path, required=True)
    p.add_argument('--historical', type=Path, required=True)
    a = p.parse_args()
    out = a.export / 'comparison.json'
    require(not out.exists(), 'Refusing to overwrite comparison')
    names = ['leo10-base', 'leo10-hold1', 'leo10-hold2', 'loss-first-base', 'loss-first-hold']
    data, manifests, inputs = {}, {}, []
    for name in names:
        source = a.export / 'cases' / name / 'summary.json'
        data[name] = json.loads(source.read_text())
        manifests[name] = json.loads((source.parent / 'manifest.json').read_text())
        inputs.append(receipt(source))
    comparisons = []
    for base, policy in [('leo10-base', 'leo10-hold1'), ('leo10-base', 'leo10-hold2'), ('loss-first-base', 'loss-first-hold')]:
        b, n = data[base], data[policy]
        bm, nm = manifests[base], manifests[policy]
        for key in ['ns3_head', 'patch_sha256', 'installed_diff_sha256', 'runtime_files',
                    'state_static_sha256', 'dynamic_input_sha256', 'forecast_source_sha256', 'runner_sha256']:
            require(bm[key] == nm[key], f'Unmatched {key}: {base}, {policy}')
        windows = n['controller']['requested_hold_windows_ns']
        tx_paths = {case: Path(next(x['path'] for x in data[case]['provenance']['analysis_inputs'] if x['kind'] == 'sender')) for case in (base, policy)}
        tx_counts = {case: tx_window_counts(path, windows) for case, path in tx_paths.items()}
        require(all(x['new_tx_bytes'] == 0 for x in tx_counts[policy]), f'New data during hold: {policy}')
        event_rows = []
        for bw, nw in zip(b['path_event_windows'], n['path_event_windows']):
            require([bw[k] for k in ['time_s', 'window_start_s', 'window_end_s']] == [nw[k] for k in ['time_s', 'window_start_s', 'window_end_s']], 'Unmatched event windows')
            if bw['time_s'] not in (26.2, 75.0):
                continue
            bc, nc = bw['flows'].get('0', {}), nw['flows'].get('0', {})
            event_rows.append({'event_s': bw['time_s'], 'window_s': [bw['window_start_s'], bw['window_end_s']],
                               'baseline': bc, 'policy': nc})
        comparisons.append({'baseline': base, 'policy': policy,
            'receiver_goodput_mbps': [b['metrics']['receiver_goodput_mbps'], n['metrics']['receiver_goodput_mbps']],
            'receiver_goodput_change_percent': 100 * (n['metrics']['receiver_goodput_mbps'] / b['metrics']['receiver_goodput_mbps'] - 1),
            'fct_s': [b['metrics']['fct_s'], n['metrics']['fct_s']],
            'fct_change_percent': None if b['metrics']['fct_s'] is None else 100 * (n['metrics']['fct_s'] / b['metrics']['fct_s'] - 1),
            'srtt_mean_ms': [b['flow']['smoothed_rtt']['time_weighted_mean_ms'], n['flow']['smoothed_rtt']['time_weighted_mean_ms']],
            'actual_hold_tx': tx_counts, 'event_windows': event_rows})
    old = json.loads(a.historical.read_text())['publication_export']
    current = {Path(x['path']).name: x for x in data['leo10-base']['provenance']['raw_inputs']}
    checks = []
    for item in old['raw_inputs'] + old['legacy_inputs']:
        name = Path(item['path']).name
        require(name in current, f'Missing historical trace: {name}')
        require(all(current[name][k] == item[k] for k in ('bytes', 'sha256')), f'Historical baseline differs: {name}')
        checks.append({'name': name, 'bytes': item['bytes'], 'sha256': item['sha256'], 'matched': True})
    out.write_text(json.dumps({'schema_version': 1, 'tool': receipt(Path(__file__)), 'inputs': inputs,
        'historical_input': receipt(a.historical), 'historical_baseline_byte_matches': checks,
        'comparisons': comparisons,
        'limits': ['Historical comparison covers exactly eight original/legacy CSV files for one condition.',
                   'All pairs use the same source and runtime. Holds are checked against actual socket events and sender transmissions.',
                   'No counter directly identifies send opportunities blocked by the gate. Baseline TX in the same window is contextual evidence only.',
                   'SRTT is not direct queueing delay; deterministic cases are not independent repetitions.']}, indent=2) + '\n')
    print(out)


if __name__ == '__main__':
    main()
