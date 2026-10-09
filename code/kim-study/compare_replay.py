"""Compare every replay raw analysis input against published SHA-256 records."""
import argparse
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs-root', type=Path, default=Path('/tmp/cs30401-study'))
parser.add_argument('--out', type=Path, default=root/'reproduction_v5.json')
args = parser.parse_args()

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

records, analyses = [], []
for case in sorted((root/'evidence'/'cases').iterdir()):
    summary = json.loads((case/'summary.json').read_text())
    manifest = json.loads((args.runs_root/case.name/'case.json').read_text())
    inputs = summary['publication_export']['raw_inputs'] + summary['publication_export'].get('legacy_inputs', [])
    for item in inputs:
        original_path = Path(item['path'])
        assert original_path.parent.name == 'logs_ns3'
        relative = Path('logs_ns3')/original_path.name
        target = args.runs_root/case.name/relative
        actual = digest(target)
        records.append({'case':case.name, 'kind':item['kind'], 'relative_file':str(relative),
                        'original_sha256':item['sha256'], 'replayed_sha256':actual,
                        'identical':actual == item['sha256']})
    assert manifest['status'] == 'complete' and manifest['exit_code'] == 0
    analysis_path = args.runs_root/case.name/'study_analysis.json'
    expected = summary['publication_export']['full_analysis_sha256']
    actual = digest(analysis_path)
    analyses.append({'case':case.name, 'original_sha256':expected, 'replayed_sha256':actual,
                     'identical':actual == expected})
record = {'checked_case_count':len({r['case'] for r in records}), 'checked_input_count':len(records),
          'checked_analysis_count':len(analyses),
          'all_identical':all(r['identical'] for r in records+analyses), 'records':records,
          'analysis_records':analyses,
          'scope':'Checks full sender, receiver, receiver application, congestion-state and drop inputs plus any recorded legacy cwnd, SRTT and sender-progress traces. Does not prove all loss paths are instrumented or generality to other scenarios.'}
args.out.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('records','analysis_records')}))
raise SystemExit(not record['all_identical'])
