#!/usr/bin/env python3
"""Extract fixed route-shortening diagnostics from existing traces only."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        yield from csv.DictReader(stream)


def source_record(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))


def held_trace(path, start, end):
    if not path.is_file():
        return None
    before = None
    changes = []
    with path.open(newline='') as stream:
        for row in csv.reader(stream):
            time, value = int(row[1]), int(row[2])
            if time < start:
                before = dict(time_ns=time, value=value)
            elif time < end:
                changes.append(dict(time_ns=time, value=value))
            else:
                break
    values = ([before['value']] if before else []) + [r['value'] for r in changes]
    return dict(held_at_start=before, first_change=changes[0] if changes else None,
                last_change=changes[-1] if changes else None, change_count=len(changes),
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def route_events(path):
    rows = list(read_rows(path))
    result = []
    for before, after in zip(rows, rows[1:]):
        old, new = Decimal(before['rtt_prop_ms']), Decimal(after['rtt_prop_ms'])
        if after['path_changed'] != '1' or new >= old:
            continue
        t = int(Decimal(after['t_s']) * 1_000_000_000)
        old_path = list(map(int, before['path_fwd'].split('-')))
        new_path = list(map(int, after['path_fwd'].split('-')))
        result.append(dict(time_ns=t, time_s=float(Decimal(after['t_s'])),
                           old_rtt_prop_ms=float(old), new_rtt_prop_ms=float(new),
                           rtt_decrease_ms=float(old - new),
                           geometric_bdp_ratio=float(new / old),
                           old_path_nodes=old_path, new_path_nodes=new_path,
                           changed_forward_nodes=sorted(set(old_path) ^ set(new_path))))
    return result


def metrics(logs, start, end, queue_file):
    def inside(row, key='time_ns'):
        return start <= int(row[key]) < end

    app_files = list(logs.glob('study_app_rx_node_*_port_1024.csv'))
    if len(app_files) != 1:
        raise ValueError('Expected exactly one flow0 application trace')
    app_bytes = sum(int(r['payload_bytes']) for r in read_rows(app_files[0])
                    if inside(r) and r['flow_id'] == '0')
    packets = Counter()
    payload_bytes = Counter()
    for row in read_rows(logs / 'tcp_flow_0_study_packets.csv'):
        if inside(row):
            packets[row['event']] += 1
            payload_bytes[row['event']] += int(row['payload_bytes'])
    events = Counter(r['event'] for r in read_rows(logs / 'tcp_flow_0_study_events.csv')
                     if inside(r))
    drops = [r for r in read_rows(logs / 'study_drops.csv') if inside(r)]
    tagged = {(r['flow_id'], r['tx_id']) for r in drops
              if r['flow_id'] and r['tx_id'] and int(r['tx_id']) > 0}
    by_device = Counter((r['layer'], r['node'], r['device']) for r in drops)
    qresult = None
    if queue_file:
        # A bin is included only when fully contained. The declared windows
        # align with the original 100-ms bins, avoiding partial-bin estimates.
        grouped = defaultdict(lambda: Counter())
        flush = defaultdict(list)
        for row in read_rows(queue_file):
            if row['flow_id'] != '0':
                continue
            key = (int(row['node_id']), int(row['device_id']))
            if start <= int(row['bin_start_ns']) and int(row['bin_end_ns']) <= end:
                c = grouped[key]
                for field in ['enqueued', 'dequeued', 'drop_before', 'drop_after',
                              'sojourn_samples', 'sojourn_sum_ns']:
                    c[field] += int(row[field])
                c['sojourn_max_ns'] = max(c['sojourn_max_ns'], int(row['sojourn_max_ns']))
            # Occupancy is a device-global value at its explicit flush time,
            # even though queue-service counters above are flow-tag-specific.
            if 'flush_time_ns' in row and start <= int(row['flush_time_ns']) < end:
                flush[key].append(dict(time_ns=int(row['flush_time_ns']),
                                       queue_packets=int(row['queue_packets_at_flush']),
                                       queue_bytes=int(row['queue_bytes_at_flush'])))
        qresult = []
        for key in sorted(set(grouped) | set(flush)):
            c = grouped[key]
            n = c['sojourn_samples']
            qresult.append(dict(node_id=key[0], device_id=key[1], **dict(c),
                                served_mean_ms=c['sojourn_sum_ns'] / n / 1e6 if n else None,
                                served_max_ms=c['sojourn_max_ns'] / 1e6 if n else None,
                                occupancy_at_flush_observations=sorted(flush[key], key=lambda r: r['time_ns'])))
    return dict(start_ns=start, end_ns=end, duration_s=(end-start)/1e9,
                application_bytes=app_bytes, application_goodput_mbps=app_bytes*8/(end-start)*1000,
                sender_event_counts=dict(packets), sender_event_payload_bytes=dict(payload_bytes),
                congestion_event_counts=dict(events), all_direction_drop_rows=len(drops),
                distinct_tagged_drop_transmissions=len(tagged),
                drop_rows_by_layer=dict(Counter(r['layer'] for r in drops)),
                drop_rows_by_device=[dict(layer=k[0], node=k[1], device=k[2], rows=v)
                                     for k, v in sorted(by_device.items())],
                exact_drop_rows=drops, tagged_flow0_device_queue_visits=qresult,
                cwnd_bytes_trace=held_trace(logs/'tcp_flow_0_cwnd.csv', start, end),
                srtt_ns_trace=held_trace(logs/'tcp_flow_0_rtt.csv', start, end))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--path-truth', type=Path, required=True)
    parser.add_argument('--queue-csv', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite output')
    run = args.run.resolve()
    logs = run / 'logs_ns3'
    manifest_path = next((run / name for name in ('manifest.json', 'case.json')
                          if (run / name).is_file()), None)
    if manifest_path is None:
        raise ValueError('Missing completed manifest')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('status') not in ('success', 'complete') or manifest.get('exit_code') != 0:
        raise ValueError('Incomplete or failed run')
    queue_file = args.queue_csv
    if queue_file is None:
        matches = list(logs.glob('*queue_bins.csv'))
        if len(matches) > 1:
            raise ValueError('Ambiguous queue traces; select --queue-csv')
        queue_file = matches[0] if matches else None
    config_path = run / 'config_ns3.properties'
    config = dict(line.split('=', 1) for line in config_path.read_text().splitlines()
                  if line and not line.startswith('#'))
    duration = int(config['simulation_end_time_ns'])
    sources = [manifest_path, args.path_truth, config_path, run/'schedule.csv',
               logs / 'study_drops.csv', logs / 'tcp_flow_0_study_packets.csv',
               logs / 'tcp_flow_0_study_events.csv']
    sources += list(logs.glob('study_app_rx_node_*_port_1024.csv'))
    sources += [p for p in (logs/'tcp_flow_0_cwnd.csv', logs/'tcp_flow_0_rtt.csv') if p.is_file()]
    if queue_file:
        sources.append(queue_file)
    for path in sources:
        if not path.is_file():
            raise ValueError('Missing input: ' + str(path))
    output_hashes = manifest.get('output_files', {})
    checks = []
    for path in sources:
        if path.is_relative_to(run) and path != manifest_path:
            rel = str(path.relative_to(run))
            receipt = output_hashes.get(rel)
            if receipt:
                recorded = receipt['sha256'] if isinstance(receipt, dict) else receipt
                actual = digest(path)
                if actual != recorded:
                    raise ValueError('Manifest output mismatch: ' + rel)
                checks.append(dict(file=rel, sha256=actual, matches=True))
    selected = []
    for event in route_events(args.path_truth):
        t = event['time_ns']
        if t + 2_000_000_000 > duration:
            continue
        event['windows'] = {
            'pre': metrics(logs, t-500_000_000, t, queue_file),
            'post': metrics(logs, t, t+500_000_000, queue_file),
            'legacy': metrics(logs, t-500_000_000, t+2_000_000_000, queue_file),
            'tight_legacy': metrics(logs, t-100_000_000, t+400_000_000, queue_file),
        }
        selected.append(event)
    report = dict(schema_version=1, run=str(run), duration_ns=duration,
                  actual_config=config,
                  original_manifest={k: v for k, v in manifest.items()
                                     if k not in ('output_files', 'state_static_sha256', 'dynamic_input_sha256')},
                  state_mapping_receipts={k: dict(count=len(manifest[k]),
                      sha256=hashlib.sha256(json.dumps(manifest[k], sort_keys=True,
                                                     separators=(',', ':')).encode()).hexdigest())
                      for k in ('state_static_sha256', 'dynamic_input_sha256') if k in manifest},
                  events=selected, queue_trace_available=bool(queue_file),
                  manifest_output_checks=checks,
                  sources=[source_record(p) for p in sources],
                  helper=source_record(Path(__file__).resolve()),
                  causal_gate='Manual evidence assessment required; this extractor never labels shortening as overflow.',
                  limits=[
                      'Windows are half-open. Sender events and ordered app bytes are separate.',
                      'No queue trace means queue surge is unmeasured, not zero.',
                      'Queue visits are flow0-tagged served visits at each device, not end-to-end queue delay.',
                      'Flush occupancy is device-global at flush_time_ns, not a bin boundary snapshot.',
                      'A route snapshot changes more than geometric propagation; no pure-shortening causality is inferred.',
                      'Existing-run output hash checks depend on available original receipt fields.',
                  ])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', newline='\n')
    print(json.dumps(dict(out=str(args.out), events=len(selected), sha256=digest(args.out))))


if __name__ == '__main__':
    main()
