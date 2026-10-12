"""Hash-check completed controls and integrate sparse exact queue-state bins."""
import argparse
from collections import Counter,defaultdict
import csv
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


queue=load('frozen_queue_metrics',REPO/'code/orbit-queue/analyze.py')
tail=load('frozen_tail_metrics',REPO/'code/orbit-tail/analyze.py')
runner=load('pacing_conditions',HERE/'run.py')
sha,rows,key=queue.sha,queue.rows,queue.key
receipt=tail.receipt
WINDOWS={'whole':(0,200000000000),**queue.WINDOWS}


def verify(run,reference=None):
    m=json.loads((run/'manifest.json').read_text())
    assert m['status']=='success' and m['exit_code']==0
    assert m['runtime_unchanged'] and m['source_unchanged'] and m['launch_source_files_unchanged']
    for rel,r in m['output_files'].items():
        path=run/rel
        assert path.resolve().is_relative_to(run.resolve()) and path.stat().st_size==r['bytes'] and sha(path)==r['sha256'],rel
    # The frozen queue reader expects its own launch-source key. Supply its
    # recorded dependency hash to that read-only adapter; preserve m on disk.
    adapted=dict(m,source_files={**m['source_files'],
        'code/orbit-queue/analyze.py':m['dependency_files']['code/orbit-queue/analyze.py']})
    return adapted,dict(all_execution_output_hashes=True,
        historical_measurement_equality='Only the OFF control is tested against frozen current-tail measurements by compare.py.')


queue.verify=verify


def exact_area(run):
    per_device=defaultdict(lambda:defaultdict(Counter));seen=set();count=0
    for row in rows(run/'logs_ns3/queue_area_bins.csv'):
        row={k:int(v) for k,v in row.items()};k=key(row)
        a,b=row['bin_start_ns'],row['bin_end_ns'];width=b-a
        assert 0<=a<b<=200000000000 and a%100000000==0 and width<=100000000
        assert row['cutoff_ns']==200000000000 and (k,a) not in seen
        seen.add((k,a));count+=1
        assert 0<=row['full_ns']<=width and row['q_packet_ns']>=0 and row['q_byte_ns']>=0
        assert row['peak_packets']<=row['max_packets']
        assert row['q_packet_ns']<=width*row['peak_packets'] and row['q_byte_ns']<=width*row['peak_bytes']
        for window,(start,end) in WINDOWS.items():
            if end<=a or b<=start:continue
            assert start<=a and b<=end,'A window cuts an exact bin; do not interpolate snapshots'
            dst=per_device[k][window]
            for field in ['q_packet_ns','q_byte_ns','full_ns']:dst[field]+=row[field]
            for field in ['peak_packets','peak_bytes']:dst[field]=max(dst[field],row[field])
    out=[];aggregate={}
    for k,data in sorted(per_device.items()):
        windows={}
        for window,(start,end) in WINDOWS.items():
            value=data[window]
            windows[window]=dict(value,start_ns=start,end_ns=end,
                mean_packets=value['q_packet_ns']/(end-start),mean_bytes=value['q_byte_ns']/(end-start))
        out.append(dict(node_id=k[0],device_id=k[1],windows=windows))
    for window,(start,end) in WINDOWS.items():
        values=[d['windows'][window] for d in out]
        aggregate[window]=dict(start_ns=start,end_ns=end,
            all_device_q_packet_ns=sum(v.get('q_packet_ns',0) for v in values),
            all_device_q_byte_ns=sum(v.get('q_byte_ns',0) for v in values),
            all_device_full_queue_ns=sum(v.get('full_ns',0) for v in values))
    return dict(source=receipt(run/'logs_ns3/queue_area_bins.csv'),bins=count,devices=out,aggregate=aggregate,
        sparse_zero_bins_are_exact_zero=True,denominator_includes_entire_window=True,
        method='Integrate previous held packet/byte state at every callback and at final cutoff; no late-flush snapshots.')


