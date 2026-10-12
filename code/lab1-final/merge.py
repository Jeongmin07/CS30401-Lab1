"""Merge the two fresh profiles without turning aliases into repeated runs."""
import argparse
import json
from pathlib import Path
import common as c

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pace',type=Path,required=True)
    p.add_argument('--bp',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
    pace,bp=[json.loads(path.read_text()) for path in [a.pace,a.bp]]
    assert pace['profile']=='pace' and bp['profile']=='bp' and not(set(pace['cases'])&set(bp['cases']))
    cases={**pace['cases'],**bp['cases']};assert set(cases)==set(c.CASES) and len(cases)==19
    proofs={**pace['parity'],**bp['parity']};assert all(p['all_exact'] for p in proofs.values())
    mapping={name:name for name in cases};mapping.update(c.ALIASES);assert len(mapping)==22
    out=dict(schema=1,phase='Fresh independent-volume course replay',report_roles=c.ROLES,cases=cases,
        mapped_conditions=mapping,physical_conditions=19,mapped_condition_count=22,aliases_are_not_simulations=True,
        parity=proofs,qa=dict(pace=pace['qa'],bp=bp['qa']),
        profile_sources=[c.receipt(a.pace),c.receipt(a.bp)],tool=c.receipt(Path(__file__)))
    c.write(a.out,out);print(json.dumps({'out':str(a.out),'physical_conditions':19,'mapped_conditions':22,'all_frozen_csv_parity':True}))
