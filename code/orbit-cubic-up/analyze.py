"""Read-only window/service source gate; preserve integer numerators and null claims."""
import argparse
from collections import Counter,defaultdict
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NS=10**9
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def rows(p):
    with p.open(newline='') as f:yield from csv.DictReader(f)
def ns(x):return int(Decimal(str(x))*NS)
def require(ok,message):
    if not ok:raise ValueError(message)

def analyze(run):
    manifest=json.loads((run/'manifest.json').read_text())
    require(manifest['status']=='success' and manifest['exit_code']==0,'Run incomplete')
    require(manifest['runtime_unchanged_after_run'],'Runtime changed')
    for name,entry in manifest['output_files'].items():
        p=run/name;require(p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],'Changed output: '+name)
    logs=run/'logs_ns3';windows=[]
    for name,bounds in manifest['declared_windows_s'].items():
        lo,hi=map(ns,bounds);windows.append({'name':name,'start_ns':lo,'end_ns':hi,'duration_ns':hi-lo})
    aggregate={w['name']:Counter() for w in windows};layers={w['name']:Counter() for w in windows}
    appfile=logs/'study_app_rx_node_1585_port_1024.csv';total=0
    for r in rows(appfile):
        require(int(r['flow_id'])==0,'Unexpected app flow');t=int(r['time_ns']);value=int(r['payload_bytes']);total+=value
        require(total==int(r['connection_total_rx_bytes'])==int(r['sink_total_rx_bytes']),'App totals differ')
        for w in windows:
            if w['start_ns']<=t<w['end_ns']:aggregate[w['name']]['app_bytes']+=value
    for r in rows(logs/'study_drops.csv'):
        t=int(r['time_ns'])
        for w in windows:
            if w['start_ns']<=t<w['end_ns']:layers[w['name']][r['layer']]+=1
    for r in rows(logs/'tcp_flow_0_study_events.csv'):
        t=int(r['time_ns']);event=r['event'];require(int(r['threshold'])==3,'Default threshold changed')
        if event=='CONG':
            for w in windows:
                if w['start_ns']<=t<w['end_ns']:
                    aggregate[w['name']]['recovery_entries']+=int(r['new_value']=='3')
                    aggregate[w['name']]['loss_entries']+=int(r['new_value']=='4')
    for r in rows(logs/'tcp_flow_0_study_packets.csv'):
        if r['event']!='RETX':continue
        t=int(r['time_ns'])
        for w in windows:
            if w['start_ns']<=t<w['end_ns']:aggregate[w['name']]['retransmissions']+=1
    # Conservation includes all flows/unknown metadata and terminal queued packets.
    balance=Counter();pending=Counter();queue_rows=list(rows(logs/'orbit_queue_bins.csv'))
    for r in queue_rows:
        key=(r['node_id'],r['device_id'],r['flow_id']);balance[key]+=int(r['enqueued'])-int(r['dequeued'])
        require(int(r['drop_after'])==0 and int(r['sojourn_samples'])==int(r['dequeued']),'Unexpected queue service semantics')
    for r in rows(logs/'orbit_queue_pending.csv'):
        pending[(r['node_id'],r['device_id'],r['flow_id'])]+=int(r['pending_packets'])
    require(all(x>=0 for x in balance.values()),'Negative queue balance')
    require({k:v for k,v in balance.items() if v}=={k:v for k,v in pending.items() if v},'Queue conservation differs')
    # Device1584/1 is the only physical source GSL; not a claim every path bottleneck is this device.
    service_rows=list(rows(logs/'orbit_service_bins.csv'));busy_per_bin=Counter()
    for r in service_rows:
        busy_per_bin[(r['node_id'],r['device_id'],r['bin_start_ns'])]+=int(r['busy_ns'])
    require(all(0<=x<=100000000 for x in busy_per_bin.values()),'Overlapping physical service')
    observations=list(rows(logs/'orbit_window.csv'))
    require(observations and all(int(r['flow_id'])==0 for r in observations),'Wrong window flow')
    require(all(int(a['time_ns'])<=int(b['time_ns']) for a,b in zip(observations,observations[1:])),'Window time decreases')
    # Last callback at the same simulation time is the post-send snapshot.
    states=[]
    for r in observations:
        if states and states[-1]['time_ns']==r['time_ns']:states[-1]=r
        else:states.append(r)
    cut=ns(manifest['definition']['duration']);steps=[]
    truth=list(rows(HERE.parents[1]/'code/kim-study/path_truth_200s.csv'))
    for before,after in zip(truth,truth[1:]):
        if after['path_changed']=='1' and float(after['rtt_prop_ms'])>float(before['rtt_prop_ms'])+.05:
            t=ns(after['t_s']);pre=next(r for r in reversed(states) if int(r['time_ns'])<t)
            steps.append({'time_ns':t,'old_prop_rtt_ms':float(before['rtt_prop_ms']),'new_prop_rtt_ms':float(after['rtt_prop_ms']),'ratio':float(after['rtt_prop_ms'])/float(before['rtt_prop_ms']),'last_observer_before_step':{k:int(pre[k]) if k not in ['phase'] else pre[k] for k in ['time_ns','phase','cwnd_bytes','ssthresh_bytes','pipe_bytes','rwnd_bytes','available_window_bytes','unsent_bytes','cong_state','cwnd_limited','srtt_ns']},'header_only_new_prop_bdp_bytes':manifest['definition']['rate']*1e6*1380/1434*float(after['rtt_prop_ms'])/1000/8})
    for w in windows:
        lo,hi=w['start_ns'],w['end_ns'];name=w['name'];a=aggregate[name]
        w.update(app_bytes=a['app_bytes'],app_goodput_mbps=a['app_bytes']*8000/(hi-lo),retransmissions=a['retransmissions'],recovery_entries=a['recovery_entries'],loss_entries=a['loss_entries'],drop_events_by_layer=dict(layers[name]))
        s=[r for r in service_rows if r['node_id']=='1584' and r['device_id']=='1' and lo<=int(r['bin_start_ns']) and int(r['bin_end_ns'])<=hi]
        source_busy=sum(int(r['busy_ns']) for r in s)
        q=[r for r in queue_rows if r['node_id']=='1584' and r['device_id']=='1' and lo<=int(r['bin_start_ns']) and int(r['bin_end_ns'])<=hi]
        visits=sum(int(r['sojourn_samples']) for r in q);wait=sum(int(r['sojourn_sum_ns']) for r in q)
        w.update(source_gsl_busy_ns=source_busy,source_gsl_busy_fraction=source_busy/(hi-lo),source_gsl_idle_fraction=1-source_busy/(hi-lo),source_device_queue_visits=visits,source_device_queue_wait_sum_ns=wait,source_device_mean_served_wait_ms=wait/visits/1e6 if visits else None,source_device_max_served_wait_ms=max([int(r['sojourn_max_ns']) for r in q],default=0)/1e6)
        weighted=Counter();extrema={k:[] for k in ['cwnd_bytes','pipe_bytes','rwnd_bytes','available_window_bytes']}
        for i,r in enumerate(states):
            start=int(r['time_ns']);end=int(states[i+1]['time_ns']) if i+1<len(states) else cut
            dt=max(0,min(end,hi)-max(start,lo))
            if not dt:continue
            cwnd,rwnd,aw,segment=map(int,[r['cwnd_bytes'],r['rwnd_bytes'],r['available_window_bytes'],r['segment_bytes']])
            open_state=int(r['cong_state'])==0;has_data=int(r['unsent_bytes'])>0
            blocked=open_state and has_data and cwnd<=rwnd and aw<segment
            weighted['observed_covered_ns']+=dt;weighted['open_data_cwnd_blocked_ns']+=dt*blocked
            weighted['non_open_ns']+=dt*(not open_state);weighted['rwnd_smaller_than_cwnd_ns']+=dt*(rwnd<cwnd)
            weighted['no_unsent_data_ns']+=dt*(not has_data)
            for k in extrema:extrema[k].append(int(r[k]))
        w['window_state_sample_hold']=dict(weighted)
        w['window_state_ranges']={k:[min(v),max(v)] if v else None for k,v in extrema.items()}
    require(total<manifest['definition']['max_bytes'],'Unexpected finite completion')
    return {'case':manifest['case'],'manifest_sha256':sha(run/'manifest.json'),'app_bytes_total':total,'flow_complete':False,'fct_s':None,'queue_conservation_verified':True,'source_gsl_device':[1584,1],'path_lengthening_steps':steps,'windows':windows,'provenance':{'run_path':str(run),'manifest_path':str(run/'manifest.json'),'manifest_bytes':(run/'manifest.json').stat().st_size,'launch_repo_commit':manifest['repo_commit'],'launch_repo_dirty':manifest['repo_dirty'],'runner_sha256':manifest['runner_sha256'],'patch_sha256':manifest['patch_sha256'],'runtime_unchanged_after_run':manifest['runtime_unchanged_after_run'],'analyzer_sha256':sha(Path(__file__))},'limits':['Window-blocked sample-hold occupancy is not independently attributable link idle or a continuous socket trace outside focus windows.','Cwnd-limited flag is the existing cached flag; actual available/pipe comes from the original getter call.','Source GSL busy time is real physical serialization activity; route changes and later-hop queues may limit delivery separately.','Source device served queue visits include control packets and exclude unfinished queued visits.','Drop layer rows are not combined as unique physical losses.','No policy benefit, statistical replication, or exact capacity optimum is asserted by this diagnostic.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Output must be new');result=analyze(a.run);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case':result['case'],'app_bytes':result['app_bytes_total'],'windows':[{k:w[k] for k in ['name','app_goodput_mbps','source_gsl_busy_fraction','retransmissions','recovery_entries']} for w in result['windows']]}))
if __name__=='__main__':main()
