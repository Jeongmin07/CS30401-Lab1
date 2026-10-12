"""Exact full-run queue/loss accounting for the fixed three-condition screen."""
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
WINDOWS={'whole':(0,200000000000),'post':(75000000000,75500000000),'focus':(74500000000,77500000000)}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def mapping(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rows(path):
    with path.open(newline='') as f:yield from csv.DictReader(f)


def names(t):return [n for n,(a,b) in WINDOWS.items() if a<=t<b]


def statistics(values):
    if not values:return dict(samples=0,mean_ns=None,p95_ns=None,p99_ns=None,max_ns=None)
    v=sorted(values);return dict(samples=len(v),mean_ns=sum(v)/len(v),p95_ns=v[math.ceil(.95*len(v))-1],p99_ns=v[math.ceil(.99*len(v))-1],max_ns=v[-1])


def identity(r):
    if r['flow_id']=='' or r['payload_bytes']=='' or int(r['payload_bytes'])<=0:return None
    assert r['flow_id']=='0' and r['tx_id']!='' and r['tx_time_ns']!='' and r['seq']!='','Unmapped tagged data loss'
    return tuple(r[k] for k in ['flow_id','tx_id','tx_time_ns','seq','payload_bytes'])


def verify(run):
    m=json.loads((run/'manifest.json').read_text());assert m['status']=='success' and m['exit_code']==0 and m['runtime_unchanged'] and m['source_unchanged']
    for name,record in m['output_files'].items():assert (run/name).stat().st_size==record['bytes'] and sha(run/name)==record['sha256'],name
    if m['case']=='control100':
        ref=json.loads((HERE/'reference-receipt.json').read_text());assert ref['all_manifest_output_hashes_verified']
        for name,record in ref['measurement_csvs'].items():assert m['output_files'][name]==record,('Legacy equivalence',name)
        for name,record in ref['input_files'].items():assert sha(run/name)==record['sha256']
        assert mapping(m['state_static_sha256'])==ref['state_static_mapping_sha256'] and mapping(m['dynamic_input_sha256'])==ref['dynamic_mapping_sha256']
    return m


def analyze(run):
    m=verify(run);logs=run/'logs_ns3';config=list(rows(logs/'bp_config.csv'));assert len(config)==1;config=config[0]
    assert config['mode']==m['queue_mode'] and config['device_max']==str(m['source_device_max_packets'])+'p'
    assert config['qdisc_max']==str(m['source_qdisc_max_packets'])+'p'
    coverage=list(rows(logs/'study_drop_coverage.csv'))
    root=[r for r in coverage if r['node']=='1584' and r['device']=='1' and r['layer']=='root_queue_disc_absent'];assert len(root)==1
    assert root[0]['connected']==('1' if m['queue_mode']=='off' else '0')
    if m['queue_mode']!='off':
        for layer in ['qdisc_DropBeforeEnqueue','qdisc_DropAfterDequeue']:
            assert any(r['node']=='1584' and r['device']=='1' and r['layer']==layer and r['connected']=='1' for r in coverage)
    assert all(r['connected']=='1' for r in coverage if r['layer']!='root_queue_disc_absent')
    summary=list(rows(logs/'bp_summary.csv'));assert len(summary)==1;s={k:int(v) for k,v in summary[0].items()}
    assert s['ingress']==s['served']+s['unique_source_discarded']+s['pending']
    assert s['pending']==s['pending_qdisc']+s['pending_device']+s['pending_transit']
    assert s['qdisc_received']==s['qdisc_enqueued']+s['qdisc_drop_before']
    assert s['qdisc_enqueued']-s['qdisc_dequeued']==s['pending_qdisc']
    assert s['qdisc_dequeued']==s['qdisc_sent']+s['qdisc_drop_after']+s['pending_transit']
    assert s['physical_drop_enabled']==int(m['physical_drop_first_original_seq1'])
    queue_counts=defaultdict(Counter);pending=Counter()
    for r in rows(logs/'orbit_queue_bins.csv'):
        k=(r['node_id'],r['device_id'],r['flow_id'])
        for field in ['enqueued','dequeued','drop_before','drop_after','sojourn_samples']:queue_counts[k][field]+=int(r[field])
    for r in rows(logs/'orbit_queue_pending.csv'):pending[(r['node_id'],r['device_id'],r['flow_id'])]+=int(r['pending_packets'])
    for k,c in queue_counts.items():assert c['enqueued']-c['dequeued']==pending[k] and c['drop_after']==0 and c['dequeued']==c['sojourn_samples'],k
    source_enq=sum(c['enqueued'] for k,c in queue_counts.items() if k[:2]==('1584','1'))
    source_deq=sum(c['dequeued'] for k,c in queue_counts.items() if k[:2]==('1584','1'))
    assert source_deq==s['served'] and source_enq==s['served']+s['pending_device']
    metrics={n:Counter() for n in WINDOWS};waits=defaultdict(list);discarded_waits=defaultdict(list);pending_waits=[]
    for r in rows(logs/'study_app_rx_node_1585_port_1024.csv'):
        for w in names(int(r['time_ns'])):metrics[w]['app_bytes']+=int(r['payload_bytes'])
    sender=set()
    for r in rows(logs/'tcp_flow_0_study_packets.csv'):
        if r['event']=='TX' and int(r['payload_bytes'])>0:sender.add(identity(r))
        if r['event']=='RETX':
            for w in names(int(r['time_ns'])):metrics[w]['retx_packets']+=1
    for r in rows(logs/'tcp_flow_0_study_events.csv'):
        if r['event']=='CONG':
            for w in names(int(r['time_ns'])):
                metrics[w]['recovery_entries']+=r['new_value']=='3';metrics[w]['loss_state_entries']+=r['new_value']=='4'
    visit_ids=set();served_rows=0
    for r in rows(logs/'bp_served.csv'):
        assert r['visit_id'] not in visit_ids;visit_ids.add(r['visit_id']);served_rows+=1
        total=int(r['total_source_wait_ns']);assert total==int(r['qdisc_wait_ns'])+int(r['device_wait_ns'])+int(r['handoff_requeue_wait_ns']) and total==int(r['time_ns'])-int(r['ingress_ns'])
        if r['tagged']=='1' and int(r['payload_bytes'])>0:assert identity(r) in sender
        for w in names(int(r['time_ns'])):waits[w].append(total)
    assert served_rows==s['served']
    loss_events=defaultdict(list);unmapped=Counter();canonical=Counter()
    for r in rows(logs/'study_drops.csv'):
        k=identity(r)
        if k is None:
            for w in names(int(r['time_ns'])):unmapped[w]+=1
            continue
        assert k in sender,'Network loss lacks exact sender transmission'
        event=(r['time_ns'],r['node'],r['device'],r['uid'],*k)
        canonical[event]+=1;loss_events[k].append(dict(time_ns=int(r['time_ns']),node=r['node'],device=r['device'],layer=r['layer']))
    outcome_count=pending_count=0
    for r in rows(logs/'bp_outcomes.csv'):
        assert r['visit_id'] not in visit_ids;visit_ids.add(r['visit_id'])
        if r['layer']=='pending':pending_count+=1;pending_waits.append(int(r['residence_ns']));continue
        outcome_count+=1
        for w in names(int(r['time_ns'])):discarded_waits[w].append(int(r['residence_ns']))
        k=identity(r)
        if k is not None:
            assert k in sender and k in loss_events,'Source discard missing from complete canonical loss coverage'
            assert any(x['time_ns']==int(r['time_ns']) and x['node']=='1584' for x in loss_events[k])
    assert outcome_count==s['unique_source_discarded'] and pending_count==s['pending'] and len(visit_ids)==s['ingress']
    for k,events in loss_events.items():
        t=min(e['time_ns'] for e in events)
        for w in names(t):metrics[w]['unique_all_layer_tx_losses']+=1
    source_native_area={};network_area={n:Counter() for n in WINDOWS}
    for r in rows(logs/'weighted_device_queues.csv'):
        a,b=int(r['bin_start_ns']),int(r['bin_end_ns']);assert a<=b and b-a<=100000000
        assert int(r['packet_ns'])<=int(r['peak_packets'])*(b-a) and int(r['byte_ns'])<=int(r['peak_bytes'])*(b-a)
        if (r['node_id'],r['device_id'])==('1584','1'):source_native_area[a]=int(r['packet_ns'])
        for w,(start,end) in WINDOWS.items():
            if start<=a and b<=end:network_area[w]['packet_ns']+=int(r['packet_ns']);network_area[w]['byte_ns']+=int(r['byte_ns'])
    area={n:Counter() for n in WINDOWS};source_busy=Counter();source_area_keys=set()
    for r in rows(logs/'bp_state_bins.csv'):
        a,b=int(r['bin_start_ns']),int(r['bin_end_ns']);assert a<=b and b-a<=100000000 and a not in source_area_keys;source_area_keys.add(a)
        assert int(r['device_packet_ns'])==source_native_area.get(a,0)
        assert int(r['packet_ns'])==int(r['qdisc_packet_ns'])+int(r['device_packet_ns'])+int(r['requeue_packet_ns'])
        for w,(start,end) in WINDOWS.items():
            if start<=a and b<=end:
                for field in ['packet_ns','byte_ns','qdisc_packet_ns','device_packet_ns','requeue_packet_ns','serializing_ns']:area[w][field]+=int(r[field])
                for field in ['peak_queued_packets','qdisc_peak_packets','device_peak_packets','requeue_peak_packets']:area[w][field]=max(area[w][field],int(r[field]))
    assert all(v==0 or k in source_area_keys for k,v in source_native_area.items())
    for r in rows(logs/'orbit_service_bins.csv'):
        if (r['node_id'],r['device_id'])!=('1584','1'):continue
        for w,(start,end) in WINDOWS.items():
            if start<=int(r['bin_start_ns']) and int(r['bin_end_ns'])<=end:source_busy[w]+=int(r['busy_ns'])
    for w,(start,end) in WINDOWS.items():
        for field in ['app_bytes','retx_packets','recovery_entries','loss_state_entries','unique_all_layer_tx_losses']:metrics[w].setdefault(field,0)
        assert source_busy[w]==area[w]['serializing_ns']<=end-start
        metrics[w].update(start_ns=start,end_ns=end,app_goodput_mbps=metrics[w]['app_bytes']*8000/(end-start),
            combined_mean_queued_packets=area[w]['packet_ns']/(end-start),qdisc_mean_packets=area[w]['qdisc_packet_ns']/(end-start),
            source_device_mean_packets=area[w]['device_packet_ns']/(end-start),requeue_mean_packets=area[w]['requeue_packet_ns']/(end-start),
            combined_mean_bytes=area[w]['byte_ns']/(end-start),peak_combined_queued_packets=area[w]['peak_queued_packets'],
            network_native_mean_queued_packets=network_area[w]['packet_ns']/(end-start),
            network_plus_qdisc_requeue_mean_packets=(network_area[w]['packet_ns']+area[w]['qdisc_packet_ns']+area[w]['requeue_packet_ns'])/(end-start),
            serialization_busy_fraction=source_busy[w]/(end-start),unmapped_drop_notifications=unmapped[w])
    return dict(case=m['case'],definition=m['definition'],queue_mode=m['queue_mode'],config=config,metrics={k:dict(v) for k,v in metrics.items()},
        served_source_residence={w:statistics(waits[w]) for w in WINDOWS},discarded_source_observed_residence={w:statistics(discarded_waits[w]) for w in WINDOWS},
        pending_source_age=statistics(pending_waits),native_summary=s,
        loss_notifications_by_layer=dict(Counter(e['layer'] for events in loss_events.values() for e in events)),
        unique_loss_count=len(loss_events),queue_conservation_groups=len(queue_counts),
        qa=dict(output_hashes=True,actual_root_coverage=True,source_ingress_conservation=True,native_queue_conservation=True,
            device_area_crosscheck=True,service_area_crosscheck=True,all_tagged_losses_match_sender_tx=True,source_losses_in_complete_coverage=True,
            original_12_measurement_csvs_equal=(m['case']=='control100')),
        source=dict(manifest_sha256=sha(run/'manifest.json'),launch_commit=m['launch_commit'],source_checkpoint=m['source_checkpoint'],
                    patch_sha256=m['patch_sha256'],runtime_mapping_sha256=mapping(m['runtime_files'])),
        caveats=['Nominal4+96 excludes requeued and serializing slots; both are observed separately.',
                 'Qdisc/native byte sizes include different layer headers; packet count and actual total residence are primary comparisons.',
                 'Source served residence is per packet TC ingress to serialization start; censored and dropped residence are separate.',
                 'All-layer loss counts deduplicate full transmitted-segment identities, not repeated notifications or UID alone.',
                 'One fixed deterministic natural trace per condition; screening gates do not prove universal performance.'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('/tmp/queue-backpressure'));p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();assert not args.out.exists(),'Refuse overwrite'
    results={name:analyze(args.root/name) for name in ['control100','fifo4-96','codel4-96']};base=results['control100'];gates={}
    for name in ['fifo4-96','codel4-96']:
        c=results[name];whole=c['metrics']['whole'];bw=base['metrics']['whole'];post=c['metrics']['post'];bp=base['metrics']['post']
        ratio=lambda a,b:None if b==0 else a/b
        gp=ratio(whole['app_goodput_mbps'],bw['app_goodput_mbps']);qm=ratio(post['combined_mean_queued_packets'],bp['combined_mean_queued_packets']);wr=ratio(c['served_source_residence']['post']['mean_ns'],base['served_source_residence']['post']['mean_ns'])
        checks=dict(goodput_retained=gp>=.995,post_mean_queue_halved=qm<=.5,post_served_wait_halved=wr<=.5,focus_unique_losses_at_most5=c['metrics']['focus']['unique_all_layer_tx_losses']<=5,
            whole_combined_queue_not_worse=whole['combined_mean_queued_packets']<=bw['combined_mean_queued_packets'],
            whole_served_wait_not_worse=c['served_source_residence']['whole']['mean_ns']<=base['served_source_residence']['whole']['mean_ns'],
            whole_unique_losses_not_worse=whole['unique_all_layer_tx_losses']<=bw['unique_all_layer_tx_losses'],
            whole_network_backlog_not_worse=whole['network_plus_qdisc_requeue_mean_packets']<=bw['network_plus_qdisc_requeue_mean_packets'],
            no_unmapped_drop_notifications=whole['unmapped_drop_notifications']==0)
        gates[name]=dict(goodput_ratio=gp,post_queue_ratio=qm,post_wait_ratio=wr,checks=checks,all_pass=all(checks.values()))
    record=dict(schema=1,helper_sha256=sha(Path(__file__)),reference_receipt_sha256=sha(HERE/'reference-receipt.json'),cases=results,prospective_gates=gates)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({'out':str(args.out),'sha256':sha(args.out),'gates':gates}))


if __name__=='__main__':main()
