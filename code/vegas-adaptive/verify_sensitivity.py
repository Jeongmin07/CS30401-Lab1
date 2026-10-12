"""Audit declared settings, historical compatibility, rules, and export all results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
from pr14_audit_mechanism import Audit

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, default=Path('/tmp/vegas-sensitivity'))
p.add_argument('--references', type=Path, default=Path(__file__).with_name('pr14-renewal-references.json'))
p.add_argument('--out', type=Path, required=True)
p.add_argument('--expected-source-commit', default='fbc0b2b01055e51ccfdd0ea33606301e8c9ae4b0')
a = p.parse_args()
assert not a.out.exists(), 'Refuse existing audit/export'
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()
matrix = json.loads((a.root / 'matrix.json').read_text())
expected = {f's1-{family}-r{r}' for family in ('leo', 'fixed-comp', 'rate50') for r in (10,20,40)} | {'s1-rate50-base'}
assert matrix['status'] == 'complete'
assert {t['case'] for t in matrix['tasks']} == expected
assert {t['case'] for t in matrix['results']} == expected and len(matrix['results']) == len(expected)
assert all(t['exit_code'] == t['analysis_exit_code'] == 0 for t in matrix['results'])
audit = Audit(a.root)
summaries, manifests = {}, {}
for name in sorted(expected):
    run = a.root / name
    m = json.loads((run / 'case.json').read_text())
    manifests[name] = m
    params = m['parameters']
    family = name[len('s1-'):].rsplit('-',1)[0]
    suffix = name.rsplit('-',1)[1]
    rounds = int(suffix[1:]) if suffix.startswith('r') else 20
    assert m['status'] == 'complete' and m['exit_code'] == 0 and not m['source_worktree_dirty']
    assert m['source_commit'] == a.expected_source_commit
    assert m['patch_sha256'] == '849ae664d01a0e084dfaaae764aff81c76333ae31c07c97eae0300cd56a0a0db'
    assert m['official_image_digest'] == 'sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
    assert m['policy']['recent_min_renewal'] == (suffix != 'base')
    assert not m['policy']['adaptive_thresholds'] and m['policy']['rounds'] == rounds
    assert m['policy']['min_rise_ns'] == 1000000
    assert params['rate'] == (50 if family == 'rate50' else 100)
    assert params['queue'] == 100 and params['duration'] == 200 and params['seed'] == 123456789
    assert params['competitor'] == (family == 'fixed-comp')
    assert params['kind'] == ('micro' if family == 'fixed-comp' else 'leo')
    for filename in ('config_driver.json', 'config_ns3.properties', 'schedule.csv'):
        if (run/filename).exists():
            assert sha(run/filename) == m[filename+'_sha256']
    audit.manifests[name] = m
    audit.audit_state(name)
    s = json.loads((a.root/'analysis'/name/'summary.json').read_text())
    summaries[name] = s
    for artifact in s['input_artifacts']:
        path = Path(artifact['path'])
        assert sha(path) == artifact['sha256']
    assert len(audit.renewal_rows[name]) == s['vegas_internal_state']['renewal_count']
assert not audit.errors, audit.errors

compatibility=[]
for old in json.loads(a.references.read_text())['cases']:
    name=old['case'].replace('v1-', 's1-').replace('-renew','-r20')
    old_params=old['original_manifest']['parameters']
    new_params=manifests[name]['parameters']
    omit={'name','root','adaptive','source_manifest'}
    assert {k:v for k,v in old_params.items() if k not in omit} == {k:v for k,v in new_params.items() if k not in omit}
    checks=[]
    for r in old['files']:
        rel=r['relative_path']
        if not rel.startswith('logs_ns3/') or not rel.endswith('.csv') or rel.endswith('timing_results.csv'):
            continue
        actual=a.root/name/rel
        checks.append(dict(file=rel,bytes=actual.stat().st_size,sha256=sha(actual),
                           match=actual.stat().st_size==r['bytes'] and sha(actual)==r['sha256']))
    assert checks and all(x['match'] for x in checks)
    compatibility.append(dict(reference=old['case'],case=name,checks=checks))

a.out.mkdir(parents=True)
rows=[]
for name,s in sorted(summaries.items()):
    folder=a.out/'cases'/name
    folder.mkdir(parents=True)
    for src in (a.root/name/'case.json', a.root/'analysis'/name/'summary.json', a.root/'analysis'/name/'windows.csv'):
        shutil.copy2(src, folder/src.name)
    m=manifests[name]
    for w in s['windows']:
        rates=[v['application_goodput_mbps'] for v in w['flows'].values()]
        fair=len(rates)>1 and all(v['active_duration_ns']==w['end_ns']-w['start_ns'] for v in w['flows'].values())
        q=[v for v in w.get('queue_sojourn',[]) if v['direction']=='forward' and v['group']=='all']
        rows.append(dict(case=name,window=w['window'],start_ns=w['start_ns'],end_ns=w['end_ns'],
            rate_mbps=m['parameters']['rate'],renewal=m['policy']['recent_min_renewal'],rounds=m['policy']['rounds'],
            vegas_mbps=w['flows']['0']['application_goodput_mbps'],
            cubic_mbps=w['flows'].get('1',{}).get('application_goodput_mbps'),
            aggregate_mbps=w['application_sum_goodput_mbps'],
            jain=sum(rates)**2/(len(rates)*sum(v*v for v in rates)) if fair and sum(rates) else None,
            queue_mean_ms=q[0]['mean_ns']/1e6 if q else None,
            TcDrop=w['drop_rows_by_layer'].get('TcDrop',0),
            vegas_retransmissions=w['flows']['0']['official_retransmission_rows'],
            renewals_whole=s['vegas_internal_state']['renewal_count']))
with (a.out/'results.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
selected={r['case']:r for r in rows if r['window']==('common' if 'fixed-comp' in r['case'] else 'whole')}
ref_leo,ref_comp=selected['s1-leo-r20'],selected['s1-fixed-comp-r20']
comparisons=[]
for rounds in (10,40):
    leo,comp=selected[f's1-leo-r{rounds}'],selected[f's1-fixed-comp-r{rounds}']
    advantages=[leo['vegas_mbps']-ref_leo['vegas_mbps'],comp['aggregate_mbps']-ref_comp['aggregate_mbps'],
                comp['jain']-ref_comp['jain'],ref_comp['queue_mean_ms']-comp['queue_mean_ms']]
    comparisons.append(dict(rounds=rounds,advantages_higher_is_better=advantages,
                            dominates_r20=all(x>=0 for x in advantages) and any(x>0 for x in advantages)))
result=dict(status='PASS',case_count=len(expected),launch_commit=next(iter(manifests.values()))['source_commit'],
            state_rows=sum(v['rows'] for v in audit.case_summaries.values()),
            renewals=sum(len(v) for v in audit.renewal_rows.values()),errors=audit.errors,
            compatibility=compatibility,compatibility_file_count=sum(len(c['checks']) for c in compatibility),
            state_cases=audit.case_summaries,state_inputs=audit.inputs,
            primary_and_capacity_results=list(selected.values()),comparisons=comparisons,
            scripts={p.name:sha(p) for p in (Path(__file__),Path(__file__).with_name('pr14_audit_mechanism.py'))})
(a.out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copy2(a.root/'matrix.json',a.out/'matrix.json')
print(json.dumps({k:result[k] for k in ('status','state_rows','renewals','compatibility_file_count','primary_and_capacity_results','comparisons')},indent=2))
