"""Cross-check compact evidence, figures, archives, replay, and GitHub upload receipts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,default=Path(__file__).with_name('sensitivity-evidence'))
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists()
read=lambda rel:json.loads((a.evidence/rel).read_text(encoding='utf-8-sig'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
v=read('verification.json')
assert v['status']=='PASS' and v['case_count']==10 and v['state_rows']==21840 and v['renewals']==101 and not v['errors']
assert v['compatibility_file_count']==37 and all(x['match'] for c in v['compatibility'] for x in c['checks'])
rows=list(csv.DictReader((a.evidence/'results.csv').open()))
assert len(rows)==57 and len({r['case'] for r in rows})==10
for x in v['primary_and_capacity_results']:
    r=next(r for r in rows if r['case']==x['case'] and r['window']==x['window'])
    for field in ('vegas_mbps','cubic_mbps','aggregate_mbps','queue_mean_ms','jain'):
        assert (float(r[field]) if r[field] else None)==x[field]
fig=read('figures/sources.json')
assert sha(a.evidence/'results.csv')==fig['results_sha256']
replay=read('portable-replay-verification.json')
assert replay['status']=='PASS' and replay['measurement_csv_count']==26 and replay['negative_source_hash_check_passed']
for name,expected in replay['inputs'].items(): assert sha(a.evidence/name)==expected
full=read('full-package-replay.json')
assert full['status']=='PASS' and full['case_count']==10
assert full['measurement_csv_count']==155 and full['baseline_measurement_csv_count']==11
assert all(full[k] for k in ('all_windows_exact','results_csv_exact','figure_png_exact',
                             'simulator_identity_exact','baseline_windows_exact'))
assert sha(a.evidence/'full-package-replay'/'verification.json')==full['regenerated_audit_sha256']
assert sha(Path(__file__).with_name('verify_full_package_replay.py'))==full['script_sha256']
publication=read('publication.json')
assert publication['release']['draft'] is False and publication['release']['prerelease'] is True
assert publication['release']['tag_name']=='vegas-sensitivity-20261011'
assert publication['release']['target_commitish']==v['launch_commit']
checks=[]
for receipt_name,inventory_name,filename in (
    ('raw-archive-receipt.json','raw-inventory.json','vegas-sensitivity-20261011-raw.tar.gz'),
    ('replay-archive-receipt.json','replay-inventory.json','vegas-sensitivity-portable-replay.tar.gz')):
    receipt=read(receipt_name); inv=read(inventory_name)
    assert sha(a.evidence/inventory_name)==receipt['inventory_sha256']
    assert len(inv['files'])==inv['file_count']==receipt['verified_file_count']
    assert len({x['path'] for x in inv['files']})==len(inv['files'])
    asset=next(x for x in publication['assets'] if x['name']==filename)
    assert asset['state']=='uploaded' and asset['size']==receipt['archive_bytes']
    assert asset['digest']=='sha256:'+receipt['archive_sha256']
    checks.append(dict(name=filename,bytes=asset['size'],sha256=receipt['archive_sha256'],verified_files=inv['file_count']))
pkg=replay['package']; asset=next(x for x in publication['assets'] if x['name']==pkg['file'])
assert asset['state']=='uploaded' and asset['size']==pkg['bytes'] and asset['digest']=='sha256:'+pkg['sha256']
result=dict(status='PASS',cases=10,table_rows=len(rows),state_rows=21840,renewals=101,
            historical_measurement_csv_matches=37,fresh_replay_measurement_csv_matches=26,
            full_package_replay_measurement_csv_matches=155,full_package_baseline_csv_matches=11,
            archives=checks,package=pkg,release=publication['release']['html_url'],
            inputs={str(x.relative_to(a.evidence)):sha(x) for x in sorted(a.evidence.rglob('*')) if x.is_file() and x!=a.out},
            limitations=['One LEO path at two capacities; one fixed-path competition scenario.',
                'Full research workflow reproduced; final report/submission ZIP is still separate.',
                'No universal optimum or route/congestion discrimination; not the final report/submission.'])
a.out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='inputs'},indent=2))
