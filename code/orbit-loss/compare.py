"""Verify paired provenance and produce scoped comparisons from compact exports."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def receipt(p):
    h=hashlib.sha256()
    with p.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''): h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def normalized_csv(path,omit=(),drop_events=()):
    with path.open() as f:
        reader=csv.DictReader(f)
        fields=[field for field in reader.fieldnames if field not in omit]
        h=hashlib.sha256(); rows=0
        for row in reader:
            if any(row.get('event','').startswith(prefix) for prefix in drop_events): continue
            h.update(json.dumps([row[field] for field in fields],separators=(',',':')).encode()+b'\n')
            rows+=1
        return dict(fields=fields,rows=rows,normalized_sha256=h.hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--raw',type=Path,default=Path('/tmp/orbit-loss-v2'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): raise ValueError('Output exists')
    summaries={q.parent.name:json.loads(q.read_text()) for q in (a.export/'cases').glob('*/summary.json')}
    manifests={n:json.loads((a.export/'cases'/n/'manifest.json').read_text()) for n in summaries}
    if len(summaries)!=7: raise ValueError('Expected seven final cases')
    first=next(iter(manifests.values()))
    assert all(m['patch_sha256']==first['patch_sha256'] and m['runtime_files']==first['runtime_files']
               and m['status']=='success' and m['runtime_unchanged'] for m in manifests.values())
    drop_base,drop_policy=[summaries[n]['injected_actual_drop'] for n in ['leo10-drop-base','leo10-drop-selective']]
    assert drop_base['selection']==drop_policy['selection']
    b,c=[manifests[n] for n in ['leo10-drop-base','leo10-drop-selective']]
    assert b['state_static_sha256']==c['state_static_sha256'] and b['dynamic_input_sha256']==c['dynamic_input_sha256']
    assert b['output_files']['config_ns3.properties']==c['output_files']['config_ns3.properties']
    schedules=[next(csv.reader((a.export/'cases'/n/'schedule.csv').open()))
               for n in ['leo10-drop-base','leo10-drop-selective']]
    assert schedules[0][:5]==schedules[1][:5]
    assert b['actual_drop_rule']==c['actual_drop_rule']
    assert drop_base['matched_physical_drop']==drop_policy['matched_physical_drop']
    pairs=[('micro-base','micro-selective'),('leo10-base','leo10-bounded20'),
           ('leo10-base','leo10-selective'),('leo10-drop-base','leo10-drop-selective')]
    comparisons=[]
    for baseline,policy in pairs:
        bm,pm=[summaries[n]['metrics'] for n in [baseline,policy]]
        metric='fct_s' if baseline.startswith('micro') else 'receiver_goodput_mbps'
        comparisons.append(dict(baseline=baseline,policy=policy,metric=metric,
            baseline_value=bm[metric],policy_value=pm[metric],delta=pm[metric]-bm[metric],
            delta_percent=(pm[metric]/bm[metric]-1)*100,
            extra_first_retx_after_drop_ns=(drop_policy['first_retransmission_after_drop_ns']-
                    drop_base['first_retransmission_after_drop_ns']) if 'drop' in baseline else None))
    historical=[]
    repo=Path(__file__).resolve().parents[2]
    for name,old_name in [('micro-base','loss-first-base'),('leo10-base','leo10-base'),
                          ('leo10-bounded20','leo10-forecast')]:
        old=repo/'docs/experiments/assets/20261012-forecast-loss/export/cases'/old_name/'summary.json'
        source=json.loads(old.read_text())
        checks=[]
        profiling=[]
        for item in source['provenance']['raw_inputs']:
            key='logs_ns3/'+Path(item['path']).name
            actual=manifests[name]['output_files'][key]
            if Path(item['path']).name=='timing_results.csv':
                profiling.append(dict(file=key,old_sha256=item['sha256'],new_sha256=actual['sha256'],
                                       qualification='Wall-clock profiling; excluded from measurement equality'))
                continue
            checks.append(dict(file=key,old_sha256=item['sha256'],new_sha256=actual['sha256'],
                               equal=item['sha256']==actual['sha256']))
        assert all(q['equal'] for q in checks)
        historical.append(dict(case=name,previous_case=old_name,source=receipt(old),checks=checks,
                               profiling_excluded=profiling))
    measurements=[]
    for item in summaries['leo10-bounded20']['provenance']['raw_inputs']:
        filename=Path(item['path']).name
        if filename=='timing_results.csv': continue
        left=a.raw/'leo10-bounded20/logs_ns3'/filename
        right=a.raw/'leo10-selective/logs_ns3'/filename
        if filename=='tcp_flow_0_study_packets.csv':
            x,y=[normalized_csv(path,omit=['threshold']) for path in [left,right]]
            scope='All fields retained except actual threshold column'
        elif filename=='tcp_flow_0_study_events.csv':
            x,y=[normalized_csv(path,omit=['threshold'],drop_events=['THRESHOLD_','BOUNDED_'])
                 for path in [left,right]]
            scope='All congestion/SSTHRESH rows retained; omit threshold column and policy setter/expiry events'
        else:
            x,y=[receipt(path) for path in [left,right]]
            x.pop('path'); y.pop('path'); scope='Raw byte-identical measurement'
        assert x==y, 'Natural trajectory differs: '+filename
        measurements.append(dict(file=filename,equal=True,scope=scope,left=x,right=y))
    record=dict(schema_version=1,tool=receipt(Path(__file__)),
        inputs=[receipt(a.export/'cases'/n/'summary.json') for n in sorted(summaries)],
        final_simulations=7,preliminary_v1_simulations=2,not_statistical_replicates=True,
        immutable_final_patch_sha256=first['patch_sha256'],all_final_runtime_files_equal=True,
        final_source_commits=sorted({m['repo_commit'] for m in manifests.values()}),
        comparisons=comparisons,historical_default_control_equivalence=historical,
        natural_bounded20_selective_trajectory=measurements,
        paired_actual_loss=dict(selection_equal=True,physical_drop_equal=True,inputs_config_endpoints_equal=True,
            selection=drop_base['selection'],baseline_drop_to_retx_ns=drop_base['first_retransmission_after_drop_ns'],
            policy_drop_to_retx_ns=drop_policy['first_retransmission_after_drop_ns'],
            extra_retx_delay_ns=drop_policy['first_retransmission_after_drop_ns']-drop_base['first_retransmission_after_drop_ns'],
            baseline_earlier_retx_ns=drop_base['earlier_retransmission_times_ns'],
            policy_earlier_retx_ns=drop_policy['earlier_retransmission_times_ns']),
        open_recovery_branch_events=sum(s['selective_policy'].get('event_counts',{}).get('OPEN_LOSS_REEVALUATED',0)
                                         for s in summaries.values()),
        qualifications=['Same-formula registration horizons differ by 5.184us and 3.820us from rounded historical windows.',
                        'The saved deadline column on an epoch without a wait can retain the previous epoch value; only wait events define a current deadline.',
                        'Whole-run RETX differences are not all independently classified as spurious.',
                        'Receiver goodput is not sender ACK progress; positive SRTT is not isolated queue delay.',
                        'No competing-flow, prediction-error sweep, statistical repetition or independent final-volume replay.'])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(comparisons=comparisons,measurement_checks=len(measurements),
                         paired_actual_drop_equal=True,open_branch_events=record['open_recovery_branch_events']),indent=2))


if __name__=='__main__': main()
