"""Analyze and export actual completed cases; no simulations are launched."""
import argparse
import collections
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
spec=importlib.util.spec_from_file_location('compact',REPO/'code/predict-loss/summarize.py')
compact=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compact)


def policy(run,manifest):
    path=run/'logs_ns3/tcp_flow_0_orbit_loss.csv'
    if not path.exists():
        if manifest['definition']['mode']=='selective': raise ValueError('Missing policy trace')
        return dict(enabled=False,events=[],episodes=[])
    events=[]
    for row in csv.DictReader(path.open()):
        events.append({k:v if k=='event' else int(v) for k,v in row.items()})
    hints={h['start_ns']:h for h in manifest['hints']}
    episodes=[]
    for epoch,group in __import__('itertools').groupby(events,lambda r:r['epoch_ns']):
        group=list(group)
        begins=[r for r in group if r['event']=='COHORT_WAIT_BEGIN']
        if len(begins)>1: raise ValueError('More than one wait deadline in epoch')
        h=hints[epoch]
        for row in group:
            if row['threshold']!=3: raise ValueError('Selective policy changed K3')
            if row['event'].startswith('COHORT_WAIT_'):
                if row['deadline_ns']!=min(begins[0]['time_ns']+h['wait_ns'],h['end_ns']):
                    raise ValueError('Shared deadline extended/mismatched')
                if not (row['cohort_lo']<=row['seq']<row['cohort_hi'] and
                        row['last_sent_ns']<=epoch and 3<=row['sacked_pkts']<=h['packet_budget']):
                    raise ValueError('Ineligible sequence/time/SACK budget')
        if begins:
            first=begins[0]
            stops=[r for r in group if r['time_ns']>=first['time_ns'] and r['event'] in
                   ['COHORT_DEADLINE','ACK_MOVED_OUTSIDE_COHORT','BUDGET_EXCEEDED','OTHER_LOSS',
                    'STOCK_RECOVERY','STOCK_ECN','STOCK_RTO','EPOCH_END']]
            if not stops: raise ValueError('Censored selective wait')
            stop=stops[0]
            if stop['time_ns']>first['deadline_ns']: raise ValueError('Wait exceeded hard deadline')
            episodes.append(dict(epoch_ns=epoch,start_ns=first['time_ns'],end_ns=stop['time_ns'],
                deadline_ns=first['deadline_ns'],duration_s=(stop['time_ns']-first['time_ns'])/1e9,
                end_event=stop['event'],deferred_sequences=sorted({r['seq'] for r in group
                                      if r['event'].startswith('COHORT_WAIT_')})))
    return dict(enabled=True,events=events,event_counts=dict(collections.Counter(r['event'] for r in events)),
                episodes=episodes,shared_deadline_audit=True,K3_audit=True,
                source=compact.receipt(path))


def export(run,out):
    manifest=json.loads((run/'manifest.json').read_text())
    if manifest['status']!='success' or not manifest['runtime_unchanged'] or manifest.get('audit_exclude'):
        raise ValueError('Incomplete/excluded simulation')
    argv=[sys.executable,'-B',str(REPO/'code/kim-study/analyze_study.py'),str(run),'--include-bins',
          '--output',str(run/'analysis.json')]
    if manifest['definition']['kind']=='leo':
        argv += ['--path-truth',str(REPO/'code/kim-study/path_truth_200s.csv')]
    else: argv += ['--events','2']
    if not (run/'analysis.json').exists(): subprocess.run(argv,check=True,capture_output=True)
    summary=compact.summarize(run)
    summary['selective_policy']=policy(run,manifest)
    retx=list(csv.DictReader((run/'logs_ns3/tcp_flow_0_study_packets.csv').open())) if manifest['definition']['kind']=='micro' else None
    summary['finite_retransmission_times_ns']=[int(r['time_ns']) for r in retx if r['event']=='RETX'] if retx else None
    drop=run/'logs_ns3/orbit_actual_drop.csv'
    if manifest['definition'].get('actual_drop'):
        selected=list(csv.DictReader(drop.open()))
        if len(selected)!=1: raise ValueError('Expected exactly one selected actual drop')
        chosen={k:int(v) for k,v in selected[0].items()}
        installation=list(csv.DictReader((run/'logs_ns3/orbit_drop_install.csv').open()))
        if not any(r['device_type']=='ns3::GSLNetDevice' for r in installation):
            raise ValueError('Actual loss control not installed on GSL')
        def matching_drop(row):
            try:
                return int(row['node'])==1585 and int(row['device']) in {
                    int(item['device_id']) for item in installation} and all(
                    int(row[key])==chosen[key] for key in
                    ['flow_id','tx_id','tx_time_ns','seq','payload_bytes','time_ns'])
            except (ValueError,KeyError): return False
        matches=[r for r in csv.DictReader((run/'logs_ns3/study_drops.csv').open())
                 if matching_drop(r)]
        if len(matches)!=1 or matches[0]['layer']!='PhyRxDrop':
            raise ValueError('Selected original transmission has no unique physical drop record')
        recovery=[]
        earlier=[]
        for row in csv.DictReader((run/'logs_ns3/tcp_flow_0_study_packets.csv').open()):
            if (row['event']=='RETX' and int(row['flow_id'])==chosen['flow_id'] and
                int(row['seq'])==chosen['seq']):
                (recovery if int(row['time_ns'])>=chosen['time_ns'] else earlier).append(int(row['time_ns']))
        if not recovery: raise ValueError('No retransmission of selected genuine loss')
        summary['injected_actual_drop']=dict(selection=chosen,installation=installation,
            retransmission_times_ns=recovery,first_retransmission_after_drop_ns=recovery[0]-chosen['time_ns'],
            earlier_retransmission_times_ns=earlier,matched_physical_drop=matches[0],
            exact_identity_and_receiver_time_audit=True,
            source=compact.receipt(drop),trace_layer='PhyRxDrop')
    target=out/'cases'/manifest['case']
    target.mkdir(parents=True,exist_ok=False)
    (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for name in ['manifest.json','config_ns3.properties','schedule.csv']:
        if (run/name).exists(): shutil.copyfile(run/name,target/name)
    for name in ['tcp_flow_0_orbit_loss.csv','orbit_actual_drop.csv','orbit_drop_install.csv']:
        if (run/'logs_ns3'/name).exists(): shutil.copyfile(run/'logs_ns3'/name,target/name)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-loss-v2'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    summaries=[export(a.root/n,a.out) for n in a.cases]
    fields=list(summaries[0]['metrics'])
    with (a.out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader(); w.writerows(s['metrics'] for s in summaries)
    (a.out/'receipt.json').write_text(json.dumps(dict(tool=compact.receipt(Path(__file__)),
        phase='Post-simulation export; physical-drop join and after-drop RETX filter strengthened after all seven runs',
        cases=[dict(case=s['metrics']['case'],manifest=s['provenance']['manifest'],
                   full_analysis=s['provenance']['full_analysis']) for s in summaries]),indent=2)+'\n')
    print(json.dumps([s['metrics'] for s in summaries],indent=2))
