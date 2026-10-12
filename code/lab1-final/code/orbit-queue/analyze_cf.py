"""Posthoc fixed-policy routing comparison with exact pre-T75 prefix checks.

The shared queue calculations are reused with a distinct validator: complete
trajectory equality is deliberately NOT claimed for changed routing inputs.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('queue_analysis', HERE/'analyze.py')
shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
CUTOFF = 75_000_000_000


def prefix(path, mode):
    with path.open(newline='') as f:
        if mode == 'plain':
            return [row for row in csv.reader(f) if int(row[1]) < CUTOFF]
        data = list(csv.DictReader(f))
    if mode == 'timed':
        return [r for r in data if int(r['time_ns']) < CUTOFF]
    if mode == 'occupancy':
        groups = defaultdict(list)
        for r in data:
            if int(r['time_ns']) < CUTOFF:
                groups[(r['node_id'],r['device_id'])].append(r)
        return [(k,v) for k,v in sorted(groups.items())]
    assert mode in ('queue_bins','service_bins')
    ignored = ({'flush_time_ns','queue_packets_at_flush','queue_bytes_at_flush'}
               if mode == 'queue_bins' else {'cutoff_ns','device_tx_active_at_cutoff'})
    projected = [{k:v for k,v in r.items() if k not in ignored} for r in data
                 if int(r['bin_end_ns']) <= CUTOFF]
    return sorted(projected,key=lambda r:(int(r['bin_start_ns']),int(r['node_id']),
                                          int(r['device_id']),r['flow_id']))


def exact_prefix(natural, cf):
    methods = {
        'study_app_rx_node_1585_port_1024.csv':'timed',
        'study_rx_node_1585_port_1024.csv':'timed','study_drops.csv':'timed',
        'tcp_flow_0_cwnd.csv':'plain','tcp_flow_0_progress.csv':'plain','tcp_flow_0_rtt.csv':'plain',
        'tcp_flow_0_study_events.csv':'timed','tcp_flow_0_study_packets.csv':'timed',
        'tcp_flow_0_orbit_loss.csv':'timed','queue_focus.csv':'timed',
        'queue_occupancy.csv':'occupancy','queue_flow_state.csv':'timed',
        'queue_tc_drop.csv':'timed','orbit_drops.csv':'timed',
        'orbit_queue_bins.csv':'queue_bins','orbit_service_bins.csv':'service_bins'}
    report = {}
    for name, mode in methods.items():
        original = prefix(natural/'logs_ns3'/name,mode)
        modified = prefix(cf/'logs_ns3'/name,mode)
        assert original == modified, ('Pre-T75 divergence',name)
        count = sum(len(v) for _,v in original) if mode == 'occupancy' else len(original)
        report[name] = dict(mode=mode,rows=count,exact=True,
                            prefix_sha256=shared.mapping_sha(original))
        if mode == 'occupancy': report[name]['device_groups'] = len(original)
    static = ['study_drop_coverage.csv','orbit_coverage.csv','orbit_service_coverage.csv','queue_devices.csv']
    for name in static:
        assert shared.sha(natural/'logs_ns3'/name) == shared.sha(cf/'logs_ns3'/name)
        report[name] = dict(mode='static_full_file',exact=True,
                            sha256=shared.sha(cf/'logs_ns3'/name))
    return dict(cutoff_ns=CUTOFF,all_exact=True,files=report,
        exclusions=['timing_results.csv measures wallclock profiling.',
                    'tcp_flows.csv contains final ACK progress, so it has no temporal prefix.',
                    'Queue pending tables are final-cutoff measurements, not pre-T75 histories.',
                    'Queue bin flush_time/queue-at-flush and service cutoff/active-at-cutoff fields are excluded because their observation can be after T75.',
                    'Occupancy is compared in recorded order per device; synthetic held boundaries need not have global file-time order.'])


def late_summary(run):
    start,end = 77_500_000_000,80_500_000_000
    logs=run/'logs_ns3'; count=Counter()
    for r in shared.rows(logs/'study_app_rx_node_1585_port_1024.csv'):
        if start <= int(r['time_ns']) < end:
            count['app_bytes']+=int(r['payload_bytes'])
    for r in shared.rows(logs/'tcp_flow_0_study_packets.csv'):
        if start <= int(r['time_ns']) < end and r['event']=='RETX':
            count['retx_packets']+=1
    for r in shared.rows(logs/'tcp_flow_0_study_events.csv'):
        if start <= int(r['time_ns']) < end and r['event']=='CONG':
            count['recovery_entries']+=r['new_value']=='3'
            count['loss_state_entries']+=r['new_value']=='4'
    drops=[r for r in shared.rows(logs/'queue_tc_drop.csv') if start<=int(r['time_ns'])<end]
    source=Counter(); max_wait=0
    for r in shared.rows(logs/'orbit_queue_bins.csv'):
        if r['node_id']=='1584' and r['device_id']=='1' and start<=int(r['bin_start_ns']) and int(r['bin_end_ns'])<=end:
            for key in ['enqueued','dequeued','drop_before','drop_after','sojourn_samples','sojourn_sum_ns']:
                source[key]+=int(r[key])
            max_wait=max(max_wait,int(r['sojourn_max_ns']))
    for key in ['app_bytes','retx_packets','recovery_entries','loss_state_entries']:
        count.setdefault(key,0)
    return dict(start_ns=start,end_ns=end,**count,app_goodput_mbps=count['app_bytes']*8000/(end-start),
        tc_drop_count=len(drops),tc_drop_rows=drops,source_queue_visits=dict(source),
        source_served_mean_ns=source['sojourn_sum_ns']/source['sojourn_samples'] if source['sojourn_samples'] else None,
        source_served_max_ns=max_wait,source_time_weighted_occupancy=None,
        limit='Exact occupancy trace ends at77.5; later visit waits use aligned100ms bins, and source occupancy is not inferred from flush snapshots.')


def policy_summary(run):
    records=list(shared.rows(run/'logs_ns3/tcp_flow_0_orbit_loss.csv'))
    return dict(full_run_event_counts=dict(Counter(r['event'] for r in records)),
        focus_event_counts=dict(Counter(r['event'] for r in records if 74_500_000_000<=int(r['time_ns'])<77_500_000_000)),
        delayed_event_counts=dict(Counter(r['event'] for r in records if 77_500_000_000<=int(r['time_ns'])<80_500_000_000)),
        wait_begin_count=sum(r['event']=='COHORT_WAIT_BEGIN' for r in records),
        wait_rows=[r for r in records if r['event'].startswith('COHORT_WAIT_')])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--natural',type=Path,default=Path('/tmp/orbit-queue/selective-natural'))
    p.add_argument('--counterfactual',type=Path,default=Path('/tmp/orbit-queue-cf/selective-route75-delayed78'))
    p.add_argument('--input-receipt',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists(),'Refuse overwrite'
    input_record=json.loads(a.input_receipt.read_text())
    reference=json.loads((HERE/'reference-receipt.json').read_text())
    natural,_=shared.verify(a.natural,reference)
    cf=json.loads((a.counterfactual/'manifest.json').read_text())
    assert cf['status']=='success' and cf['exit_code']==0 and cf['source_unchanged'] and cf['runtime_unchanged']
    assert natural['runtime_files']==cf['runtime_files'] and natural['patch_sha256']==cf['patch_sha256']
    assert natural['state_static_sha256']==cf['state_static_sha256']
    assert not cf['policy_changed'] and cf['routing_input_changed'] and not cf['observer_only']
    assert shared.sha(a.natural/'schedule.csv')==shared.sha(a.counterfactual/'schedule.csv')
    assert cf['routing_counterfactual']['input_receipt_sha256']==shared.sha(a.input_receipt)
    assert cf['dynamic_input_sha256']==input_record['modified_dynamic_input_sha256']
    changes=[n for n in natural['dynamic_input_sha256'] if natural['dynamic_input_sha256'][n]!=cf['dynamic_input_sha256'][n]]
    assert set(changes)=={'fstate_75000000000.txt','fstate_78000000000.txt'}
    assert natural['dynamic_input_sha256']['fstate_75000000000.txt']==cf['dynamic_input_sha256']['fstate_78000000000.txt']
    for name,record in cf['output_files'].items():
        path=a.counterfactual/name
        assert path.stat().st_size==record['bytes'] and shared.sha(path)==record['sha256'],name
    state=Path(input_record['modified_state'])
    assert shared.mapping_sha({str(p.relative_to(state)):shared.sha(p) for p in sorted(state.rglob('*')) if p.is_file()})==input_record['modified_files_mapping_sha256']
    pre=exact_prefix(a.natural,a.counterfactual)
    # Reuse only queue/measurement calculations; the validator for changed
    # inputs is explicit and cannot claim whole-trajectory original equality.
    shared.verify=lambda run,ref:(cf,dict(pre75_prefix_exact=True,original_case='selective-natural',
        original_manifest_sha256=shared.sha(a.natural/'manifest.json'),
        original_launch_commit=natural['launch_commit'],new_launch_commit=cf['launch_commit'],
        entire_trajectory_equality_claimed=False))
    result=shared.analyze(a.counterfactual,reference)
    result['observer_only']=False
    result['qa']['input_state_equal']=False
    result['qa'].update(input_change_exactly_declared=True,pre75_prefix_exact=True,
                        same_policy_schedule=True,same_patch_and_runtime=True)
    result['caveats']=[s for s in result['caveats'] if not s.startswith('Same measurement trajectories')]
    result['caveats'].extend(input_record['assumptions'])
    record=dict(schema=1,helper_sha256=shared.sha(Path(__file__)),shared_helper_sha256=shared.sha(HERE/'analyze.py'),
        input_receipt_sha256=shared.sha(a.input_receipt),prefix=pre,counterfactual=result,
        late_transition={'selective-natural':late_summary(a.natural),
                         'selective-route75-delayed78':late_summary(a.counterfactual)},
        policy={'selective-natural':policy_summary(a.natural),
                'selective-route75-delayed78':policy_summary(a.counterfactual)})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps({'out':str(a.out),'sha256':shared.sha(a.out),'bytes':a.out.stat().st_size,
                      'prefix_files':len(pre['files']),'qa':result['qa']}))


if __name__=='__main__':
    main()
