"""Check published provenance/counts/table/figure links without rerunning TCP."""
import csv
import hashlib
import json
from pathlib import Path

root=Path(__file__).parent
ev=root/'evidence'
def j(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rows=list(csv.DictReader((ev/'results.csv').open()))
assert len(rows)==52 and len({r['case'] for r in rows})==8
for r in rows:
    assert not r['jain'] or int(r['start_ns'])>=80000000000
    assert 0<=float(r['goodput_mbps'])<=100
for folder in (ev/'cases').iterdir():
    m=j(folder/'case.json')
    assert m['status']=='complete' and m['exit_code']==0 and not m['source_worktree_dirty']
    assert m['source_commit']=='7ac0751235dc1ecb14b3042622ac50990429f17c'
    assert m['patch_sha256']==sha(root/'ns3.patch')
    assert m['binary_sha256']==m['binary']['sha256']
    assert not m['policy']['recent_min_renewal']
audit=j(ev/'a1-audit-final.json')
assert audit['status']=='pass' and audit['audit_source_sha256']==sha(root/'audit_adaptive.py')
assert sum(r.get('checked_decisions',0) for r in audit['audit'])==8704
assert sum(r['vegas_rows'] for r in audit['audit'])==17533
compat=j(ev/'a1-baseline-final.json')
assert compat['status']=='pass' and compat['parameters_match']
assert sum(len(c['checks']) for c in compat['cases'])==75
assert all(r['match'] for c in compat['cases'] for r in c['checks'])
replay=j(ev/'a1-replay-publication.json')
assert replay['status']=='pass' and replay['replay_source_binary_libraries_parameters_match']
assert len(replay['comparison'])==27 and all(r['equal'] for r in replay['comparison'])
sources=j(ev/'figures/sources.json')
for name,digest in sources.items():
    p=root/name if name=='plot_results.py' else ev/name
    assert sha(p)==digest, name
receipt=j(ev/'raw-archive-receipt.json')
inventory=j(ev/'raw-inventory.json')
assert receipt['verified_file_count']==inventory['file_count']==285
assert receipt['inventory_sha256']==sha(ev/'raw-inventory.json')
release=j(ev/'raw-publication.json')
assert release['asset']['size']==receipt['archive_bytes']==1214998496
assert release['asset']['digest']=='sha256:'+receipt['archive_sha256']
assert release['asset']['state']=='uploaded'
assert release['release']['target_commitish']=='7ac0751235dc1ecb14b3042622ac50990429f17c'
print(json.dumps({'status':'pass','primary_cases':8,'state_rows':17533,'adaptive_decisions':8704,
                  'baseline_measurement_files':75,'fresh_replay_measurement_files':27,'archive_files':285,
                  'figure_sources_match':True,'github_asset_digest_matches':True}))
