"""Validate completed passive runs and report attributable device queues.

Occupancy is time-weighted state; sojourn is packet-visit weighted, not an
end-to-end delay. Busy time is actual per-device serialization, including all
flows. Exact original CSV equality is required before any performance summary.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
WINDOWS = {'pre': (74_500_000_000, 75_000_000_000),
           'post': (75_000_000_000, 75_500_000_000),
           'legacy': (74_500_000_000, 77_000_000_000),
           'focus': (74_500_000_000, 77_500_000_000)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def mapping_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def rows(path):
    with path.open(newline='') as f:
        yield from csv.DictReader(f)


def key(row):
    return int(row['node_id']), int(row['device_id'])


def window_names(t):
    return [n for n, (a, b) in WINDOWS.items() if a <= t < b]


def stats(values):
    if not values:
        return dict(samples=0, mean_ns=None, p95_ns=None, p99_ns=None, max_ns=None)
    values = sorted(values)
    return dict(samples=len(values), mean_ns=sum(values) / len(values),
                p95_ns=values[math.ceil(len(values)*.95)-1],
                p99_ns=values[math.ceil(len(values)*.99)-1], max_ns=values[-1])


def verify(run, reference):
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'success' and manifest['exit_code'] == 0, 'Incomplete run'
    assert manifest['runtime_unchanged'] and manifest['source_unchanged'], 'Runtime changed'
    for p, record in manifest['output_files'].items():
        assert (run / p).stat().st_size == record['bytes'] and sha(run / p) == record['sha256'], p
    ref = reference['cases'][manifest['case']]
    assert ref['all_manifest_output_hashes_verified']
    original = ref['measurement_csvs']
    actual = {p: manifest['output_files'][p] for p in original}
    assert actual == original, 'Existing measurement trajectory differs'
    # New observers are additional files. No old CSV may disappear.
    assert all((run / p).is_file() for p in original)
    for p, record in ref['input_files'].items():
        assert sha(run / p) == record['sha256'] and (run / p).stat().st_size == record['bytes'], p
    for field in ['state_static_sha256', 'dynamic_input_sha256']:
        assert mapping_sha(manifest[field]) == ref[field+'_mapping_sha256'], field
        assert len(manifest[field]) == ref[field+'_file_count'], field
    return manifest, dict(exact_measurement_csv_count=len(original),
                         all_exact=True, original_case=ref['original_case'],
                         original_manifest_sha256=ref['manifest_sha256'],
                         original_launch_commit=ref['original_launch_commit'],
                         new_launch_commit=manifest['launch_commit'])


def occupancy_stats(trace, start, end):
    assert trace[0][0] == WINDOWS['focus'][0] and trace[-1][0] == WINDOWS['focus'][1]
    assert all(a[0] <= b[0] for a, b in zip(trace, trace[1:])), 'Occupancy order'
    area_packets = area_bytes = full_ns = 0
    peak_packets = peak_bytes = 0
    full_intervals = []
    for left, right in zip(trace, trace[1:]):
        t, n, by, maximum = left
        a, b = max(t, start), min(right[0], end)
        if a >= b:
            continue
        area_packets += n * (b-a)
        area_bytes += by * (b-a)
        peak_packets = max(peak_packets, n)
        peak_bytes = max(peak_bytes, by)
        is_full = ((maximum.endswith('p') and n == int(maximum[:-1])) or
                   (maximum.endswith('B') and by == int(maximum[:-1])))
        if is_full:
            full_ns += b-a
            if full_intervals and full_intervals[-1][1] == a:
                full_intervals[-1][1] = b
            else:
                full_intervals.append([a, b])
    return dict(time_weighted_packets=area_packets/(end-start),
                time_weighted_bytes=area_bytes/(end-start), peak_packets=peak_packets,
                peak_bytes=peak_bytes, literally_full_ns=full_ns,
                full_intervals_ns=full_intervals, start_ns=start, end_ns=end)


def analyze(run, reference):
    manifest, equality = verify(run, reference)
    logs = run / 'logs_ns3'
    metadata = {}
    for r in rows(logs / 'queue_devices.csv'):
        k = key(r)
        assert k not in metadata or metadata[k] == r, 'Multiple txq mapping unsupported'
        metadata[k] = r
    totals = defaultdict(Counter)
    for r in rows(logs / 'orbit_queue_bins.csv'):
        k = (*key(r), r['flow_id'])
        for f in ['enqueued', 'dequeued', 'drop_before', 'drop_after', 'sojourn_samples', 'sojourn_sum_ns']:
            totals[k][f] += int(r[f])
        totals[k]['sojourn_max_ns'] = max(totals[k]['sojourn_max_ns'], int(r['sojourn_max_ns']))
    pending = Counter()
    for r in rows(logs / 'orbit_queue_pending.csv'):
        pending[(*key(r), r['flow_id'])] += int(r['pending_packets'])
    conservation = []
    for k in sorted(set(totals) | set(pending)):
        c = totals[k]
        assert c['enqueued'] - c['dequeued'] == pending[k], ('Queue conservation', k)
        assert c['drop_after'] == 0 and c['dequeued'] == c['sojourn_samples'], k
        conservation.append(dict(node_id=k[0], device_id=k[1], flow_id=k[2],
                                 **c, pending=pending[k], valid=True))
    occupancy = defaultdict(list)
    for r in rows(logs / 'queue_occupancy.csv'):
        k = key(r)
        occupancy[k].append((int(r['time_ns']), int(r['new_packets']),
                             int(r['queue_bytes']), r['max_size']))
        if r['event'] == 'CHANGE' and len(occupancy[k]) > 1:
            assert int(r['old_packets']) == occupancy[k][-2][1], ('Occupancy continuity', k)
    visit_waits = defaultdict(list)
    visits = defaultdict(Counter)
    for r in rows(logs / 'queue_focus.csv'):
        t = int(r['time_ns']); assert WINDOWS['focus'][0] <= t < WINDOWS['focus'][1]
        for w in window_names(t):
            visits[(key(r), w)][r['event']] += 1
            if r['event'] == 'DEQUEUE':
                assert int(r['sojourn_ns']) >= 0
                visit_waits[(key(r), w)].append(int(r['sojourn_ns']))
    busy = Counter()
    for r in rows(logs / 'orbit_service_bins.csv'):
        a, b = int(r['bin_start_ns']), int(r['bin_end_ns'])
        assert b-a == 100_000_000
        for w, (start, end) in WINDOWS.items():
            if start <= a and b <= end:
                busy[(key(r), w)] += int(r['busy_ns'])
    flow_states = defaultdict(list)
    for r in rows(logs / 'queue_flow_state.csv'):
        t = int(r['time_ns'])
        if not window_names(t):
            continue
        assert int(r['is_stopped']) == (int(r['new_device_stop']) | int(r['new_bql_stop']))
        flow_states[key(r)].append(r)
    tc_drops = list(rows(logs / 'queue_tc_drop.csv'))
    attributed = defaultdict(list)
    for r in tc_drops:
        assert int(r['is_stopped']) == 1 and int(r['queue_mapped']) == 1, 'Unattributed stopped drop'
        assert int(r['device_stop']) | int(r['bql_stop']) == 1
        attributed[key(r)].append(r)
    tagged_drops = list(rows(logs / 'study_drops.csv'))
    old_tc = Counter((r['time_ns'], r['node'], r['uid'], r['flow_id'],
                      r['tx_id'], r['tx_time_ns'], r['seq'], r['payload_bytes'])
                     for r in tagged_drops if r['layer'] == 'TcDrop')
    new_tc = Counter((r['time_ns'], r['node_id'], r['packet_uid'], r['flow_id'],
                      r['tx_id'], r['tx_time_ns'], r['seq'], r['payload_bytes']) for r in tc_drops)
    assert old_tc == new_tc, 'Exact stopped-device hook does not match original TcDrop'
    important = set(attributed)
    for k, tr in occupancy.items():
        if max(v[1] for v in tr) > 0 or k[0] in (1584, 1585):
            important.add(k)
    devices = []
    for k in sorted(important):
        assert k in metadata and k in occupancy
        d = dict(mapping=metadata[k], windows={}, full_run_tc_drop_count=len(attributed[k]))
        for w, (a, b) in WINDOWS.items():
            service = busy[(k, w)]
            assert 0 <= service <= b-a, ('Serialization overcount', k, w)
            ds = [r for r in attributed[k] if a <= int(r['time_ns']) < b]
            states = [r for r in flow_states[k] if a <= int(r['time_ns']) < b]
            d['windows'][w] = dict(occupancy=occupancy_stats(occupancy[k], a, b),
                served_sojourn=stats(visit_waits[(k, w)]), visits=dict(visits[(k, w)]),
                serialization_busy_ns=service, serialization_busy_fraction=service/(b-a),
                tc_drop_count=len(ds), tc_drop_rows=ds,
                stop_count=sum(r['reason'] == 'DEVICE_STOP' for r in states),
                wake_count=sum(r['reason'] == 'DEVICE_WAKE' for r in states),
                bql_stop_count=sum(r['reason'] == 'BQL_STOP' for r in states),
                bql_wake_count=sum(r['reason'] == 'BQL_WAKE' for r in states),
                state_event_count=len(states), first_flow_state=states[0] if states else None,
                last_flow_state=states[-1] if states else None)
        devices.append(d)
    metrics = {n: Counter() for n in ['whole', *WINDOWS]}
    for r in rows(logs / 'study_app_rx_node_1585_port_1024.csv'):
        t = int(r['time_ns']); n = int(r['payload_bytes'])
        assert r['flow_id'] == '0', 'Unexpected application flow'
        for w in ['whole', *window_names(t)]:
            metrics[w]['app_bytes'] += n
    highest = 0
    sender_data_keys = set()
    for r in rows(logs / 'tcp_flow_0_study_packets.csv'):
        if r['event'] == 'RETX':
            for w in ['whole', *window_names(int(r['time_ns']))]:
                metrics[w]['explicit_retx_events'] += 1
        if r['event'] != 'TX' or int(r['payload_bytes']) <= 0:
            continue
        seq, count, t = int(r['seq']), int(r['payload_bytes']), int(r['time_ns'])
        sender_data_keys.add((r['flow_id'], r['packet_uid'], r['tx_id'],
                              r['tx_time_ns'], r['seq'], r['payload_bytes']))
        retx = seq < highest
        highest = max(highest, seq+count)
        for w in ['whole', *window_names(t)]:
            metrics[w]['tx_packets'] += 1
            metrics[w]['retx_packets'] += retx
    for r in tc_drops:
        if r['flow_id'] == '0' and int(r['payload_bytes']) > 0:
            assert (r['flow_id'], r['packet_uid'], r['tx_id'], r['tx_time_ns'],
                    r['seq'], r['payload_bytes']) in sender_data_keys, 'Dropped data does not match sender transmission'
    for r in rows(logs / 'tcp_flow_0_study_events.csv'):
        if r['event'] != 'CONG':
            continue
        t = int(r['time_ns'])
        for w in ['whole', *window_names(t)]:
            metrics[w]['recovery_entries'] += r['new_value'] == '3'
            metrics[w]['loss_state_entries'] += r['new_value'] == '4'
    for r in tagged_drops:
        t = int(r['time_ns'])
        if r['flow_id'] == '0':
            for w in ['whole', *window_names(t)]:
                metrics[w]['tagged_drop_count'] += 1
                metrics[w]['tagged_'+r['layer']] += 1
    measured = {}
    for w, m in metrics.items():
        for field in ['app_bytes', 'tx_packets', 'retx_packets', 'recovery_entries',
                      'loss_state_entries', 'tagged_drop_count', 'tagged_TcDrop',
                      'explicit_retx_events']:
            m.setdefault(field, 0)
        assert m['retx_packets'] == m['explicit_retx_events'], ('Retransmission accounting', w)
        a, b = (0, 200_000_000_000) if w == 'whole' else WINDOWS[w]
        measured[w] = dict(start_ns=a, end_ns=b, **m,
                           app_goodput_mbps=m['app_bytes']*8000/(b-a))
    return dict(schema=1, case=manifest['case'], observer_only=True,
                equality=equality, measurements=measured, devices=devices,
                queue_conservation=conservation,
                qa=dict(manifest_hashes_verified=True, input_state_equal=True,
                        exact_tc_drop_multiset=True, all_queue_conservation=True,
                        tagged_tc_drops_match_sender_tx=True,
                        source_runtime_unchanged=True),
                source=dict(manifest_sha256=sha(run/'manifest.json'),
                            patch_sha256=manifest['patch_sha256'],
                            launch_commit=manifest['launch_commit'],
                            launch_analyzer_sha256=manifest['source_files']['code/orbit-queue/analyze.py'],
                            source_checkpoint=manifest['declared_source_checkpoint'],
                            input_files=manifest['input_files'],
                            runtime_mapping_sha256=mapping_sha(manifest['runtime_files'])),
                caveats=['Same measurement trajectories are verified against completed final V2 runs.',
                         'Device-stop, BQL-stop, literal-full occupancy and Queue drop callbacks are distinct.',
                         'TC rejection before enqueue can occur with zero Queue::DropBeforeEnqueue callbacks.',
                         'Sojourn is per served queue visit; it is not an end-to-end waiting-time sum.',
                         'Focus start/end rows hold the preceding state and do not add simulator events.',
                         'Natural pairs alone do not isolate routing causality.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('/tmp/orbit-queue'))
    p.add_argument('--reference', type=Path, default=HERE/'reference-receipt.json')
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(); assert not a.out.exists(), 'Refuse overwrite'
    reference = json.loads(a.reference.read_text())
    result = {'schema': 1, 'helper_sha256': sha(Path(__file__)),
              'reference_receipt_sha256': sha(a.reference),
              'cases': {n: analyze(a.root/n, reference) for n in ['base-natural', 'selective-natural']}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2)+'\n', newline='\n')
    print(json.dumps({'out': str(a.out), 'sha256': sha(a.out),
                      'qa': {n: c['qa'] for n, c in result['cases'].items()}}))


if __name__ == '__main__':
    main()
