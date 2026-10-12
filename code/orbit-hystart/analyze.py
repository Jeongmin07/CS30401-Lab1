"""Validate finite completion and export compact, source-backed HyStart evidence."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()


def rows(path):
    with Path(path).open(newline='') as f: return list(csv.DictReader(f))


def analyze(root,name):
    run=root/name
    manifest=json.loads((run/'manifest.json').read_text())
    if manifest['status']!='success' or manifest['exit_code']!=0:
        raise ValueError('Incomplete simulation: '+name)
    for relative,item in manifest['output_files'].items():
        p=run/relative
        if p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
            raise ValueError('Raw file differs from preserved receipt: '+str(p))
    logs=run/'logs_ns3'
    app=rows(logs/'study_app_rx_node_1585_port_1024.csv')
    assert app and all(x['flow_id']=='0' and x['connection_id']=='0' for x in app)
    delivered=sum(int(x['payload_bytes']) for x in app)
    assert delivered==int(app[-1]['connection_total_rx_bytes'])==8388608
    start=manifest['flow']['start_ns']
    first,last=int(app[0]['time_ns']),int(app[-1]['time_ns'])
    assert first>=start and last<=manifest['flow']['duration_ns']
    sock=rows(logs/'hystart_socket.csv')
    assert len(sock)==1 and sock[0]['actual_type']=='ns3::TcpCubic'
    assert (sock[0]['hystart_enabled']=='1')==manifest['definition']['hystart']
    state=rows(logs/'hystart_state.csv') if (logs/'hystart_state.csv').exists() else []
    exits=[r for r in state if r['event']=='EXIT']
    for r in exits:
        assert int(r['reason_mask']) in (1,2,3)
        assert int(r['ssthresh_after_bytes'])==int(r['cwnd_bytes'])
        if int(r['reason_mask'])&1:
            assert int(r['ack_gap_before_ns'])<=2000000
            assert int(r['round_elapsed_ns'])>int(r['delay_min_ns'])
        if int(r['reason_mask'])&2:
            assert int(r['current_rtt_ns'])>int(r['delay_min_ns'])+int(r['threshold_ns'])
    events=rows(logs/'tcp_flow_0_study_events.csv')
    packets=rows(logs/'tcp_flow_0_study_packets.csv')
    drops=rows(logs/'study_drops.csv')
    tagged={tuple(r[k] for k in ['flow_id','tx_id','tx_time_ns']) for r in drops
            if r['flow_id']=='0' and int(r['tx_id'])>0}
    tc=[r for r in drops if r['layer']=='TcDrop' and r['flow_id']=='0']
    queue={}
    if (logs/'orbit_queue_bins.csv').exists():
        bins=rows(logs/'orbit_queue_bins.csv')
        pending=rows(logs/'orbit_queue_pending.csv')
        acc=defaultdict(lambda:dict(enqueued=0,dequeued=0,drop_before=0,drop_after=0,
                                   samples=0,sum_ns=0,max_ns=0,pending=0))
        for r in bins:
            key=(r['node_id'],r['device_id'],r['flow_id'])
            a=acc[key]
            for k in ['enqueued','dequeued','drop_before','drop_after']: a[k]+=int(r[k])
            a['samples']+=int(r['sojourn_samples'])
            a['sum_ns']+=int(r['sojourn_sum_ns'])
            a['max_ns']=max(a['max_ns'],int(r['sojourn_max_ns']))
        for r in pending:
            acc[(r['node_id'],r['device_id'],r['flow_id'])]['pending']+=int(r['pending_packets'])
        assert all(a['enqueued']-a['dequeued']==a['pending'] and a['drop_after']==0
                   and a['samples']==a['dequeued'] for a in acc.values())
        def aggregate(selected):
            samples=sum(a['samples'] for a in selected)
            return dict(dequeued_queue_visits=samples,
                mean_ms=sum(a['sum_ns'] for a in selected)/samples/1e6 if samples else None,
                max_ms=max([a['max_ns'] for a in selected],default=0)/1e6,
                pending_packets=sum(a['pending'] for a in selected),
                drop_before=sum(a['drop_before'] for a in selected))
        queue={'conservation_passed':True,'all_visits':aggregate(list(acc.values())),
               'flow0_visits':aggregate([a for key,a in acc.items() if key[2]=='0']),
               'source_flow0_visits':aggregate([a for key,a in acc.items() if key[0]=='1584' and key[2]=='0']),
               'meaning':'Packet-weighted device-queue visits, including zero waits; not end-to-end queue delay. Flush occupancy is at flush_time_ns, not a bin-boundary snapshot.'}
    first_tc=min([int(r['time_ns']) for r in tc],default=None)
    intervals=Counter(r['event'] for r in state)
    return dict(case=name,full_delivery_verified=True,delivered_bytes=delivered,
        application_start_ns=start,first_app_delivery_ns=first,last_app_delivery_ns=last,
        completion_s=(last-start)/1e9,socket_configuration=sock[0],hystart_exits=exits,
        hystart_event_counts=dict(intervals),
        forecast_window_samples=sum(r['event']=='HYSTART_SAMPLE' and
             121600000000<=int(r['time_ns'])<121781136000 for r in state),
        drop_rows_by_layer=dict(Counter(r['layer'] for r in drops)),
        distinct_tagged_drop_transmissions=len(tagged),first_tc_drop_ns=first_tc,
        first_drop_before_hystart_exit=(bool(exits) and first_tc is not None and
                                      first_tc<int(exits[0]['time_ns'])),
        retransmission_rows=sum(r['event']=='RETX' for r in packets),
        recovery_entries=sum(r['event']=='CONG' and r['new_value']=='3' for r in events),
        loss_entries=sum(r['event']=='CONG' and r['new_value']=='4' for r in events),
        queue=queue,manifest_sha256=sha(run/'manifest.json'),
        raw_file_hashes=manifest['output_files'],
        source={k:manifest[k] for k in ['repo_commit','repo_dirty','runner_sha256','patch_sha256',
              'patch_path','ns3_head','runtime_files','image_ref','input_files','path_truth_sha256',
              'command','environment','definition','wall_seconds','status','exit_code']},
        state_input_receipt=dict(static_count=len(manifest['state_static_sha256']),
             dynamic_count=len(manifest['dynamic_input_sha256']),
             static_mapping_sha256=hashlib.sha256(json.dumps(manifest['state_static_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
             dynamic_mapping_sha256=hashlib.sha256(json.dumps(manifest['dynamic_input_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest()))


def compare_measurements(root,left,right):
    def names(name):
        return {p.name for p in (root/name/'logs_ns3').glob('*.csv')
                if not p.name.startswith(('hystart_','orbit_')) and p.name!='timing_results.csv'}
    selected=names(left)
    assert selected and selected==names(right)
    checks=[dict(file=name,left_sha256=sha(root/left/'logs_ns3'/name),
                       right_sha256=sha(root/right/'logs_ns3'/name)) for name in sorted(selected)]
    for r in checks: r['equal']=r['left_sha256']==r['right_sha256']
    return dict(left=left,right=right,all_measurements_byte_identical=all(r['equal'] for r in checks),
         checks=checks,limits='Timing and new observer files excluded. Case source/binary identities remain separate. One-condition equality is not universal behavior equivalence.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases',nargs='+')
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-hystart'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    summaries={name:analyze(a.root,name) for name in a.cases}
    compact=[]
    for name,r in summaries.items():
        d=a.out/'cases'/name
        d.mkdir(parents=True)
        (d/'summary.json').write_text(json.dumps(r,indent=2)+'\n',newline='\n')
        for f in ['config_ns3.properties','schedule.csv']:
            if (a.root/name/f).exists(): shutil.copyfile(a.root/name/f,d/f)
        exit=r['hystart_exits'][0] if r['hystart_exits'] else None
        q=r['queue'].get('flow0_visits',{})
        compact.append(dict(case=name,completion_s=r['completion_s'],app_bytes=r['delivered_bytes'],
          hystart=int(r['socket_configuration']['hystart_enabled']),
          drop_transmissions=r['distinct_tagged_drop_transmissions'],retx=r['retransmission_rows'],
          recovery=r['recovery_entries'],loss=r['loss_entries'],
          exit_s=int(exit['time_ns'])/1e9 if exit else '',exit_reason_mask=exit['reason_mask'] if exit else '',
          exit_cwnd_mss=int(exit['cwnd_bytes'])//1380 if exit else '',
          queue_visit_mean_ms=q.get('mean_ms',''),queue_visit_max_ms=q.get('max_ms',''),
          forecast_defer_count=r['hystart_event_counts'].get('FORECAST_DEFER',0),
          wall_seconds=r['source']['wall_seconds'],patch_sha256=r['source']['patch_sha256']))
    with (a.out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=compact[0].keys(),lineterminator='\n');w.writeheader();w.writerows(compact)
    comparisons={}
    if 'near-on-unobserved' in summaries:
        comparisons['passive_observation']=compare_measurements(a.root,'near-on','near-on-unobserved')
        assert comparisons['passive_observation']['all_measurements_byte_identical']
    if 'near-forecast' in summaries:
        comparisons['forecast_trajectory']=compare_measurements(a.root,'near-on','near-forecast')
    record=dict(analyzer_sha256=sha(Path(__file__)),cases=a.cases,comparison=comparisons,
                measurements='Ordered application completion and directly observed drops/retransmissions; queue mean/max only, no p95 inferred from bins.',
                limits='Declared deterministic conditions; no independent replay/seed replications here.')
    (a.out/'export.json').write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps(compact,indent=2))


if __name__=='__main__': main()