def first_loss(run,m):
    if not m['definition'].get('first_loss'):return None
    logs=run/'logs_ns3';chosen=list(rows(logs/'pacing_first_loss.csv'))
    assert len(chosen)==1
    chosen={k:int(v) for k,v in chosen[0].items()}
    assert chosen['flow_id']==0 and chosen['seq']==1 and chosen['payload_bytes']==1380 and chosen['receiver_node']==1585
    install=list(rows(logs/'pacing_first_loss_install.csv'))
    devices={int(r['device_id']) for r in install if r['device_type']=='ns3::GSLNetDevice'}
    assert devices,'Loss helper not installed on actual destination GSL'
    matches=[]
    for r in rows(logs/'study_drops.csv'):
        if r['node']!='1585' or int(r['device']) not in devices or r['layer']!='PhyRxDrop':continue
        if all(int(r[k])==chosen[k] for k in ['flow_id','tx_id','tx_time_ns','seq','payload_bytes','time_ns']):matches.append(r)
    assert len(matches)==1,'Selected loss has no unique exact physical identity and receiver-time match'
    sent=[];retx=[];earlier=[]
    for r in rows(logs/'tcp_flow_0_study_packets.csv'):
        if int(r['seq'])!=1 or int(r['payload_bytes'] or 0)!=1380:continue
        if r['event']=='TX' and all(int(r[k])==chosen[k] for k in ['flow_id','tx_id','tx_time_ns','seq','payload_bytes']):sent.append(r)
        if r['event']=='RETX':
            (retx if int(r['time_ns'])>=chosen['time_ns'] else earlier).append(int(r['time_ns']))
    assert len(sent)==1 and retx,'Missing original TX or genuine-loss recovery'
    assert int(sent[0]['time_ns'])==chosen['tx_time_ns']<chosen['time_ns']
    return dict(selection=chosen,physical_drop=matches[0],actual_original_tx=sent[0],
        retx_after_drop_ns=retx,earlier_retx_ns=earlier,drop_to_first_retx_ns=retx[0]-chosen['time_ns'],
        exact_identity_and_receiver_time_audit=True,
        shared_rule_is_not_identical_transmission_time=True,source=receipt(logs/'pacing_first_loss.csv'))


def pacing(run,m):
    trace=run/'logs_ns3/tcp_flow_0_pacing.csv'
    assert trace.exists(),'Missing direct native pacing-rate trace'
    data=[{k:int(v) for k,v in r.items()} for r in rows(trace)]
    assert all(r['flow_id']==0 and 0<=r['time_ns']<int(m['definition'].get('duration',4)*1e9) for r in data)
    assert all(0<=r['new_bps']<=m['native_pacing']['max_bps'] for r in data)
    if not m['native_pacing']['enabled']:assert not data,'OFF changed native pacing rate'
    else:assert data,'ON has no direct native pacing-rate changes'
    return dict(declared=m['native_pacing'],source=receipt(trace),change_count=len(data),
        min_observed_new_bps=min((r['new_bps'] for r in data),default=None),
        max_observed_new_bps=max((r['new_bps'] for r in data),default=None),
        first_changes=data[:5],last_changes=data[-5:],native_initial_assignment_precedes_observer=True)


