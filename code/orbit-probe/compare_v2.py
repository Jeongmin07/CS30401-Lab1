#!/usr/bin/env python3
"""Verify a same-binary V2 pair, disclosing the runner-only build-guard repair."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--off', type=Path, required=True)
    p.add_argument('--on', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Output must be new')
    runs = [a.off, a.on]
    records = [json.loads((run / 'manifest.json').read_text()) for run in runs]
    if not all(r['status'] == 'success' and r['returncode'] == 0 for r in records):
        raise ValueError('Incomplete execution')
    if records[0]['definition']['policy'] or not records[1]['definition']['policy']:
        raise ValueError('Not OFF/ON')
    keys = ('patch_sha256', 'installed_diff_sha256', 'runtime_files', 'config_sha256', 'schedule_sha256',
            'state_static_sha256', 'dynamic_state_sha256', 'forecast_source_sha256', 'forecast_sha256',
            'sim_seconds', 'rate_mbps', 'queue_packets', 'seed', 'windows')
    if any(records[0][key] != records[1][key] for key in keys):
        raise ValueError('Unmatched NS3 source/runtime/inputs')
    normalize = lambda r: ['--run_dir=CASE' if w.startswith('--run_dir=') else '--ns3::TcpBbr::OrbitProbe=POLICY' if w.startswith('--ns3::TcpBbr::OrbitProbe=') else w for w in r['command']]
    if normalize(records[0]) != normalize(records[1]):
        raise ValueError('Unexpected command difference')
    for run, r in zip(runs, records):
        for name, expected in r['outputs'].items():
            path = run / name
            if path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
                raise ValueError('Changed raw: ' + name)
        header = (run / 'logs_ns3/orbit_probe.csv').open().readline().strip().split(',')
        if 'last_probe_complete_ns' not in header or 'cong_state' not in header:
            raise ValueError('Invalid V2 runtime trace')
    archive_runner = Path(__file__).with_name('run-v2-before-guard.py')
    guarded_sha = sha(Path(__file__).with_name('run_v2.py'))
    if records[1]['runner_sha256'] not in (sha(archive_runner), guarded_sha) or records[0]['runner_sha256'] != guarded_sha:
        raise ValueError('Unresolved runner source attribution')
    record = {'matched_ns3_binary_libraries_source_and_inputs': True, 'actual_v2_trace_headers_verified': True,
              'normalized_commands_equal': True, 'matched_fields': list(keys),
              'manifest_sha256': [sha(run / 'manifest.json') for run in runs],
              'runner_sha256': [r['runner_sha256'] for r in records],
              'runner_difference': 'Both executions use the same guarded runner.' if records[0]['runner_sha256'] == records[1]['runner_sha256'] else 'OFF uses a pending-build/runtime-before-and-after guard; ON used the preserved pre-guard runner. Commands and actual NS3 binaries/libraries/patch/inputs match; both V2 trace headers verified. Invalid earlier OFF excluded separately.',
              'tool_sha256': sha(__file__)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(record, indent=2) + '\n')
    print('PASS same V2 runtime, source, normalized command, config/schedule/forecast/state inputs and actual output hashes')


if __name__ == '__main__':
    main()
