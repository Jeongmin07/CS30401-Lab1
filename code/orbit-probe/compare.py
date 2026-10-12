#!/usr/bin/env python3
"""Compare matched OFF/ON execution identities and actual measurement hashes."""
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
    p.add_argument('--root', type=Path, default=Path('/tmp/orbit-probe'))
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Output must be new')
    pairs = []
    for family in ('solo40', 'rise140'):
        runs = [a.root / (family + '-' + mode) for mode in ('off', 'on')]
        records = [json.loads((run / 'manifest.json').read_text()) for run in runs]
        if not all(r['status'] == 'success' and r['returncode'] == 0 for r in records):
            raise ValueError('Incomplete pair: ' + family)
        if records[0]['definition']['policy'] or not records[1]['definition']['policy']:
            raise ValueError('Policy flags are not OFF/ON')
        keys = ('runner_sha256', 'patch_sha256', 'installed_diff_sha256', 'runtime_files', 'config_sha256',
                'schedule_sha256', 'state_static_sha256', 'dynamic_state_sha256', 'forecast_source_sha256',
                'forecast_sha256', 'sim_seconds', 'rate_mbps', 'queue_packets', 'seed', 'windows')
        if any(records[0][key] != records[1][key] for key in keys):
            raise ValueError('Unmatched source/runtime/settings: ' + family)
        for run, record in zip(runs, records):
            for name, expected in record['outputs'].items():
                path = run / name
                if path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
                    raise ValueError('Changed actual output: ' + str(path))
        files = [{name for name in r['outputs'] if name.endswith('.csv') and Path(name).name not in ('timing_results.csv', 'orbit_probe.csv')} for r in records]
        if not files[0] or files[0] != files[1]:
            raise ValueError('Measurement sets differ')
        checks = [{'path': name, 'off_sha256': records[0]['outputs'][name]['sha256'],
                   'on_sha256': records[1]['outputs'][name]['sha256'],
                   'equal': records[0]['outputs'][name] == records[1]['outputs'][name]} for name in sorted(files[0])]
        pairs.append({'family': family, 'matched_fields': list(keys), 'all_measured_csv_equal': all(c['equal'] for c in checks),
                      'checks': checks, 'execution_manifest_sha256': [sha(run / 'manifest.json') for run in runs],
                      'scope': 'Timing and controller decision CSVs excluded from behavioral equality; all raw output SHA/size independently checked.'})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({'tool_sha256': sha(__file__), 'pairs': pairs}, indent=2) + '\n')
    print(json.dumps([(r['family'], r['all_measured_csv_equal'], len(r['checks'])) for r in pairs]))


if __name__ == '__main__':
    main()
