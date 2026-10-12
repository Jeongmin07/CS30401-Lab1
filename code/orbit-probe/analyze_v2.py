#!/usr/bin/env python3
"""Audit V2 completed-ProbeRTT freshness and original measurement safeguards."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    with path.open(newline='') as source:
        return list(csv.DictReader(source))


def analyze(run, helper):
    manifest = json.loads((run / 'manifest.json').read_text())
    require(manifest['status'] == 'success' and manifest['returncode'] == 0, 'Incomplete execution')
    for name, expected in manifest['outputs'].items():
        path = run / name
        require(path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], 'Changed raw output: ' + name)
    for name, key in [('config_ns3.properties', 'config_sha256'), ('schedule.csv', 'schedule_sha256'), ('forecast.txt', 'forecast_sha256')]:
        require(sha(run / name) == manifest[key], 'Changed settings: ' + name)
    helper.WINDOWS = manifest['windows']
    record, _, devices = helper.analyze(run)
    rows = read(run / 'logs_ns3/orbit_probe.csv')
    require(rows and all(int(r['flow_id']) == 0 and bool(int(r['policy_enabled'])) == manifest['definition']['policy'] for r in rows), 'Policy/flow identity mismatch')
    require(all(int(r['min_rtt_filter_ns']) == 10_000_000_000 and int(r['probe_duration_ns']) == 200_000_000 for r in rows), 'Changed default measurement durations')
    probes, active, decisions, previous = [], None, [], -1
    for row in rows:
        time, event = int(row['time_ns']), row['event']
        require(time >= previous, 'Orbit trace is not chronological')
        previous = time
        require('last_probe_complete_ns' in row and 0 <= int(row['cong_state']) <= 4, 'Expected V2 completion/congestion provenance')
        if event.startswith('HINT_'):
            require(manifest['definition']['policy'] and time >= int(row['hint_ready_ns']) >= int(row['hint_event_ns']), 'Invalid forecast decision time')
            decisions.append(row)
            if event == 'HINT_INVALIDATE':
                require(int(row['last_probe_complete_ns']) < int(row['hint_event_ns']) and int(row['bbr_state']) == 2, 'Invalid completed-probe gate request')
        elif event == 'PROBE_ENTER':
            require(active is None and int(row['bbr_state']) == 3, 'Overlapping or invalid ProbeRTT')
            active = dict(start_ns=time, enter=row, samples=[])
        elif event == 'PROBE_DRAINED':
            require(active is not None and 'drained_ns' not in active and int(row['inflight_bytes']) <= int(row['min_pipe_cwnd_bytes']), 'Invalid drain')
            require(int(row['probe_done_ns']) == time + 200_000_000, 'Low-inflight duration was shortened')
            active.update(drained_ns=time, drain=row)
        elif event == 'PROBE_COMPLETE':
            require(int(row['last_probe_complete_ns']) == time, 'Incomplete completion timestamp')
            require(active is not None and 'drained_ns' in active and int(row['probe_round_done']) == 1 and time > int(row['probe_done_ns']), 'Invalid completed ProbeRTT')
            after = [s for s in active['samples'] if int(s['time_ns']) > active['drained_ns']]
            active.update(end_ns=time, residence_s=(time-active['start_ns'])/1e9,
                          low_inflight_s=(time-active['drained_ns'])/1e9,
                          accepted_samples_after_drain=len(after),
                          minimum_accepted_rtprop_after_drain_ns=min((int(s['rtprop_ns']) for s in after), default=None),
                          completion=row, censored=False)
            require(after, 'No accepted RTT samples after draining')
            active.pop('samples')
            probes.append(active)
            active = None
        elif event == 'RTPROP_SAMPLE':
            require(int(row['last_rtt_ns']) > 0 and int(row['rtprop_ns']) == int(row['last_rtt_ns']), 'Installed RTprop differs from measured sample')
            if active is not None:
                active['samples'].append(row)
        else:
            raise ValueError('Unknown orbit event: ' + event)
    if active is not None:
        active.update(end_ns=None, censored=True)
        active.pop('samples')
        probes.append(active)
    states = read(run / 'logs_ns3/bbr_state.csv')
    probe_states = [r for r in states if int(r['bbr_state']) == 3]
    require(all(int(r['cwnd_bytes']) <= 5520 for r in probe_states), 'ProbeRTT cwnd exceeds original four 1380-byte MSS')
    record.update(exact_probe_intervals=probes, policy_decisions=decisions,
                  probe_cwnd_cap_bytes=5520, probe_sample_rows=len(probe_states),
                  measured_sample_installation_verified=True,
                  orbit_trace={'sha256': sha(run / 'logs_ns3/orbit_probe.csv'), 'rows': len(rows)})
    return record, devices


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', type=Path, nargs='+')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    require(not a.out.exists(), 'Output directory must be new')
    source = HERE.parent / 'bbr-route/analyze_pilot.py'
    spec = importlib.util.spec_from_file_location('passive_bbr', source)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.sha = sha  # Same digest, streamed rather than loading entire CSVs.
    records, all_devices, windows = [], [], []
    for run in a.runs:
        record, devices = analyze(run, helper)
        records.append(record)
        all_devices.extend(devices)
        for window in record['windows']:
            windows.append({k: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v for k, v in window.items()})
    a.out.mkdir(parents=True)
    for run, record in zip(a.runs, records):
        target = a.out / 'cases' / run.name
        target.mkdir(parents=True)
        for name in ('manifest.json', 'config_ns3.properties', 'schedule.csv', 'forecast.txt'):
            shutil.copy2(run / name, target / name)
        (target / 'summary.json').write_text(json.dumps(record, indent=2) + '\n')
        shutil.copy2(run / 'logs_ns3/orbit_probe.csv', target / 'orbit_probe.csv')
    for name, values in [('windows.csv', windows), ('device-queues.csv', all_devices)]:
        with (a.out / name).open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=list(values[0]))
            writer.writeheader(); writer.writerows(values)
    report = {'analyzer_sha256': sha(__file__), 'passive_helper_sha256': sha(source), 'cases': records,
              'limits': ['TcpBbr is the provided BBRv1 family, not modern BBRv3.',
                         'Operator hints are ideal geometry information; two-direction propagation RTT does not prove queue clearance.',
                         'RTprop installations are accepted TCP lastRtt samples, which may be quantized and cache the latest RTT observation; no geometry value is installed.',
                         'Per served device-queue visit includes zero waits and both data/ACK directions, not end-to-end queue latency.',
                         'Drop layers are hook-event counts, not distinct physical packet losses.',
                         'Sparse bbr_state rows are sample-hold traces; exact ProbeRTT lifecycle is separately instrumented.',
                         'Early filter invalidation is the policy; filter length remains ten seconds and the original measurement conditions are retained.',
                         'No random repetitions, competition, predictor error study or deployment validation.']}
    (a.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    receipt = {'inputs': [{'run': str(run), 'manifest_sha256': sha(run / 'manifest.json')} for run in a.runs],
               'outputs': [{'path': str(path.relative_to(a.out)), 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in sorted(a.out.rglob('*')) if path.is_file()]}
    (a.out / 'analysis-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(a.out)


if __name__ == '__main__':
    main()
