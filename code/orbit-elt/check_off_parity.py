"""Check newly executed OFF controls against frozen PR16 checksums only."""
import argparse
import json
from pathlib import Path
import common as c

MAPPING={'micro20-stock':'micro-base','micro20-selective':'micro-selective',
         'micro20-tail':'micro-tail','micro21-selective':'micro21-selective',
         'micro21-tail':'micro21-tail','leo200-stock':'leo10-base','leo200-tail':'leo10-tail'}
p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path)
p.add_argument('--out',required=True,type=Path);p.add_argument('--cases',nargs='+',choices=MAPPING)
a=p.parse_args();assert not a.out.exists()
expected=json.loads((c.HERE/'deps/inputs/expected-parity.json').read_text())['cases']
records=[]
for name in (a.cases or MAPPING):
    run=a.root/name;m=json.loads((run/'manifest.json').read_text())
    assert m['status']=='success' and m['definition']['elt_mode']==0 and m['runtime_unchanged']
    for rel,known in expected[MAPPING[name]]['measurement_csvs'].items():
        pth=run/rel;actual=dict(bytes=pth.stat().st_size,sha256=c.sha(pth))
        records.append(dict(case=name,file=rel,equal=actual==known,actual=actual,expected=known))
c.write(a.out,dict(reference='PR16 frozen pace controls',case_count=len(a.cases or MAPPING),
    compared_files=len(records),all_equal=all(r['equal'] for r in records),checks=records))
print(json.dumps(dict(compared_files=len(records),all_equal=all(r['equal'] for r in records))))
assert all(r['equal'] for r in records), 'OFF behavior differs; preserve comparison receipt'