def queue_summary(run,m):
    data=queue.analyze(run,None);data['observer_only']=m['observer_only']
    data['qa']['input_state_equal']='Checked pairwise by compare.py'
    data['caveats']=data['caveats'][1:]+['Pacing is an active native setting; only OFF has historical trajectory equality.']
    area=exact_area(run);lookup={(d['node_id'],d['device_id']):d for d in area['devices']}
    for d in data['devices']:
        k=key(d['mapping'])
        for window in queue.WINDOWS:
            expected=lookup.get(k,{}).get('windows',{}).get(window,{'mean_packets':0})
            assert abs(d['windows'][window]['occupancy']['time_weighted_packets']-expected['mean_packets'])<1e-8,'Focus packet area mismatch'
    data['exact_state_area']=area
    serialized=Counter();busy=Counter()
    for r in rows(run/'logs_ns3/orbit_service_bins.csv'):
        k=key(r);busy[k]+=int(r['busy_ns']);serialized[k]+=int(r['serialized_bytes_started'])
    data['whole_service']=[dict(node_id=k[0],device_id=k[1],busy_ns=value,
        busy_fraction=value/200000000000,serialized_bytes_started=serialized[k]) for k,value in sorted(busy.items())]
    assert all(d['busy_ns']<=200000000000 for d in data['whole_service'])
    data['pending_age_records']=list(rows(run/'logs_ns3/orbit_queue_pending.csv'))
    drop_rows=defaultdict(list)
    for row in rows(run/'logs_ns3/study_drops.csv'):
        if row['flow_id']!='0':continue
        identity=tuple(int(row[f]) for f in ['flow_id','tx_id','tx_time_ns','seq','payload_bytes'])
        for window,(start,end) in WINDOWS.items():
            if start<=int(row['time_ns'])<end:drop_rows[window].append(identity)
    data['drop_identity_windows']={w:dict(rows=len(drop_rows[w]),distinct_transmissions=len(set(drop_rows[w])),
        row_to_distinct_equal=len(drop_rows[w])==len(set(drop_rows[w]))) for w in WINDOWS}
    # Wire overhead check uses observed focus queue entries joined to full-size
    # sender TX identity. It is a focus sample, not every serialization.
    full_tx={int(r['tx_id']) for r in rows(run/'logs_ns3/tcp_flow_0_study_packets.csv')
             if r['event']=='TX' and int(r['payload_bytes'] or 0)==1380}
    sizes=Counter(int(r['packet_bytes']) for r in rows(run/'logs_ns3/queue_focus.csv')
                  if r['event']=='ENQUEUE' and r['flow_id']=='0' and int(r['tx_id'] or -1) in full_tx)
    assert not sizes or set(sizes)=={1434},'Declared full-data overhead differs from actual queue entries'
    data['wire_overhead_focus_visit_check']=dict(payload_bytes=1380,expected_serialized_bytes=1434,
        observed_packet_bytes_counts=dict(sizes),qualified_scope='Full-payload flow0 enqueue visits inside the fixed focus window.')
    return data


def export(run,out):
    m,_=verify(run)
    summary=tail.export(run,out)
    summary['native_pacing']=pacing(run,m)
    summary['first_sequence_actual_loss']=first_loss(run,m)
    summary['queue']=queue_summary(run,m) if m['definition']['kind']=='leo' else None
    summary['pacing_analysis']=dict(tool=receipt(Path(__file__)),dependencies=[receipt(REPO/p) for p in
        ['code/orbit-queue/analyze.py','code/orbit-tail/analyze.py','code/orbit-loss/analyze.py']],
        analysis_phase='Postprocessing; completed raw success status is unchanged.')
    dst=out/'cases'/m['case'];(dst/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',newline='\n')
    for name in ['pacing_first_loss.csv','pacing_first_loss_install.csv']:
        if (run/'logs_ns3'/name).exists():shutil.copyfile(run/'logs_ns3'/name,dst/name)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('/tmp/queue-pacing'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',nargs='+',required=True,choices=runner.CASES)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    results=[export(a.root/name,a.out) for name in a.cases]
    with (a.out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]['metrics']));w.writeheader();w.writerows(s['metrics'] for s in results)
    (a.out/'receipt.json').write_text(json.dumps(dict(tool=receipt(Path(__file__)),
        cases=[s['metrics']['case'] for s in results],outputs=[receipt(p) for p in sorted(a.out.rglob('*')) if p.is_file()]),indent=2)+'\n',newline='\n')
    print(json.dumps([s['metrics'] for s in results],indent=2))
