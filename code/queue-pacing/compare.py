"""Verify matched controls and apply the success gates fixed before simulation."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
spec=importlib.util.spec_from_file_location('pacing_runner',HERE/'run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sha=runner.sha


def receipt(path):return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def parse_config(path):
    return dict(line.strip().split('=',1) for line in path.read_text().splitlines()
                if '=' in line and not line.lstrip().startswith('#'))


def verify_settings(export,data,manifests,winner):
    first=manifests['off'];checks=[]
    for name,m in manifests.items():
        case=runner.definition(name,winner)
        assert m['definition']==case and m['tail_admission']==case['tail']
        assert m['status']=='success' and m['runtime_unchanged'] and m['source_unchanged'] and m['launch_source_files_unchanged']
        for f in ['runtime_files','patch_sha256','source_files','dependency_files','runner_sha256','build_ready_sha256','state_static_sha256','forecast_source_sha256']:
            assert m[f]==first[f],f
        additional,hints=runner.tail.parameters(case)
        assert m['additional_parameters']==additional and m['hints']==hints
        expected={a.split('=',1)[0]:a.split('=',1)[1] for a in runner.native_cli(case)}
        if case['kind']=='micro':
            expected.update({'--cc':'TcpCubic','--duration':'4','--rate':'100','--queue_pkts':'2000',
                '--before_ms':'50','--after_ms':'50','--event_s':'2','--initial_ssthresh_pkts':'900',
                '--max_bytes':'27600','--loss_seq':'1','--enable_pacing':str(case['pacing']).lower()})
            if additional:expected['--parameters']=additional
            assert m['expected_finite_bytes']==27600 and m['dynamic_input_sha256'] is None
            assert m['command'][0]==str(runner.NS3/'build/scratch/study_micro/ns3.48-study_micro')
        else:
            assert m['dynamic_input_sha256']==first['dynamic_input_sha256']
            assert m['command'][0]==str(runner.NS3/'build/scratch/main_satnet/ns3.48-main_satnet')
            assert list(csv.reader((export/'cases'/name/'schedule.csv').open()))==[['0','1584','1585','100000000000','0',additional,'']]
        args=m['command'][1:];cli=dict(a.split('=',1) for a in args)
        assert len(args)==len(cli),'Duplicate native options'
        run=Path(data[name]['provenance']['manifest']['path']).parent
        assert cli.pop('--run_dir')==str(run) and cli==expected
        for env in ['CS30401_STUDY_TRACE_DIR','CS30401_ORBIT_QUEUE_TRACE_DIR']:
            assert m['environment'][env]==str(run/'logs_ns3')
        assert m['environment']['CS30401_ORBIT_ACTUAL_DROP']=='0'
        assert m['environment']['CS30401_QUEUE_PACING_FIRST_LOSS']==('1' if case.get('first_loss') else '0')
        for env in ['CS30401_STUDY_TRACE','CS30401_ORBIT_QUEUE_TRACE','CS30401_ORBIT_SERVICE_TRACE','CS30401_QUEUE_FLOW_TRACE','CS30401_QUEUE_PACING_RATE_TRACE']:
            assert m['environment'][env]=='1'
        assert m['native_pacing']==dict(enabled=case['pacing'],max_bps=runner.maximum(case),ss_ratio=200,ca_ratio=120,
                                     pace_initial_window=False,payload_bytes=1380,assumed_serialized_data_bytes=1434)
        checks.append(dict(case=name,exact_definition_cli_hints_state_runtime=True))
    groups=[runner.INITIAL]
    if set(runner.SAFETY)<=set(data):groups+=[runner.SAFETY[:3],runner.SAFETY[3:]]
    for group in groups:
        cfgs=[parse_config(export/'cases'/n/'config_ns3.properties') for n in group]
        for name,cfg in zip(group,cfgs):
            if manifests[name]['definition']['kind']=='leo':
                assert cfg.pop('tcp_enable_pacing')==str(manifests[name]['definition']['pacing']).lower()
        assert all(cfg==cfgs[0] for cfg in cfgs),'Unmatched non-pacing configuration'
    return checks,groups


def source_post(summary):
    q=summary['queue']
    area=next(d for d in q['exact_state_area']['devices'] if (d['node_id'],d['device_id'])==(1584,1))
    visits=next(d for d in q['devices'] if (int(d['mapping']['node_id']),int(d['mapping']['device_id']))==(1584,1))
    assert visits['mapping']['device_type']=='ns3::GSLNetDevice'
    return area['windows']['post'],visits['windows']['post']['served_sojourn']


def gates(data):
    base=data['off'];bq,bw=source_post(base);out=[]
    for name in ['native','capacity']:
        s=data[name];q,w=source_post(s)
        focus=s['queue']['drop_identity_windows']['focus']['distinct_transmissions']
        tests=dict(goodput_floor=s['metrics']['receiver_goodput_mbps']>=9.498776256,
            source_post_queue_half=q['mean_packets']<=bq['mean_packets']*.5,
            source_post_served_wait_half=w['mean_ns'] is not None and w['mean_ns']<=bw['mean_ns']*.5,
            focus_drops_at_most_five=focus<=5,
            whole_all_device_queue_not_worse=s['queue']['exact_state_area']['aggregate']['whole']['all_device_q_packet_ns']<=base['queue']['exact_state_area']['aggregate']['whole']['all_device_q_packet_ns'],
            whole_distinct_drops_not_worse=s['metrics']['distinct_tagged_drops']<=base['metrics']['distinct_tagged_drops'])
        out.append(dict(case=name,passed=all(tests.values()),tests=tests,
            whole_goodput_mbps=s['metrics']['receiver_goodput_mbps'],source_post_mean_packets=q['mean_packets'],
            source_post_served_wait_ms=w['mean_ns']/1e6 if w['mean_ns'] is not None else None,
            focus_distinct_dropped_transmissions=focus,
            focus_drop_rows=s['queue']['drop_identity_windows']['focus']['rows'],whole_distinct_drops=s['metrics']['distinct_tagged_drops'],
            whole_all_device_queue_packet_ns=s['queue']['exact_state_area']['aggregate']['whole']['all_device_q_packet_ns']))
    passed=[r for r in out if r['passed']]
    passed.sort(key=lambda r:(r['whole_distinct_drops'],r['whole_all_device_queue_packet_ns'],-r['whole_goodput_mbps'],r['case']!='native'))
    return out,passed[0]['case'] if passed else None


def historical(data,manifests):
    pairs=[('off','leo10-tail')]
    if 'micro-current' in data:pairs += [('micro-original','micro-base'),('micro-current','micro-tail')]
    output=[]
    for name,old in pairs:
        source=REPO/'docs/experiments/assets/20261013-orbit-tail/final/cases'/old/'summary.json'
        prior=json.loads(source.read_text());checks=[]
        for item in prior['provenance']['raw_inputs']:
            rel='logs_ns3/'+Path(item['path']).name
            if rel.endswith('timing_results.csv'):continue
            actual=manifests[name]['output_files'][rel]
            assert actual['sha256']==item['sha256'] and actual['bytes']==item['bytes'],'Historical measurement differs: '+name+' '+rel
            checks.append(dict(file=rel,sha256=actual['sha256'],bytes=actual['bytes'],equal=True))
        output.append(dict(case=name,prior_case=old,source=receipt(source),checks=checks,exclusion='Wall-clock timing_results.csv only'))
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--export',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['initial','safety'],default='initial')
    p.add_argument('--selection',type=Path);a=p.parse_args();assert not a.out.exists()
    data={q.parent.name:json.loads(q.read_text()) for q in (a.export/'cases').glob('*/summary.json')}
    expected=runner.INITIAL+(runner.SAFETY if a.phase=='safety' else [])
    assert set(data)==set(expected),'Not the exact declared condition set'
    selected=json.loads(a.selection.read_text()) if a.selection else None
    if a.phase=='safety':assert selected and selected['prospective_gates_passed']
    manifests={n:json.loads((a.export/'cases'/n/'manifest.json').read_text()) for n in data}
    checks,groups=verify_settings(a.export,data,manifests,selected['winner'] if selected else None)
    tested,winner=gates(data)
    if selected:assert winner==selected['winner'],'Winner differs from original prospective selection'
    comparisons=[]
    for name in expected:
        s=data[name];metrics=s['metrics']
        record=dict(case=name,**{k:metrics[k] for k in ['receiver_goodput_mbps','receiver_bytes','fct_s','retransmissions','recovery_entries','ca_loss_entries','distinct_tagged_drops']},tail_admissions=s['tail_policy']['count'])
        if s['queue']:
            post,wait=source_post(s)
            record.update(post_mean_queue_packets=post['mean_packets'],post_served_wait_ms=wait['mean_ns']/1e6 if wait['mean_ns'] else 0,
                focus_drop_rows=s['queue']['drop_identity_windows']['focus']['rows'],
                focus_distinct_drops=s['queue']['drop_identity_windows']['focus']['distinct_transmissions'],
                whole_queue_packet_ns=s['queue']['exact_state_area']['aggregate']['whole']['all_device_q_packet_ns'])
        if s['first_sequence_actual_loss']:record['drop_to_first_retx_ms']=s['first_sequence_actual_loss']['drop_to_first_retx_ns']/1e6
        comparisons.append(record)
    first=manifests['off']
    out=dict(schema=1,phase=a.phase,tool=receipt(Path(__file__)),conditions=len(data),not_statistical_replicates=True,
        prospective_gates=tested,prospective_gates_passed=winner is not None,winner=winner,
        patch_sha256=first['patch_sha256'],runtime_files=first['runtime_files'],exact_settings=checks,
        matched_contrast_groups=groups,historical_measurement_equality=historical(data,manifests),
        comparisons=comparisons,inputs=[receipt(a.export/'cases'/n/'summary.json') for n in sorted(data)],
        limitations=['Fixed single-seed conditions, not repeated estimates.',
            'Native initial window is unpaced; direct retransmissions can exceed the timer ceiling.',
            'Finite or actual-loss regressions remain limits even when bulk queue gates pass.',
            'Shared first-loss rules do not imply identical TX times under pacing.'])
    if a.phase=='safety':
        assert manifests['loss-current']['actual_drop_rule']==manifests['loss-selected']['actual_drop_rule']
        out['actual_loss_pair_own_transmission_identity_verified']=True
        out['finite_fct_percent_vs_current']=(data['micro-selected']['metrics']['fct_s']/data['micro-current']['metrics']['fct_s']-1)*100
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2)+'\n',newline='\n')
    print(json.dumps(dict(winner=winner,gates=tested,comparisons=comparisons),indent=2))
