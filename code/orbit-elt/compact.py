"""Publish compact fresh metrics; retain full audited objects in the raw archive."""
import json
from pathlib import Path

here=Path(__file__).resolve().parent
source=here/'results/results.json'
data=json.loads(source.read_text())
out=dict(schema=1,source_analysis_tool=data['analysis_tool'],window_convention=data['window_convention'],cases=[])
for s in data['cases']:
    policies={}
    for name,p in s['policies'].items():
        policies[name]={k:v for k,v in p.items() if k not in ('events','source')}
    q=s['queue']
    out['cases'].append(dict(case=s['case'],definition=s['definition'],
        fct_s=s['fct_s'],transfer_complete=s['transfer_complete'],metrics=s['metrics'],
        queue_windows=q['windows'] if q else None,
        first_physical_drop=s['drops']['first_physical_drop'],policies=policies,
        manifest_sha256=s['provenance']['manifest']['sha256'],limitations=s['limitations']))
target=here/'results/metrics.json';assert not target.exists()
target.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',newline='\n')
print(json.dumps(dict(cases=len(out['cases']),bytes=target.stat().st_size)))
