"""Produce a portable, complete measurement receipt for one representative case."""
import argparse
import hashlib
import json
from pathlib import Path
from pr14_audit_mechanism import Audit

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--run',type=Path,required=True)
p.add_argument('--analysis',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
m=json.loads((a.run/'case.json').read_text())
assert m['status']=='complete' and m['exit_code']==0
s=json.loads((a.analysis/'summary.json').read_text())
audit=Audit(a.run.parent)
audit.manifests[a.run.name]=m
audit.audit_state(a.run.name)
assert not audit.errors,audit.errors
files={x.name:dict(bytes=x.stat().st_size,sha256=sha(x))
       for x in sorted((a.run/'logs_ns3').glob('*.csv')) if x.name!='timing_results.csv'}
assert files
result=dict(case=a.run.name,manifest=m,measurement_files=files,
            windows=s['windows'],state_audit=audit.case_summaries[a.run.name],
            state_inputs=audit.inputs,analysis_sha256=sha(a.analysis/'summary.json'),
            script_sha256=sha(Path(__file__)))
a.out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(case=a.run.name,measurement_files=len(files),state_rows=result['state_audit']['rows'])))
