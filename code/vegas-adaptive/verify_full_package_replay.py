"""Compare the complete Git-free replay to preserved primary raw fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--reference', type=Path, required=True)
p.add_argument('--replay-root', type=Path, default=Path('/tmp/vegas-sensitivity'))
p.add_argument('--regenerated', type=Path, required=True)
p.add_argument('--figures', type=Path, required=True)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--baseline-analysis', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
assert not a.out.exists()

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text())

ref = a.reference / 'sensitivity-evidence'
inventory = read(ref / 'raw-inventory.json')
measurements = [x for x in inventory['files'] if '/logs_ns3/' in x['path']
                and x['path'].endswith('.csv') and not x['path'].endswith('timing_results.csv')]
assert measurements
cases = sorted({x['path'].split('/')[0] for x in measurements})
assert len(cases) == 10
actual_paths = {x.relative_to(a.replay_root).as_posix() for case in cases
                for x in (a.replay_root / case / 'logs_ns3').glob('*.csv')
                if x.name != 'timing_results.csv'}
assert actual_paths == {x['path'] for x in measurements}
checks = []
for item in measurements:
    actual = a.replay_root / item['path']
    assert actual.stat().st_size == item['bytes'], item['path']
    assert sha(actual) == item['sha256'], item['path']
    checks.append(item)
for case in cases:
    old = read(ref / 'cases' / case / 'case.json')
    new = read(a.replay_root / case / 'case.json')
    assert new['status'] == 'complete' and new['exit_code'] == 0
    assert new['source_verification'] == 'exported_hash_inventory'
    assert new['source_commit'] == '1deee988a37325c230a389ad4e6dafc518fc138f'
    for key in ('binary', 'shared_libraries', 'patch_sha256', 'official_image_digest', 'policy'):
        assert old[key] == new[key], (case, key)
    omit = {'source_manifest'}
    assert {k:v for k,v in old['parameters'].items() if k not in omit} == {
        k:v for k,v in new['parameters'].items() if k not in omit}, case
    source_omit = {'/work/code/vegas-adaptive/run_case.py'}
    assert [x for x in old['sources'] if x['path'] not in source_omit] == [
        x for x in new['sources'] if x['path'] not in source_omit], case
    old_summary = read(ref / 'cases' / case / 'summary.json')
    new_summary = read(a.replay_root / 'analysis' / case / 'summary.json')
    assert old_summary['windows'] == new_summary['windows'], case
assert sha(ref / 'results.csv') == sha(a.regenerated / 'results.csv')
audit = read(a.regenerated / 'verification.json')
assert audit['status'] == 'PASS' and not audit['errors']
assert audit['case_count'] == 10 and audit['state_rows'] == 21840 and audit['renewals'] == 101
assert audit['compatibility_file_count'] == 37
assert sha(ref / 'figures' / 'sensitivity.png') == sha(a.figures / 'sensitivity.png')
assert read(ref / 'figures' / 'sources.json') == read(a.figures / 'sources.json')
# PDF embeds generation-time metadata, so byte identity is not a scientific check.
assert (a.figures / 'sensitivity.pdf').stat().st_size > 0
baseline_inventory = read(a.reference / 'evidence' / 'raw-inventory.json')
baseline_files = [x for x in baseline_inventory['files'] if x['path'].startswith('a1-leo-base/logs_ns3/')
                  and x['path'].endswith('.csv') and not x['path'].endswith('timing_results.csv')]
assert baseline_files
for item in baseline_files:
    actual = a.baseline / Path(item['path']).relative_to('a1-leo-base')
    assert actual.stat().st_size == item['bytes'] and sha(actual) == item['sha256'], item['path']
old_baseline = read(a.reference / 'baseline-summary.json')
new_baseline = read(a.baseline_analysis / 'summary.json')
assert old_baseline['windows'] == new_baseline['windows']
result = dict(status='PASS', case_count=10, measurement_csv_count=len(checks),
    baseline_measurement_csv_count=len(baseline_files), baseline_windows_exact=True,
    state_rows=21840, renewals=101,
    historical_compatibility_csv_count=37, all_windows_exact=True, results_csv_exact=True,
    figure_png_exact=True, simulator_identity_exact=True,
    package_source_commit='1deee988a37325c230a389ad4e6dafc518fc138f',
    matrix_wall_s=read(a.replay_root / 'matrix.json')['end_unix']-read(a.replay_root / 'matrix.json')['start_unix'],
    checks=checks, baseline_checks=baseline_files,
    inputs={str(x.relative_to(a.reference)):sha(x) for x in [ref/'raw-inventory.json', ref/'results.csv',
        ref/'figures'/'sensitivity.png', a.reference/'evidence'/'raw-inventory.json',
        a.reference/'baseline-summary.json']},
    regenerated_audit_sha256=sha(a.regenerated/'verification.json'),
    script_sha256=sha(Path(__file__)),
    limits=['Deterministic reproduction, not independent statistical replication.',
            'Research source ZIP, not a final report/submission package.'])
a.out.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','baseline_checks','inputs')}, indent=2))
