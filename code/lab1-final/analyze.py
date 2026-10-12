"""Regenerate report inputs from fresh raw runs, then enforce historical byte parity."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import common as c

queue=c.module('final_queue_analysis','code/queue-pacing/analyze.py')
bp=c.module('final_bp_analysis','code/queue-backpressure/analyze.py')
cf=c.module('final_cf_prefix','code/orbit-queue/analyze_cf.py')


def figure_series(run):
    logs=run/'logs_ns3';before=None;points=[]
    with (logs/'tcp_flow_0_cwnd.csv').open(newline='') as f:
        for row in csv.reader(f):
            t,v=int(row[1]),int(row[2])
            if t<25900000000:before=[t,v]
            elif t<=26600000000:points.append([t,v])
    if before:points.insert(0,before)
    if points:points.append([26600000000,points[-1][1]])
    bins={t:0 for t in range(74500000000,77500000000,100000000)}
    for r in queue.rows(logs/'queue_area_bins.csv'):
        t=int(r['bin_start_ns'])
        if r['node_id']=='1584' and r['device_id']=='1' and t in bins:
            assert int(r['bin_end_ns'])==t+100000000
            bins[t]+=int(r['q_packet_ns'])
    return dict(cwnd=points,source_queue_bins=[dict(start_ns=t,end_ns=t+100000000,packet_ns=v) for t,v in bins.items()],
        source=[c.receipt(logs/'tcp_flow_0_cwnd.csv'),c.receipt(logs/'queue_area_bins.csv')])


def normalize_pace(run,summary):
    q=summary['queue'];windows=q['measurements'] if q else {}
    if q:
        for w in summary['path_event_windows']:
            if abs(w['window_start_s']-25.7)<1e-8 and abs(w['window_end_s']-28.2)<1e-8:
                f=w['flows']['0'];counts=f.get('counts',f)
                windows['first']=dict(start_ns=25700000000,end_ns=28200000000,
                    app_bytes=counts.get('application_delivered_bytes',0),app_goodput_mbps=f.get('receiver_application_goodput_mbps',0),
                    retx_packets=counts.get('official_retransmission_rows',0),recovery_entries=counts.get('recovery_state_entries',0),
                    loss_state_entries=counts.get('loss_state_entries',0),tagged_drop_count=counts.get('drop_trace_rows',0))
        source=next(d for d in q['devices'] if (int(d['mapping']['node_id']),int(d['mapping']['device_id']))==(1584,1))
        total=[r for r in q['queue_conservation'] if (r['node_id'],r['device_id'])==(1584,1)]
        visits=sum(r['sojourn_samples'] for r in total);wait=sum(r['sojourn_sum_ns'] for r in total)
        queue_record=dict(source=source,all_device=q['exact_state_area']['aggregate'],
            whole_source_served_wait=dict(samples=visits,sum_ns=wait,mean_ns=wait/visits if visits else None),
            exact_state_area=q['exact_state_area'],drop_identity_windows=q['drop_identity_windows'],pending=q['pending_age_records'])
    else:queue_record=None
    return dict(metrics=summary['metrics'],windows=windows,selective_episodes=summary['selective_policy']['episodes'],
        tail_admissions=summary['tail_policy']['count'],tail_policy=summary['tail_policy'],queue=queue_record,
        actual_drop=summary.get('injected_actual_drop') or summary.get('first_sequence_actual_loss'),
        native_pacing=summary['native_pacing'],provenance=summary['provenance'],
        figure_series=figure_series(run) if q else None,
        compatibility_note='guard_starts describes legacy threshold setters; selective_episodes is the actual K3 waiting evidence.')


def parity(run,expected):
    m=json.loads((run/'manifest.json').read_text());checks=[]
    for name,r in expected['measurement_csvs'].items():
        actual=m['output_files'].get(name)
        assert actual==r,'Frozen measurement parity failed: '+m['case']+' '+name
        checks.append(dict(file=name,**actual,equal=True))
    return dict(all_exact=True,checks=checks,reference_sha256=expected['reference_sha256'],
        reference_path=expected['reference_path'],qualification='Wall profiling excluded; fresh manifests/runtime identity are retained separately.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=c.PATCHES,required=True)
    p.add_argument('--root',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.root=a.root or c.ROOTS[a.profile];assert not a.out.exists();a.out.mkdir(parents=True)
    expected=json.loads((c.HERE/'inputs/expected-parity.json').read_text());cases={};proofs={}
    for name,d in c.CASES.items():
        if d['profile']!=a.profile:continue
        run=a.root/name;m=json.loads((run/'manifest.json').read_text())
        assert m['status']=='success' and m['exit_code']==0 and not m.get('audit_exclude'),'Incomplete/excluded replay'
        assert m['definition']==d['definition'] and m['profile']==a.profile and m['patch_sha256']==c.PATCHES[a.profile]
        assert m['source_unchanged'] and m['runtime_unchanged'] and m['launch_source_files_unchanged']
        proofs[name]=parity(run,expected['cases'][name])
        if a.profile=='pace':
            s=queue.export(run,a.out);cases[name]=normalize_pace(run,s)
            if 'metrics' in expected['cases'][name]:
                assert s['metrics']==expected['cases'][name]['metrics'],'Frozen scalar parity failed: '+name
        else:
            s=bp.analyze(run);whole=s['metrics']['whole']
            cases[name]=dict(metrics=dict(case=name,receiver_bytes=whole['app_bytes'],receiver_goodput_mbps=whole['app_goodput_mbps'],
                fct_s=None,retransmissions=whole['retx_packets'],recovery_entries=whole['recovery_entries'],
                ca_loss_entries=whole['loss_state_entries'],distinct_tagged_drops=whole['unique_all_layer_tx_losses']),
                windows=s['metrics'],selective_episodes=[],tail_admissions=0,actual_drop=None,
                queue=dict(source=s['metrics'],source_residence=s['served_source_residence'],native_summary=s['native_summary'],
                    pending=s['pending_source_age'],all_device={w:dict(network_plus_qdisc_requeue_mean_packets=v['network_plus_qdisc_requeue_mean_packets']) for w,v in s['metrics'].items()}),
                provenance=dict(manifest=c.receipt(run/'manifest.json'),source=s['source']),figure_series=None)
            c.write(a.out/'cases'/name/'summary.json',s)
    extra={}
    if a.profile=='pace':
        extra['counterfactual_exact_pre75']=cf.exact_prefix(a.root/'leo10-selective',a.root/c.CF)
        # Add the exact new integral logger to the original prefix contract.
        def prefix(root):return [r for r in queue.rows(root/'logs_ns3/queue_area_bins.csv') if int(r['bin_end_ns'])<=75000000000]
        assert prefix(a.root/'leo10-selective')==prefix(a.root/c.CF),'Pre75 exact integral differs'
        extra['counterfactual_new_area_prefix_equal']=True
    else:extra['backpressure_matched_inputs']=bp.matched_inputs(a.root)
    record=dict(schema=1,phase='Fresh independent-volume replay; figures use observed raw series, never reference numbers.',
        profile=a.profile,report_roles=c.ROLES,cases=cases,physical_conditions=len(cases),aliases=c.ALIASES,
        parity=proofs,qa=extra,tool=c.receipt(Path(__file__)),expected_contract=c.receipt(c.HERE/'inputs/expected-parity.json'))
    c.write(a.out/'report-data.json',record)
    print(json.dumps({'profile':a.profile,'conditions':len(cases),'all_frozen_csv_parity':True,'report_data':str(a.out/'report-data.json')}))
