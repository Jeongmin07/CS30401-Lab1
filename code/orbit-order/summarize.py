#!/usr/bin/env python3
"""Export new-data hold cases with independent input and controller checks.

Example: python3 -B summarize.py --root /tmp/orbit-order --out NEW --cases CASE
Hashes identify observed files; they do not independently certify source builds.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil


def require(condition, message):
    if not condition:
        raise ValueError(message)


def receipt(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def rows(path, fields):
    with path.open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        require(set(fields) <= set(reader.fieldnames or []), f'Unsupported header: {path}')
        yield from reader


def summarize(run):
    manifest_path, analysis_path = run / 'manifest.json', run / 'analysis.json'
    manifest, data = [json.loads(p.read_text()) for p in (manifest_path, analysis_path)]
    require(manifest.get('status') == 'success' and manifest.get('exit_code') == 0, f'Incomplete: {run}')
    require(data.get('schema_version') == 1 and set(data['flows']) == {'0'}, f'Expected one flow 0: {run}')
    definition, flow, duration = manifest['definition'], data['flows']['0'], data['duration_s']
    cli = dict(arg[2:].split('=', 1) for arg in manifest['command'] if arg.startswith('--') and '=' in arg)
    config = dict(line.strip().split('=', 1) for line in (run / 'config_ns3.properties').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
    require(duration > 0 and round(duration * 1e9) == int(config['simulation_end_time_ns']) and duration == float(definition.get('duration', cli.get('duration', duration))), f'Duration mismatch: {run}')
    require(not data['trace_rows'].get('unmapped_app_rows', 0), f'Unmapped receiver delivery: {run}')
    inputs = data['inputs']
    require({i['kind'] for i in inputs} == {'sender', 'receiver', 'app', 'state', 'drop'}, f'Missing trace kind: {run}')
    for item in inputs:
        require(Path(item['path']).resolve().is_relative_to(run.resolve()), f'External analysis input: {item}')
    observed = {}
    for name, expected in manifest['output_files'].items():
        path = run / name
        require(path.resolve().is_relative_to(run.resolve()) and path.is_file(), f'Invalid/missing manifest output: {name}')
        item = receipt(path)
        require(all(item[k] == expected[k] for k in ('bytes', 'sha256')), f'Manifest output mismatch: {path}')
        observed[name] = item
    current = {str(p.relative_to(run)) for p in run.rglob('*') if p.is_file() and p.suffix in ('.csv', '.txt', '.properties')}
    require(current == set(observed), f'Unrecorded/missing raw output: {run}')
    raw = [i for name, i in observed.items() if Path(name).parts[0] == 'logs_ns3' and name.endswith('.csv')]
    known = {Path(i['path']).resolve() for i in raw}
    require(all(Path(i['path']).resolve() in known for i in inputs), f'Missing analysis input: {run}')
    checked = []
    for name in ('config_ns3.properties', 'schedule.csv'):
        path = run / name
        if path.exists():
            checked.append(observed[name])
    require(any(Path(i['path']).name == 'config_ns3.properties' for i in checked), f'Missing config: {run}')
    app_inputs = [Path(i['path']) for i in inputs if i['kind'] == 'app']
    require(len(app_inputs) == 1, f'Expected one receiver application trace: {run}')
    delivered, last_ns, window_bytes = 0, None, [0] * len(data['path_event_windows'])
    for row in rows(app_inputs[0], ('flow_id', 'time_ns', 'payload_bytes')):
        require(row['flow_id'] == '0', f'Wrong receiver flow: {run}')
        payload, time_ns = int(row['payload_bytes']), int(row['time_ns'])
        require(payload >= 0 and 0 <= time_ns < round(duration * 1e9), f'Invalid receiver row: {run}')
        delivered += payload
        for index, window in enumerate(data['path_event_windows']):
            if round(window['window_start_s'] * 1e9) <= time_ns < round(window['window_end_s'] * 1e9):
                window_bytes[index] += payload
        if payload:
            last_ns = time_ns
    require(delivered == flow['counts'].get('application_delivered_bytes', 0), f'App sum mismatch: {run}')
    require(math.isclose(delivered * 8 / duration / 1e6, flow['receiver_application_goodput_mbps'], abs_tol=1e-9, rel_tol=0), f'Goodput mismatch: {run}')
    require(last_ns == (None if flow['last_receiver_application_delivery_time_s'] is None else round(flow['last_receiver_application_delivery_time_s'] * 1e9)), f'App endpoint mismatch: {run}')
    for window, amount in zip(data['path_event_windows'], window_bytes):
        counter, width = window['flows'].get('0', {}), window['window_end_s'] - window['window_start_s']
        require(width > 0 and counter.get('application_delivered_bytes', 0) == amount and math.isclose(counter.get('receiver_application_goodput_mbps', 0), amount * 8 / width / 1e6, abs_tol=1e-9, rel_tol=0), f'Event window app/denominator mismatch: {run}')
    controller, intervals, event_counts = [], [], collections.Counter()
    active, previous, previous_time = None, None, -1
    threshold_events = {'THRESHOLD_INIT', 'THRESHOLD_SET', 'THRESHOLD_RESTORE', 'THRESHOLD_RTO_RELEASE'}
    supported = threshold_events | {'THRESHOLD_RESTORE_DEFERRED', 'RESTORE_DEADLINE_MISSED', 'FORECAST_GUARD_SKIP', 'BOUNDED_EXPIRY_REEVALUATE', 'NEW_DATA_HOLD_BEGIN', 'NEW_DATA_HOLD_END', 'SHORT_FLOW_SIZE_BYTES', 'SHORT_FLOW_NOMINAL_MSS', 'SHORT_FLOW_GUARD_BYPASS'}
    state_inputs = [Path(i['path']) for i in inputs if i['kind'] == 'state']
    require(len(state_inputs) == 1, f'Expected one controller trace: {run}')
    for row in rows(state_inputs[0], ('flow_id', 'time_ns', 'event', 'old_value', 'new_value', 'threshold', 'cong_state')):
        require(row['flow_id'] == '0', f'Wrong controller flow: {run}')
        event, time_ns, threshold = row['event'], int(row['time_ns']), int(row['threshold'])
        require(previous_time <= time_ns < round(duration * 1e9), f'Invalid controller time: {run}')
        previous_time = time_ns
        if event not in ('CONG', 'SSTHRESH'):
            require(event in supported, f'Unsupported controller event {event}: {run}')
            controller.append({k: int(v) if k != 'event' else v for k, v in row.items()})
            event_counts[event] += 1
        if event in threshold_events:
            require(int(row['new_value']) == threshold and (previous is None or int(row['old_value']) == previous), f'Threshold transition mismatch: {run}')
            if active is not None and threshold != previous:
                intervals.append({**active, 'end_ns': time_ns, 'end_event': event, 'censored': False})
                active = None
            if threshold > 3 and active is None:
                active = {'start_ns': time_ns, 'threshold': threshold}
            previous = threshold
        else:
            require(previous is None or threshold == previous, f'Unlogged threshold change: {run}')
    require(event_counts['THRESHOLD_INIT'] == 1, f'Missing/duplicate threshold initialization: {run}')
    if active is not None:
        intervals.append({**active, 'end_ns': round(duration * 1e9), 'end_event': None, 'censored': True})
    options = dict(part.split('=', 1) for part in manifest['additional_parameters'].split(';') if part)
    windows = [list(map(int, w.split(':'))) for w in options.get('study_windows', '').split('|') if w]
    bounded = options.get('study_bounded_restore', '0') == '1'
    if bounded:
        for interval in intervals:
            end = max((b for a, b in windows if a <= interval['start_ns'] < b), default=-1)
            require(interval['end_ns'] <= end, f'Bounded interval exceeds declared window: {run}')
    for interval in intervals:
        interval['duration_s'] = (interval['end_ns'] - interval['start_ns']) / 1e9
    require(all(e['threshold']==3 for e in controller), f'Loss threshold changed in hold experiment: {run}')
    holds=[]
    active_hold=None
    for e in controller:
        if e['event']=='NEW_DATA_HOLD_BEGIN':
            require(active_hold is None, f'Overlapping actual hold: {run}')
            active_hold={'start_ns':e['time_ns'],'expected_end_ns':e['new_value']}
        elif e['event']=='NEW_DATA_HOLD_END':
            require(active_hold is not None and e['time_ns']==active_hold['expected_end_ns'],f'Hold end mismatch: {run}')
            holds.append({**active_hold,'end_ns':e['time_ns']})
            active_hold=None
    require(active_hold is None,f'Censored hold requires separate analysis: {run}')
    requested_holds = [list(map(int, w.split(':'))) for w in options.get('orbit_hold_windows', '').split('|') if w]
    require([[h['start_ns'], h['end_ns']] for h in holds] == requested_holds,
            f'Actual hold intervals differ from declared socket schedule: {run}')
    tx=[Path(i['path']) for i in inputs if i['kind']=='sender']
    require(len(tx)==1,f'Expected one sender: {run}')
    high=1
    forbidden_new_bytes=0
    retx_during=0
    for row in rows(tx[0],('event','time_ns','seq','payload_bytes')):
        if row['event']!='TX' or not row['seq'] or int(row['payload_bytes'])<=0: continue
        seq,payload,t=int(row['seq']),int(row['payload_bytes']),int(row['time_ns'])
        new=max(0,seq+payload-max(seq,high))
        if any(h['start_ns']<=t<h['end_ns'] for h in holds):
            forbidden_new_bytes+=new
            if new==0: retx_during+=1
        high=max(high,seq+payload)
    require(forbidden_new_bytes==0,f'New data sent inside hold: {run}')
    maximum, start_s = manifest['expected_finite_bytes'], float(cli.get('flow_start_s', 0))
    require(maximum is None or maximum == int(cli['max_bytes']), f'Finite size declaration mismatch: {run}')
    if (run / 'schedule.csv').exists():
        schedule = list(csv.reader((run / 'schedule.csv').open(newline='')))
        require(len(schedule) == 1 and schedule[0][0] == '0', f'Expected single flow schedule: {run}')
        start_s = int(schedule[0][4]) / 1e9
        require(schedule[0][5] == manifest['additional_parameters'], f'Schedule parameters mismatch: {run}')
    complete = delivered == maximum if maximum is not None and maximum > 0 else None
    metrics = {'case': manifest['case'], 'duration_s': duration, 'flow_start_s': start_s, 'expected_finite_bytes': maximum,
               'receiver_bytes': delivered, 'receiver_goodput_mbps': flow['receiver_application_goodput_mbps'], 'transfer_complete': complete,
               'fct_s': last_ns / 1e9 - start_s if complete else None, 'retransmissions': flow['counts'].get('official_retransmission_rows', 0),
               'recovery_entries': flow['counts'].get('recovery_state_entries', 0), 'ca_loss_entries': flow['counts'].get('loss_state_entries', 0),
               'distinct_tagged_drops': flow['distinct_tagged_transmissions_dropped'], 'drop_trace_rows': flow['counts'].get('drop_trace_rows', 0),
               'actual_high_threshold_time_s': sum(i['duration_s'] for i in intervals), 'censored_high_threshold_intervals': sum(i['censored'] for i in intervals),
               'guard_starts': sum(e['event'] == 'THRESHOLD_SET' and e['new_value'] > 3 for e in controller), 'guard_start_skips': event_counts['FORECAST_GUARD_SKIP'], 'bounded_expiry_reevaluations': event_counts['BOUNDED_EXPIRY_REEVALUATE'], 'expiry_entered_recovery': sum(e['event'] == 'BOUNDED_EXPIRY_REEVALUATE' and e['new_value'] == 1 for e in controller), 'hold_count': len(holds), 'hold_time_s': sum((h['end_ns']-h['start_ns'])/1e9 for h in holds), 'forbidden_new_bytes_during_hold': forbidden_new_bytes, 'retx_tx_during_hold': retx_during}
    compact = {k: v for k, v in flow.items() if k not in ('receiver_application_bins', 'gap_case_samples', 'drop_case_samples', 'recovery_periods', 'protection_intervals', 'unfinished_protection_start_ns')}
    event_windows = [{k: v for k, v in w.items() if k != 'gap_case_samples'} for w in data['path_event_windows']]
    return {'metrics': metrics, 'flow': compact, 'path_event_windows': event_windows, 'analysis_parameters': data['analysis_parameters'],
            'drop_rows_by_layer': data['drop_rows_by_layer'], 'drop_rows_without_usable_transmission_tag': data['drop_rows_without_usable_transmission_tag'], 'drop_coverage': data['drop_coverage'],
            'controller': {'actual_new_data_holds': holds, 'requested_hold_windows_ns': requested_holds, 'bounded_restore_declared': bounded, 'requested_windows_ns': windows, 'events': controller, 'event_counts': dict(event_counts), 'actual_high_threshold_intervals': intervals},
            'provenance': {'manifest': receipt(manifest_path), 'full_analysis': receipt(analysis_path), 'checked_settings': checked, 'verified_execution_outputs': list(observed.values()), 'raw_inputs': raw, 'analysis_inputs': inputs},
            'omissions': {'receiver_application_bins': len(flow.get('receiver_application_bins', [])), 'gap_case_samples': len(flow.get('gap_case_samples', [])), 'drop_case_samples': len(flow.get('drop_case_samples', [])), 'recovery_periods': len(flow.get('recovery_periods', []))},
            'limitations': data['limitations'] + ['CA_LOSS is not independently identified as an RTO; FCT is reported only when receiver delivery equals positive MaxBytes.', 'Hold setters and absence of new transmissions verify scheduled socket holds, but there is no direct counter of send opportunities blocked by the gate. Previously transmitted or device-queued data cannot be recalled; indirect ACK-clock effects may delay genuine loss recovery.', 'Source/binary hashes in the copied execution manifest are declarations, not independently rebuilt validation.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/tmp/orbit-order'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cases', nargs='+')
    args = parser.parse_args()
    require(not args.out.exists(), f'Refusing to overwrite: {args.out}')
    runs = [args.root / n for n in args.cases] if args.cases else sorted(p.parent for p in args.root.glob('*/manifest.json'))
    require(runs and len({p.resolve() for p in runs}) == len(runs), 'No cases or duplicate cases')
    summaries = [summarize(p) for p in runs]
    args.out.mkdir(parents=True)
    for run, data in zip(runs, summaries):
        target = args.out / 'cases' / run.name
        target.mkdir(parents=True)
        (target / 'summary.json').write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
        for name in ('manifest.json', 'config_ns3.properties', 'schedule.csv'):
            if (run / name).exists():
                shutil.copy2(run / name, target / name)
    with (args.out / 'results.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(summaries[0]['metrics']))
        writer.writeheader()
        writer.writerows(d['metrics'] for d in summaries)
    outputs = [receipt(p) for p in sorted(args.out.rglob('*')) if p.is_file()]
    (args.out / 'export-receipt.json').write_text(json.dumps({'schema_version': 1, 'tool': receipt(Path(__file__)), 'cases': [d['metrics']['case'] for d in summaries], 'outputs': outputs, 'raw_archives': 'Not created or claimed by this exporter; raw_inputs receipts identify files for a separate archive manifest.'}, indent=2) + '\n')
    print(args.out)


if __name__ == '__main__':
    main()
