"""Scoped metrics, immutable-runtime and historical OFF measurement comparisons."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path


def receipt(p):
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Output exists')
    repo=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('declared_tail_runner',Path(__file__).with_name('run.py'))
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    data={q.parent.name:json.loads(q.read_text()) for q in (a.export/'cases').glob('*/summary.json')}
    manifests={n:json.loads((a.export/'cases'/n/'manifest.json').read_text()) for n in data}
    if set(data)!=set(runner.CASES):raise ValueError('Export differs from the exact declared ten-case set')
    first=next(iter(manifests.values()))
    assert all(m['status']=='success' and m['runtime_unchanged'] and m['patch_sha256']==first['patch_sha256'] and
               m['runtime_files']==first['runtime_files'] for m in manifests.values())
    settings=[]
    parsed_commands={}
    for name,m in manifests.items():
        definition=runner.CASES[name]
        assert m['definition']==definition and m['tail_admission']==bool(definition.get('tail'))
        parameter,hints=runner.parameters(definition)
        assert m['additional_parameters']==parameter and m['hints']==hints
        assert m['forecast_source_sha256']==runner.sha(runner.FORWARD)
        assert m['state_static_sha256']==first['state_static_sha256']
        assert m['source_files']==first['source_files'] and m['dependencies']==first['dependencies']
        assert m['runner_sha256']==runner.sha(Path(__file__).with_name('run.py'))
        cli={}
        for arg in m['command'][1:]:
            key,value=arg.split('=',1);assert key.startswith('--') and key not in cli;cli[key]=value
        # Output directory is intentionally different; validate all substantive native flags exactly.
        actual_run=Path(data[name]['provenance']['manifest']['path']).parent
        assert cli['--run_dir']==str(actual_run)
        assert m['environment']['CS30401_STUDY_TRACE_DIR']==str(actual_run/'logs_ns3')
        expected={'--ns3::TcpSocketBase::OrbitTailAdmission':'true' if definition.get('tail') else 'false'}
        if definition['kind']=='micro':
            expected.update({'--cc':'TcpCubic','--duration':'4','--rate':'100','--queue_pkts':'2000',
                '--before_ms':'50','--after_ms':'50','--event_s':'2','--initial_ssthresh_pkts':'900',
                '--max_bytes':str(definition.get('bytes',27600)),'--loss_seq':'1'})
            if parameter:expected['--parameters']=parameter
            assert m['command'][0]==str(runner.NS3/'build/scratch/study_micro/ns3.48-study_micro')
            assert m['dynamic_input_sha256'] is None
            assert m['expected_finite_bytes']==definition.get('bytes',27600)
        else:
            assert m['command'][0]==str(runner.NS3/'build/scratch/main_satnet/ns3.48-main_satnet')
            rows=list(csv.reader((a.export/'cases'/name/'schedule.csv').open()))
            assert rows==[['0','1584','1585','100000000000','0',parameter,'']]
        assert {k:v for k,v in cli.items() if k!='--run_dir'}==expected
        assert m['environment']['CS30401_STUDY_TRACE']=='1'
        assert m['environment']['CS30401_ORBIT_ACTUAL_DROP']==('1' if definition.get('actual_drop') else '0')
        assert m['environment']['LD_LIBRARY_PATH']==str(runner.NS3/'build/lib')
        parsed_commands[name]={k:v for k,v in cli.items() if k not in
            ['--run_dir','--parameters','--ns3::TcpSocketBase::OrbitTailAdmission']}
        settings.append(dict(case=name,exact_definition_hints_forecast_and_native_cli=True))
    groups=[['micro-base','micro-selective','micro-tail'],['micro21-selective','micro21-tail'],
        ['leo10-base','leo10-selective','leo10-tail'],['leo10-drop-base','leo10-drop-tail']]
    for group in groups:
        reference=manifests[group[0]]
        for name in group:
            m=manifests[name]
            assert parsed_commands[name]==parsed_commands[group[0]]
            assert m['output_files']['config_ns3.properties']==reference['output_files']['config_ns3.properties']
            assert m['dynamic_input_sha256']==reference['dynamic_input_sha256']
    historical=[]
    for n in ['micro-base','micro-selective','leo10-base','leo10-selective','leo10-drop-base']:
        old=repo/'docs/experiments/assets/20261012-orbit-loss/final/cases'/n/'summary.json'
        previous=json.loads(old.read_text());checks=[];excluded=[]
        for item in previous['provenance']['raw_inputs']:
            key='logs_ns3/'+Path(item['path']).name
            actual=manifests[n]['output_files'][key]
            if key.endswith('timing_results.csv'):
                excluded.append(key);continue
            checks.append(dict(file=key,old_sha256=item['sha256'],actual_sha256=actual['sha256'],
                               equal=item['sha256']==actual['sha256']))
        assert all(c['equal'] for c in checks),'Historical measurement changed: '+n
        historical.append(dict(case=n,source=receipt(old),checks=checks,excluded_wall_profiling=excluded))
    pairs=[('micro-base','micro-selective'),('micro-selective','micro-tail'),('micro-base','micro-tail'),
           ('micro21-selective','micro21-tail'),('leo10-base','leo10-tail'),
           ('leo10-selective','leo10-tail'),('leo10-drop-base','leo10-drop-tail')]
    comparisons=[]
    for x,y in pairs:
        m,n=data[x]['metrics'],data[y]['metrics'];metric='fct_s' if x.startswith('micro') else 'receiver_goodput_mbps'
        b,c=m[metric],n[metric]
        comparisons.append(dict(baseline=x,policy=y,metric=metric,baseline_value=b,policy_value=c,
            delta=c-b,delta_percent=(c/b-1)*100,baseline_retx=m['retransmissions'],policy_retx=n['retransmissions'],
            baseline_recovery=m['recovery_entries'],policy_recovery=n['recovery_entries'],
            baseline_distinct_drops=m['distinct_tagged_drops'],policy_distinct_drops=n['distinct_tagged_drops']))
    drops=[data[n]['injected_actual_drop'] for n in ['leo10-drop-base','leo10-drop-tail']]
    assert drops[0]['selection']==drops[1]['selection'] and drops[0]['matched_physical_drop']==drops[1]['matched_physical_drop']
    x,y=[manifests[n] for n in ['leo10-drop-base','leo10-drop-tail']]
    assert x['state_static_sha256']==y['state_static_sha256'] and x['dynamic_input_sha256']==y['dynamic_input_sha256']
    schedules=[next(csv.reader((a.export/'cases'/n/'schedule.csv').open())) for n in ['leo10-drop-base','leo10-drop-tail']]
    assert schedules[0][:5]==schedules[1][:5] and x['actual_drop_rule']==y['actual_drop_rule']
    assert x['output_files']['config_ns3.properties']==y['output_files']['config_ns3.properties']
    record=dict(schema_version=1,tool=receipt(Path(__file__)),inputs=[receipt(a.export/'cases'/n/'summary.json') for n in sorted(data)],
        conditions=10,not_statistical_replicates=True,final_patch_sha256=first['patch_sha256'],all_runtime_files_equal=True,
        source_commits=sorted({m['repo_commit'] for m in manifests.values()}),historical_off_controls=historical,
        exact_declared_case_settings=settings,matched_contrast_groups=groups,
        comparisons=comparisons,tail_admissions={n:s['tail_policy']['count'] for n,s in data.items()},
        paired_drop_identity=drops[0]['selection'],paired_physical_drop_equal=True,
        extra_drop_to_first_retx_ns=drops[1]['first_retransmission_after_drop_ns']-drops[0]['first_retransmission_after_drop_ns'],
        limitation='One deterministic run per condition; no deployment, loss of the extra tail, zero-window, ECN or RTO boundary proof.')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(comparisons=comparisons,tail_admissions=record['tail_admissions']),indent=2))
