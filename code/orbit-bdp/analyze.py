"""Validate actual delivery/queue accounting and compare four declared orbit cases."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def require(value,message):
    if not value:raise ValueError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-bdp'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Output must be new')
    helper=REPO/'code/bbr-route/analyze_pilot.py'
    spec=importlib.util.spec_from_file_location('observer_analysis',helper)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.WINDOWS={'whole':(0,40),'steady':(10,40),'shortening':(25.7,28.2)}
    records=[];flat=[];manifests={};second_bins=[];device_queues=[]
    for rate in (100,10):
        for mode in ('base','orbit'):
            name=f'bbr{rate}-{mode}40';run=a.root/name
            manifest=json.loads((run/'manifest.json').read_text());manifests[name]=manifest
            require(manifest['windows']=={k:list(v) for k,v in mod.WINDOWS.items()},'Window differs from declaration')
            for path,entry in manifest['outputs'].items():
                actual=run/path
                require(actual.stat().st_size==entry['bytes'] and sha(actual)==entry['sha256'],'Changed run output: '+path)
            record,seconds,devices=mod.analyze(run)
            second_bins.extend(seconds);device_queues.extend(devices)
            trace=rows(run/'logs_ns3/orbit_bdp_state.csv')
            require(trace and {int(r['flow_id']) for r in trace}=={0},'Wrong orbit flow trace')
            enabled=mode=='orbit'
            require(all(bool(int(r['enabled']))==enabled for r in trace),'Orbit enable mismatch')
            active=[r for r in trace if int(r['active'])]
            changed=[r for r in active if r['original_target_bytes']!=r['actual_target_bytes']]
            require(all(int(r['bbr_state'])==2 for r in active),'Policy active outside ProbeBW')
            if enabled:require(active and changed,'Policy never changed an actual target')
            else:require(not active and all(r['original_target_bytes']==r['actual_target_bytes'] for r in trace),'Off path mutated target')
            require(all(int(r['lookup_time_ns'])==int(r['time_ns'])+int(r['geo_now_ns']) for r in trace),'Wrong forecast horizon')
            record['policy_trace']={'sha256':sha(run/'logs_ns3/orbit_bdp_state.csv'),'rows':len(trace),
                'active_rows':len(active),'changed_target_rows':len(changed),
                'actual_target_range_bytes':[min(int(r['actual_target_bytes']) for r in trace),max(int(r['actual_target_bytes']) for r in trace)],
                'observed_min_rtt_range_ms':[min(int(r['min_rtt_ns']) for r in trace)/1e6,max(int(r['min_rtt_ns']) for r in trace)/1e6]}
            records.append(record)
            for w in record['windows']:
                flat.append({'case':name,'window':w['window'],'start_s':w['start_s'],'end_s':w['end_s'],
                    'app_goodput_mbps':w['aggregate_app_goodput_mbps'],
                    'mean_served_queue_visit_ms':w['served_queue_visit_mean_wait_ms'],
                    'max_served_queue_visit_ms':w['served_queue_visit_max_wait_ms'],
                    'drops_by_layer':json.dumps(w['drop_events_by_layer'],sort_keys=True)})
        left=manifests[f'bbr{rate}-base40'];right=manifests[f'bbr{rate}-orbit40']
        for key in ['config_sha256','schedule_sha256','runtime_files','geometry_sha256','dynamic_input_sha256',
                    'state_static_sha256','patch_sha256','sim_seconds','rate_mbps','queue_packets','seed']:
            require(left[key]==right[key],'Paired input differs: '+key)
    comparisons=[]
    for rate in (100,10):
        for window in mod.WINDOWS:
            x=next(r for r in flat if r['case']==f'bbr{rate}-base40' and r['window']==window)
            y=next(r for r in flat if r['case']==f'bbr{rate}-orbit40' and r['window']==window)
            comparisons.append({'rate_mbps':rate,'window':window,
                'baseline_app_mbps':x['app_goodput_mbps'],'policy_app_mbps':y['app_goodput_mbps'],
                'app_goodput_delta_pct':100*(y['app_goodput_mbps']/x['app_goodput_mbps']-1),
                'baseline_queue_visit_mean_ms':x['mean_served_queue_visit_ms'],
                'policy_queue_visit_mean_ms':y['mean_served_queue_visit_ms']})
    compatibility=[]
    previous=json.loads((REPO/'docs/experiments/assets/20261012-bbr-route/equivalence-original-on.json').read_text())
    baseline=a.root/'bbr100-base40/logs_ns3'
    for row in previous['checks']:
        value=sha(baseline/row['file'])
        compatibility.append({'file':row['file'],'new_sha256':value,'original_sha256':row['reference_sha256'],'equal':value==row['reference_sha256']})
    require(all(r['equal'] for r in compatibility),'Baseline legacy measurement changed')
    a.out.mkdir(parents=True)
    for path,values in [('results.csv',flat),('comparison.csv',comparisons),
                        ('second-bins.csv',second_bins),('device-queues.csv',device_queues)]:
        with (a.out/path).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
    result={'analyzer_sha256':sha(__file__),'reused_helper_sha256':sha(helper),'cases':records,
            'comparisons':comparisons,'compatibility_previous_original_measurements':compatibility,
            'limits':['Four deterministic paired cases, no statistical replicates.',
                'Exact operator future geometry; no forecast-error or notification implementation.',
                'Queue statistics are served device visits including ACKs; not end-to-end queue RTT.',
                'Drop hook layers and BBR sampled loss bytes are not unique packet-loss or retransmission counts.',
                'Internal measured RTprop and ProbeRTT are unchanged; only normal ProbeBW cwnd target BDP RTT changes.',
                '40s cutoff, first route shortening; not a 200s/other-route generalization.']}
    (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparisons':comparisons,'compatibility_all_equal':True,'out':str(a.out)},indent=2))

if __name__=='__main__':main()
