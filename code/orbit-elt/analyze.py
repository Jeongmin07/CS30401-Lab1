#!/usr/bin/env python3
"""Analyze completed ELT screening traces without simulations or old result inputs.

Example: python3 -B analyze.py --root /tmp/orbit-elt --out /tmp/orbit-elt-summary
All time windows use [start, end); FCT requires complete ordered APP delivery.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import shutil

NS = 1_000_000_000
STEP = 100_000_000
MSS = 1380
IDENTITY = ('flow_id', 'tx_id', 'tx_time_ns', 'seq', 'payload_bytes')
WINDOWS = {'first': (25_700_000_000, 28_200_000_000),
           'legacy': (74_500_000_000, 77_000_000_000),
           'focus75': (74_500_000_000, 77_500_000_000),
           'pre75': (74_500_000_000, 75_000_000_000),
           'post75': (75_000_000_000, 75_500_000_000)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def receipt(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def rows(path, fields=()):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        require(set(fields) <= set(reader.fieldnames or ()), f'Unsupported header: {path}')
        for r in reader:
            require(None not in r and all(v is not None for v in r.values()), f'Malformed row: {path}')
            yield r


def number(r, field, default=None):
    value = r.get(field)
    return default if value in (None, '') else int(value)


def identity(r):
    if any(r.get(k) in (None, '') for k in IDENTITY):
        return None
    result = tuple(int(r[k]) for k in IDENTITY)
    return result if result[0] == 0 and result[-1] > 0 else None


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def verify(run):
    path = run / 'manifest.json'
    m = json.loads(path.read_text(encoding='utf-8-sig'))
    require(m.get('status') == 'success' and m.get('exit_code') == 0 and not m.get('audit_exclude'),
            f'Incomplete/excluded case: {run}')
    for flag in ('runtime_unchanged', 'source_unchanged'):
        require(m.get(flag) is True, f'Missing/failed {flag}: {run}')
    if 'launch_source_files_unchanged' in m:
        require(m['launch_source_files_unchanged'] is True, f'Launch sources changed: {run}')
    expected = m.get('output_files')
    require(isinstance(expected, dict) and expected, f'No raw output inventory: {run}')
    actual = {}
    for name, claimed in expected.items():
        p = run / name
        require(p.resolve().is_relative_to(run.resolve()) and p.is_file(), f'Invalid/missing output: {name}')
        record = receipt(p)
        require(all(record[k] == claimed[k] for k in ('bytes', 'sha256')), f'Raw hash mismatch: {p}')
        actual[name] = record
    found = {p.relative_to(run).as_posix() for p in run.rglob('*')
             if p.is_file() and p.suffix in ('.csv', '.txt', '.properties')}
    expected_raw = {name for name in actual if Path(name).suffix in ('.csv', '.txt', '.properties')}
    require(found == expected_raw, f'Unrecorded/missing raw files: {run}: {found ^ expected_raw}')
    for name, claimed in m.get('input_files', {}).items():
        p = run / name
        require(p.resolve().is_relative_to(run.resolve()) and p.is_file(), f'Invalid/missing run input: {name}')
        observed = receipt(p)
        require(all(observed[k] == claimed[k] for k in ('bytes', 'sha256')), f'Input hash mismatch: {name}')
    if 'input_files_unchanged' in m:
        require(m['input_files_unchanged'] is True, f'Run input changed: {run}')
    if 'state_inputs_unchanged' in m:
        require(m['state_inputs_unchanged'] is True, f'Supplied state input changed: {run}')
    if m.get('profile') == 'elt':
        require(m.get('input_files_unchanged') is True and m.get('state_inputs_unchanged') is True,
                f'ELT run lacks successful input immutability checks: {run}')
    config_path = run / 'config_ns3.properties'
    require(config_path.is_file() and 'config_ns3.properties' in actual, f'Missing recorded config: {run}')
    config = dict(line.split('=', 1) for line in config_path.read_text().splitlines()
                  if '=' in line and not line.lstrip().startswith('#'))
    duration = int(config['simulation_end_time_ns'])
    require(duration > 0, f'Invalid duration: {run}')
    d = m['definition']
    if 'duration' in d:
        require(round(float(d['duration']) * NS) == duration, f'Definition/config duration differs: {run}')
    maximum = m.get('expected_finite_bytes')
    start = 0
    if (run / 'schedule.csv').exists():
        with (run / 'schedule.csv').open(newline='') as f:
            schedule = list(csv.reader(f))
        require(len(schedule) == 1 and schedule[0][0] == '0', f'Expected one flow schedule: {run}')
        start = int(schedule[0][4])
        if m.get('additional_parameters') is not None:
            require(schedule[0][5] == m['additional_parameters'], f'Schedule parameters differ: {run}')
    else:
        options = dict(x[2:].split('=', 1) for x in m.get('command', []) if x.startswith('--') and '=' in x)
        start = round(float(options.get('flow_start_s', d.get('flow_start_s', 0))) * NS)
        if 'max_bytes' in options:
            require(maximum == int(options['max_bytes']), f'Finite byte declaration differs: {run}')
    require(0 <= start < duration and (maximum is None or maximum > 0), f'Invalid flow bounds: {run}')
    return m, actual, duration, start, maximum


def windows(duration):
    return {'whole': (0, duration), **{k: v for k, v in WINDOWS.items() if v[1] <= duration}}


def app_delivery(logs, bounds, duration):
    inputs = sorted(logs.glob('study_app_rx_node_*_port_*.csv'))
    require(len(inputs) == 1, f'Expected one ordered APP trace: {logs}')
    totals = Counter(); connection = Counter(); last = None; first = None; previous = -1
    for r in rows(inputs[0], ('flow_id', 'time_ns', 'payload_bytes', 'connection_total_rx_bytes')):
        t, amount = int(r['time_ns']), int(r['payload_bytes'])
        require(r['flow_id'] == '0' and previous <= t and 0 <= t < duration,
                f'Invalid APP ordering/flow: {logs}')
        require(amount >= 0, f'Negative APP payload: {logs}')
        previous = t
        key = (r.get('node_id'), r.get('connection_id'))
        connection[key] += amount
        require(connection[key] == int(r['connection_total_rx_bytes']), f'APP cumulative sum differs: {logs}')
        if amount:
            first = t if first is None else first
            last = t
        for name, (a, b) in bounds.items():
            if a <= t < b:
                totals[name] += amount
    return {'source': receipt(inputs[0]), 'window_bytes': totals, 'first_ns': first, 'last_ns': last,
            'ordered_app_bytes': totals['whole'], 'connection_totals': list(connection.values())}


def drops(logs, bounds):
    path = logs / 'study_drops.csv'
    data = defaultdict(list); by_layer = Counter(); untagged = Counter(); dropped = {}; original_matches = Counter()
    for r in rows(path, ('time_ns', 'layer', 'node', 'device', *IDENTITY)):
        t = int(r['time_ns']); by_layer[r['layer']] += 1
        key = identity(r)
        if key is None:
            untagged[r['layer']] += 1
            continue
        dropped.setdefault(key, []).append(r)
        for name, (a, b) in bounds.items():
            if a <= t < b:
                data[name].append(key)
    return {'source': receipt(path), 'by_layer': dict(by_layer), 'unmapped_notifications': dict(untagged),
            'identities': dropped, 'window_identities': data, 'tx_matches': original_matches}


def packet_metrics(logs, bounds, dropped):
    path = logs / 'tcp_flow_0_study_packets.csv'
    counts = {name: Counter() for name in bounds}; retx = defaultdict(list); tx_for_drop = {}
    first_tx = None; last_tx = None; previous = -1
    for r in rows(path, ('flow_id', 'time_ns', 'event', *IDENTITY)):
        t = int(r['time_ns']); require(t >= previous and r['flow_id'] == '0', f'Sender ordering/flow: {path}')
        previous = t
        if r['event'] not in ('TX', 'RETX') or int(r['payload_bytes'] or 0) <= 0:
            continue
        key = identity(r); require(key is not None and t == key[2], f'Bad TX identity: {path}')
        if r['event'] == 'TX':
            first_tx = t if first_tx is None else first_tx; last_tx = t
            if key in dropped['identities']:
                require(key not in tx_for_drop, f'Duplicate TX tuple: {key}')
                tx_for_drop[key] = {k: int(r[k]) for k in ('time_ns', *IDENTITY)}
        else:
            retx[int(r['seq'])].append({'time_ns': t, 'payload_bytes': int(r['payload_bytes']),
                                      'tx_id': int(r['tx_id']), 'tx_time_ns': int(r['tx_time_ns'])})
        for name, (a, b) in bounds.items():
            if a <= t < b:
                counts[name]['retx_packets' if r['event'] == 'RETX' else 'tx_payload_rows'] += 1
    require(set(tx_for_drop) == set(dropped['identities']), f'Drop lacks exact sender TX identity: {path}')
    joined = []
    for key, notifications in sorted(dropped['identities'].items(), key=lambda kv: min(int(r['time_ns']) for r in kv[1])):
        first = min(notifications, key=lambda r: int(r['time_ns'])); t = int(first['time_ns'])
        require(key[2] <= t, f'Drop precedes TX: {key}')
        later = [r for r in retx[key[3]] if r['time_ns'] >= t and r['payload_bytes'] >= key[4]]
        joined.append({'identity': dict(zip(IDENTITY, key)), 'first_drop': first,
                       'actual_tx': tx_for_drop[key], 'drop_notifications': len(notifications),
                       'first_retx_after_drop': later[0] if later else None,
                       'drop_to_first_retx_ns': later[0]['time_ns'] - t if later else None})
    return counts, joined, {'source': receipt(path), 'first_payload_tx_ns': first_tx, 'last_payload_tx_ns': last_tx,
                           'first_retx_ns': min((v[0]['time_ns'] for v in retx.values()), default=None)}


def state_metrics(logs, bounds, counts):
    path = logs / 'tcp_flow_0_study_events.csv'; thresholds = set(); previous = -1
    for r in rows(path, ('flow_id', 'time_ns', 'event', 'old_value', 'new_value', 'threshold')):
        t = int(r['time_ns']); require(t >= previous and r['flow_id'] == '0', f'State ordering/flow: {path}')
        previous = t; thresholds.add(int(r['threshold']))
        if r['event'] != 'CONG' or r['old_value'] == r['new_value']:
            continue
        event = {3: 'recovery_entries', 4: 'loss_state_entries'}.get(int(r['new_value']))
        if event:
            for name, (a, b) in bounds.items():
                if a <= t < b:
                    counts[name][event] += 1
    require(thresholds == {3}, f'Unexpected global DupAckThreshold values: {thresholds}')
    return {'source': receipt(path), 'observed_threshold_values': sorted(thresholds),
            'ca_loss_is_not_an_independent_RTO_counter': True}


def queue_metrics(logs, bounds, duration):
    path = logs / 'queue_area_bins.csv'
    if not path.exists():
        return None
    sums = {w: Counter() for w in bounds}; source = {w: Counter() for w in bounds}; seen = set(); source_bins = {}
    for r in rows(path, ('bin_start_ns', 'bin_end_ns', 'node_id', 'device_id', 'q_packet_ns', 'q_byte_ns',
                         'peak_packets', 'peak_bytes', 'full_ns', 'max_packets', 'cutoff_ns')):
        r = {k: int(v) for k, v in r.items()}; a, b = r['bin_start_ns'], r['bin_end_ns']
        key = (r['node_id'], r['device_id'], a)
        require(key not in seen and 0 <= a < b <= duration and a % STEP == 0 and b - a <= STEP,
                f'Invalid/duplicate queue bin: {path}')
        seen.add(key)
        require(r['cutoff_ns'] == duration and 0 <= r['full_ns'] <= b - a and
                r['peak_packets'] <= r['max_packets'] and
                0 <= r['q_packet_ns'] <= (b - a) * r['peak_packets'] and
                0 <= r['q_byte_ns'] <= (b - a) * r['peak_bytes'], f'Invalid queue area: {path}')
        at_source = (r['node_id'], r['device_id']) == (1584, 1)
        if at_source:
            source_bins[a] = r
        for w, (start, end) in bounds.items():
            if end <= a or b <= start:
                continue
            require(start <= a and b <= end, f'Window splits exact bin; interpolation refused: {w}')
            for dst in ([sums[w], source[w]] if at_source else [sums[w]]):
                for field in ('q_packet_ns', 'q_byte_ns', 'full_ns'):
                    dst[field] += r[field]
                for field in ('peak_packets', 'peak_bytes'):
                    dst[field] = max(dst[field], r[field])
    result = {}
    for w, (a, b) in bounds.items():
        result[w] = {'source': dict(source[w], mean_packets=source[w]['q_packet_ns'] / (b - a),
                                   mean_bytes=source[w]['q_byte_ns'] / (b - a)),
                     'all_device': dict(sums[w], summed_mean_packets=sums[w]['q_packet_ns'] / (b - a))}
    conservation = {}; service = {w: Counter() for w in bounds}; visits_path = logs / 'orbit_queue_bins.csv'
    for r in rows(visits_path, ('bin_start_ns', 'bin_end_ns', 'node_id', 'device_id', 'flow_id', 'enqueued',
                                'dequeued', 'drop_before', 'drop_after', 'sojourn_samples', 'sojourn_sum_ns', 'sojourn_max_ns')):
        key = (int(r['node_id']), int(r['device_id']), r['flow_id'])
        total = conservation.setdefault(key, Counter())
        for k in ('enqueued', 'dequeued', 'drop_before', 'drop_after', 'sojourn_samples', 'sojourn_sum_ns'):
            total[k] += int(r[k])
        require(int(r['drop_after']) == 0 and int(r['dequeued']) == int(r['sojourn_samples']),
                f'Device dequeue cannot be interpreted as served: {visits_path}')
        if key[:2] == (1584, 1):
            a, b = int(r['bin_start_ns']), int(r['bin_end_ns'])
            for w, (start, end) in bounds.items():
                if end <= a or b <= start:
                    continue
                require(start <= a and b <= end, f'Sojourn window splits bin: {w}')
                service[w]['samples'] += int(r['sojourn_samples'])
                service[w]['sum_ns'] += int(r['sojourn_sum_ns'])
                service[w]['max_ns'] = max(service[w]['max_ns'], int(r['sojourn_max_ns']))
    pending = {}; pending_path = logs / 'orbit_queue_pending.csv'
    for r in rows(pending_path, ('cutoff_ns', 'node_id', 'device_id', 'flow_id', 'pending_packets')):
        require(int(r['cutoff_ns']) == duration, 'Pending cutoff mismatch')
        key = (int(r['node_id']), int(r['device_id']), r['flow_id'])
        require(key not in pending, 'Duplicate pending queue/flow')
        pending[key] = int(r['pending_packets'])
    require(set(pending) <= set(conservation), 'Pending without enqueue observations')
    for key, v in conservation.items():
        require(v['enqueued'] - v['dequeued'] == pending.get(key, 0), f'Queue conservation failed: {key}')
    for w, v in service.items():
        result[w]['source_served_wait'] = dict(v, mean_ns=v['sum_ns'] / v['samples'] if v['samples'] else None)
    bins = [dict(start_ns=t, end_ns=min(t + STEP, duration),
                 packet_ns=source_bins.get(t, {}).get('q_packet_ns', 0),
                 byte_ns=source_bins.get(t, {}).get('q_byte_ns', 0),
                 peak_packets=source_bins.get(t, {}).get('peak_packets', 0),
                 full_ns=source_bins.get(t, {}).get('full_ns', 0)) for t in range(0, duration, STEP)]
    return {'windows': result, 'source_bins': bins, 'source_node': 1584, 'source_device': 1,
            'observed_device_bins': len(seen), 'queue_conservation_passed': True,
            'pending_packets': sum(pending.values()), 'sources': [receipt(p) for p in (path, visits_path, pending_path)],
            'method': 'Exact held-state areas, full window denominator and sparse zero bins. Served wait is per device visit, not end-to-end delay.'}


def sparse_policy(logs, filename):
    path = logs / filename
    if not path.exists():
        return {'source': None, 'events': [], 'event_counts': {}, 'count': 0}
    events = [{k: v if k == 'event' else (int(v) if v else None) for k, v in r.items()} for r in rows(path)]
    require(all(r.get('flow_id') == 0 for r in events), f'Unexpected policy flow: {path}')
    require([r['time_ns'] for r in events] == sorted(r['time_ns'] for r in events), f'Policy time order: {path}')
    return {'source': receipt(path), 'events': events,
            'event_counts': dict(Counter(r['event'] for r in events)), 'count': len(events)}


def validate_policies(logs, m, policies):
    selective, tail, elt = (policies[k] for k in ('selective', 'tail', 'elt'))
    begins = [r for r in selective['events'] if r['event'] == 'COHORT_WAIT_BEGIN']
    require(all(r['threshold'] == 3 for r in selective['events']), 'Selective policy changed global K3')
    epochs = {r['epoch_ns']: r for r in begins}
    require(len(epochs) == len(begins), 'Multiple waits in one registered epoch')
    stops = {'COHORT_DEADLINE', 'ACK_MOVED_OUTSIDE_COHORT', 'BUDGET_EXCEEDED', 'OTHER_LOSS',
             'STOCK_RECOVERY', 'STOCK_ECN', 'STOCK_RTO', 'EPOCH_END'}
    episodes = []
    for r in begins:
        endings = [v for v in selective['events'] if v['epoch_ns'] == r['epoch_ns'] and
                   v['time_ns'] >= r['time_ns'] and v['event'] in stops]
        require(endings and endings[0]['time_ns'] <= r['deadline_ns'], 'Censored/unbounded selective wait')
        if m.get('hints'):
            hint = next((h for h in m['hints'] if h['start_ns'] == r['epoch_ns']), None)
            require(hint and r['deadline_ns'] == min(r['time_ns'] + hint['wait_ns'], hint['end_ns']),
                    'Actual selective deadline differs from original declared hint')
        ending = endings[0]
        episodes.append(dict(epoch_ns=r['epoch_ns'], start_ns=r['time_ns'], end_ns=ending['time_ns'],
                             deadline_ns=r['deadline_ns'], end_event=ending['event'],
                             elapsed_ns=ending['time_ns'] - r['time_ns']))
    selective['episodes'] = episodes
    tail['admissions'] = [r for r in tail['events'] if r['event'] == 'TAIL_ADMIT']
    mode = int(m['definition'].get('elt_mode', 0))
    require(mode in (0, 1, 2), 'Unsupported declared ELT mode')
    if mode:
        require(elt['source'] is not None and not tail['admissions'], 'ELT trace missing or legacy tail admitted')
    else:
        require(not elt['events'], 'Disabled ELT emitted active events')
    require(all(r['mode'] == mode for r in elt['events']), 'ELT mode differs from declaration')
    starts = [r for r in elt['events'] if r['event'] == 'ELT_BEGIN']
    require(len({(r['epoch_ns'], r['deadline_ns']) for r in starts}) == len(starts),
            'Multiple ELT activations in one episode')
    validations = []
    for begin in starts:
        episode = next((e for e in episodes if e['epoch_ns'] == begin['epoch_ns'] and
                        e['start_ns'] <= begin['time_ns'] <= e['end_ns']), None)
        require(episode and begin['deadline_ns'] == episode['deadline_ns'], 'ELT activation outside actual wait')
        require(begin['saved_flight_bytes'] > 0 and begin['active'] == 1 and begin['phase_used'] == 1,
                'Invalid entry flight/activation trace')
        group = [r for r in elt['events'] if r['epoch_ns'] == begin['epoch_ns'] and
                 r['deadline_ns'] == begin['deadline_ns']]
        require(all(r['saved_flight_bytes'] == begin['saved_flight_bytes'] for r in group),
                'ELT saved entry flight changed')
        before = [r for r in group if r['event'] == 'ELT_SEND_BEFORE']
        sends = [r for r in group if r['event'] == 'ELT_NEW_TX']
        require(len(before) == len(sends), 'Unpaired planned/actual ELT send')
        for pre, post in zip(before, sends):
            require((pre['time_ns'], pre['seq']) == (post['time_ns'], post['seq']), 'ELT send pair identity differs')
            require(pre['sent_bytes'] == post['sent_bytes'] == MSS and pre['active'] == post['active'] == 1 and
                    pre['unsent_bytes'] >= MSS and pre['seq'] == pre['high_tx'] and
                    pre['seq'] + MSS <= pre['receiver_right_edge'] and pre['new_sack_bytes'] > 0 and
                    begin['time_ns'] <= pre['time_ns'] < begin['deadline_ns'], 'ELT new-data send gate failed')
            require(pre['pipe_bytes'] + pre['skipped_bytes'] + MSS <= begin['saved_flight_bytes'],
                    'ELT entry-flight ceiling failed')
            require(post['pipe_bytes'] == pre['pipe_bytes'] + MSS and post['high_tx'] == pre['high_tx'] + MSS,
                    'ELT send flight/highTx change differs from payload')
            require(post['pipe_bytes'] <= begin['saved_flight_bytes'], 'Actual post-send flight exceeds entry flight')
            require(post['skipped_bytes'] == (pre['skipped_bytes'] + MSS if mode == 2 else 0) and
                    (mode == 2 or pre['skipped_bytes'] == 0), 'ELT mode-specific skipped allowance failed')
            require(post['cwnd_bytes'] == pre['cwnd_bytes'], 'ELT send changed native cwnd')
        cacks = [r for r in group if r['event'] == 'ELT_EXIT_CACK']
        before_cacks = [r for r in group if r['event'] == 'ELT_CACK_BEFORE']
        require(len(cacks) == len(before_cacks), 'Unpaired cumulative-ACK T1/T2 events')
        for pre, r in zip(before_cacks, cacks):
            pending = [v for v in group if v['event'] == 'ELT_CACK_PENDING' and v['time_ns'] <= pre['time_ns']]
            require(pre['active'] == 1 or (pre['active'] == 0 and pending), 'T1/T2 lacks active or pending CACK phase')
            require(pre['time_ns'] == r['time_ns'] and pre['head_seq'] == r['head_seq'] and
                    pre['high_tx'] == r['high_tx'], 'T1/T2 changed ACK flight or chronology')
            post_ack_flight = max(0, r['high_tx'] - r['head_seq'])
            require(r['active'] == 0 and
                    r['cwnd_bytes'] == min(post_ack_flight + MSS, begin['saved_flight_bytes']) and
                    r['ssthresh_bytes'] == begin['saved_flight_bytes'], 'Cumulative-ACK T1/T2 trace does not match')
        validations.append(dict(epoch_ns=begin['epoch_ns'], deadline_ns=begin['deadline_ns'],
                                saved_flight_bytes=begin['saved_flight_bytes'], original_sends=len(sends),
                                original_sent_bytes=sum(r['sent_bytes'] for r in sends), cack_exits=len(cacks)))
    admissions = [r for r in elt['events'] if r['event'] == 'ELT_NEW_TX']
    wanted = {(r['time_ns'], r['seq'], r['sent_bytes']): r for r in admissions}
    require(len(wanted) == len(admissions), 'Duplicate ELT send identity')
    matches = Counter(); first_by_seq = {}; same_time_retx = Counter()
    if admissions:
        for r in rows(logs / 'tcp_flow_0_study_packets.csv', ('event', 'time_ns', 'seq', 'payload_bytes', *IDENTITY)):
            if r['event'] not in ('TX', 'RETX') or int(r['payload_bytes'] or 0) <= 0:
                continue
            t, seq, amount = int(r['time_ns']), int(r['seq']), int(r['payload_bytes'])
            k = (t, seq, amount)
            if r['event'] == 'TX':
                first_by_seq.setdefault(seq, t)
                if k in wanted:
                    matches[k] += 1
            elif k in wanted:
                same_time_retx[k] += 1
        require(all(matches[k] == 1 and same_time_retx[k] == 0 and first_by_seq[k[1]] == k[0] for k in wanted),
                'ELT action lacks a unique original sender TX')
    elt['episode_validation'] = validations
    elt['mode'] = mode
    elt['new_tx_actions'] = len(admissions)
    elt['new_tx_bytes'] = sum(r['sent_bytes'] for r in admissions)
    elt['actual_original_sender_TX_audit'] = True
    elt['flight_ceiling_and_mode_allowance_audit'] = True
    elt['allowance_semantics'] = ('E2 checks pre-send pipe+Skipped+MSS<=entry flight. Actual post-send pipe<=entry flight; '
                                'Careful increments Skipped after send, so pipe+Skipped may then exceed entry flight by one MSS.')
    elt['cack_T1_T2_audit_scope'] = 'Observed ELT_EXIT_CACK rows only; no untriggered branch safety claim.'
    elt['sequence_arithmetic_scope'] = 'These declared 10-Mbps/200-s and finite cases do not wrap 32-bit data sequences; FIN beyond high data TX means zero post-ACK data flight.'


def analyze(run):
    m, raw, duration, start, expected = verify(run); logs = run / 'logs_ns3'; bounds = windows(duration)
    app = app_delivery(logs, bounds, duration); loss = drops(logs, bounds)
    counts, joined, packet = packet_metrics(logs, bounds, loss)
    state = state_metrics(logs, bounds, counts); queue = queue_metrics(logs, bounds, duration)
    complete = app['ordered_app_bytes'] == expected if expected is not None else None
    require(expected is None or app['ordered_app_bytes'] <= expected, f'APP exceeds finite MaxBytes: {run}')
    require(app['first_ns'] is None or app['first_ns'] >= start, f'APP arrived before flow start: {run}')
    metrics = {}
    for w, (a, b) in bounds.items():
        metrics[w] = {'start_ns': a, 'end_ns': b, 'app_bytes': app['window_bytes'][w],
                      'app_goodput_mbps': app['window_bytes'][w] * 8 * 1000 / (b - a),
                      **{k: counts[w][k] for k in ('tx_payload_rows', 'retx_packets', 'recovery_entries', 'loss_state_entries')},
                      'tagged_data_drop_notifications': len(loss['window_identities'][w]),
                      'unique_tagged_data_losses': len(set(loss['window_identities'][w]))}
    policies = {'selective': sparse_policy(logs, 'tcp_flow_0_orbit_loss.csv'),
                'tail': sparse_policy(logs, 'tcp_flow_0_orbit_loss_tail.csv'),
                'elt': sparse_policy(logs, 'tcp_flow_0_orbit_loss_elt.csv')}
    validate_policies(logs, m, policies)
    first_physical = next((r for r in joined if r['first_drop']['layer'] == 'PhyRxDrop'), None)
    coverage_path = logs / 'study_drop_coverage.csv'
    coverage = list(rows(coverage_path, ('node', 'device', 'layer', 'connected')))
    return {'case': m['case'], 'definition': m['definition'], 'duration_ns': duration, 'flow_start_ns': start,
            'expected_finite_bytes': expected, 'transfer_complete': complete,
            'fct_s': (app['last_ns'] - start) / NS if complete else None,
            'metrics': metrics, 'application': app, 'sender': packet, 'state': state,
            'drops': {'by_layer': loss['by_layer'], 'unmapped_notifications': loss['unmapped_notifications'],
                      'distinct_identity_joins': joined, 'first_recorded_data_drop': joined[0] if joined else None,
                      'first_physical_drop': first_physical, 'source': loss['source'], 'coverage': coverage,
                      'coverage_source': receipt(coverage_path), 'all_tagged_data_drops_have_exact_TX': True},
            'queue': queue, 'policies': policies,
            'provenance': {'manifest': receipt(run / 'manifest.json'), 'verified_raw_files': raw,
                           'launch_identity': {k: m[k] for k in ('command', 'declared_source_checkpoint', 'source_checkpoint',
                               'launch_commit', 'repo_commit', 'source_files', 'runtime', 'runtime_files', 'patch_sha256',
                               'installed_diff_sha256', 'image', 'image_ref', 'image_digest', 'hints', 'input_files',
                               'state_static_sha256', 'dynamic_input_sha256', 'forecast_source_sha256',
                               'build_ready_sha256', 'runner_sha256', 'environment', 'wall_seconds',
                               'runtime_unchanged', 'source_unchanged', 'launch_source_files_unchanged',
                               'input_files_unchanged', 'state_inputs_unchanged') if k in m},
                           'analysis_tool': receipt(Path(__file__))},
            'limitations': ['FCT is null unless the entire positive finite MaxBytes was delivered; bulk FCT is null.',
                'APP HandleRead is ordered delivery; cached SRTT is not measured queue residence.',
                'Tagged payload-bearing data loss is a full TX identity union; unmapped ACK/control notifications stay separate.',
                'CA_LOSS state entries are not independently counted RTOs.',
                'Tail/ELT behavior is not a queue fix. No T75 causality is inferred from cwnd, drops or absent policy actions.',
                'Historical OFF byte parity is a separate root-owned check; this analyzer hashes newly completed raw data.']}


def matched_inputs(runs):
    """Compare immutable launch identities, preserving declared policy differences."""
    records = [json.loads((r / 'manifest.json').read_text()) for r in runs]
    fields = ('patch_sha256', 'installed_diff_sha256', 'runtime_files', 'source_files',
              'state_static_sha256', 'dynamic_input_sha256', 'forecast_source_sha256', 'image_ref')
    checks = {}
    for field in fields:
        presence = [field in m for m in records]
        require(all(presence) or not any(presence), f'Inconsistent provenance key: {field}')
        if not any(presence):
            continue
        # Micro does not load the LEO routing state. Compare routing-input hashes
        # within each model; implementation/runtime/image must match globally.
        groups = defaultdict(list)
        for m in records:
            group = m['definition']['kind'] if field in ('state_static_sha256', 'dynamic_input_sha256') else 'all'
            groups[group].append(m)
        checks[field] = {}
        for group, items in groups.items():
            require(all(m[field] == items[0][field] for m in items), f'Unmatched {field}: {group}')
            checks[field][group] = {'cases': [m['case'] for m in items], 'equal': True}
    family_checks = []
    groups = defaultdict(list)
    for run, m in zip(runs, records):
        d = m['definition']
        groups[(d['kind'], d.get('bytes'), d.get('duration'), d.get('rate'), d.get('queue'))].append((run, m))
    for family, items in groups.items():
        configs = []
        schedules = []
        for run, m in items:
            config = dict(line.split('=', 1) for line in (run / 'config_ns3.properties').read_text().splitlines()
                          if '=' in line and not line.lstrip().startswith('#'))
            # Strip only the path locator of this run's differently named schedule.
            locators = {k for k, v in config.items() if str(run) in v}
            configs.append({k: ('<run-locator>' if k in locators else v) for k, v in config.items()})
            if (run / 'schedule.csv').exists():
                with (run / 'schedule.csv').open(newline='') as f:
                    schedule = list(csv.reader(f))
                require(len(schedule) == 1, 'Multiple schedules in matched input family')
                schedules.append(schedule[0][:5] + schedule[0][6:])
            options = dict(x[2:].split('=', 1) for x in m['command'] if x.startswith('--') and '=' in x)
            if m['definition']['kind'] == 'micro':
                require(options.get('loss_seq') == '1' and options.get('before_ms') == '50' and
                        options.get('after_ms') == '50' and options.get('rate') == '100' and
                        options.get('queue_pkts') == '2000', 'Micro fixed loss/path/link control differs')
        require(all(c == configs[0] for c in configs), f'Matched family config differs: {family}')
        require(not schedules or all(s == schedules[0] for s in schedules), f'Matched schedule endpoints/start/bytes differ: {family}')
        family_checks.append({'family': list(family), 'cases': [m['case'] for _, m in items],
                              'config_equal_except_run_locator': True,
                              'schedule_equal_except_policy_parameter_field': True})
    return {'source_runtime_checks': checks, 'families': family_checks,
            'policy_and_forecast_hints': {m['case']: m.get('hints') for m in records},
            'qualification': 'Case policy flags/CLI attributes and schedule parameter field intentionally differ. '
                             'Recorded launch hashes are compared and raw/config bytes verified; no independent clean rebuild is claimed.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cases', nargs='+'); args = p.parse_args()
    require(not args.out.exists(), f'Refusing to overwrite: {args.out}')
    runs = [args.root / n for n in args.cases] if args.cases else sorted(x.parent for x in args.root.glob('*/manifest.json'))
    require(runs and len({x.resolve() for x in runs}) == len(runs), 'No cases or duplicates')
    summaries = [analyze(run) for run in runs]
    require(len({s['case'] for s in summaries}) == len(summaries), 'Duplicate manifest case names')
    matched = matched_inputs(runs)
    args.out.mkdir(parents=True)
    table = []
    for run, s in zip(runs, summaries):
        target = args.out / 'cases' / s['case']; write(target / 'summary.json', s)
        shutil.copyfile(run / 'manifest.json', target / 'manifest.json')
        for name in ('config_ns3.properties', 'schedule.csv'):
            if (run / name).exists(): shutil.copyfile(run / name, target / name)
        for w, metric in s['metrics'].items():
            q = s['queue']['windows'][w] if s['queue'] else None
            a, b = metric['start_ns'], metric['end_ns']
            elt_actions = [r for r in s['policies']['elt']['events'] if r['event'] == 'ELT_NEW_TX' and a <= r['time_ns'] < b]
            tail_actions = [r for r in s['policies']['tail']['events'] if r['event'] == 'TAIL_ADMIT' and a <= r['time_ns'] < b]
            wait_starts = [r for r in s['policies']['selective']['episodes'] if a <= r['start_ns'] < b]
            table.append({'case': s['case'], 'window': w, 'kind': s['definition']['kind'],
                          'variant': s['definition'].get('variant', s['definition'].get('mode')),
                          'expected_finite_bytes': s['expected_finite_bytes'], 'transfer_complete': s['transfer_complete'],
                          'fct_s': s['fct_s'], **metric,
                          'source_mean_queue_packets': q['source']['mean_packets'] if q else None,
                          'all_device_summed_mean_queue_packets': q['all_device']['summed_mean_packets'] if q else None,
                          'source_served_wait_mean_ns': q['source_served_wait']['mean_ns'] if q else None,
                          'selective_wait_starts': len(wait_starts),
                          'elt_new_tx_actions': len(elt_actions),
                          'elt_new_tx_bytes': sum(r['sent_bytes'] for r in elt_actions),
                          'tail_admissions': len(tail_actions)})
    with (args.out / 'summary.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(table)
    write(args.out / 'results.json', {'schema': 1, 'analysis_tool': receipt(Path(__file__)),
                                 'window_convention': '[start_ns,end_ns)', 'matched_inputs': matched, 'cases': summaries})
    write(args.out / 'receipt.json', {'analysis_tool': receipt(Path(__file__)), 'case_count': len(summaries),
                                 'outputs': [receipt(p) for p in sorted(args.out.rglob('*')) if p.is_file()]})
    print(json.dumps({'cases': len(summaries), 'table_rows': len(table), 'out': str(args.out)}))


if __name__ == '__main__':
    main()
