"""Export completed one-tail cases and independently join actual extra original transmissions."""
import argparse
import collections
import csv
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
spec=importlib.util.spec_from_file_location('selective_export',REPO/'code/orbit-loss/analyze.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
receipt=base.compact.receipt


def tail_audit(run,manifest,policy):
    trace=run/'logs_ns3/tcp_flow_0_orbit_loss_tail.csv'
    enabled=manifest['tail_admission']
    if not trace.exists():
        if manifest['definition']['mode']=='selective': raise ValueError('Missing tail trace')
        return dict(enabled=enabled,events=[],admissions=[],count=0)
    events=[{k:v if k=='event' else int(v) for k,v in row.items()}
            for row in csv.DictReader(trace.open())]
    admissions=[r for r in events if r['event']=='TAIL_ADMIT']
    if admissions and not enabled: raise ValueError('Disabled policy admitted data')
    if any(n>1 for n in collections.Counter(r['epoch_ns'] for r in admissions).values()):
        raise ValueError('Multiple extra admissions per epoch')
    for r in admissions:
        if not (0<r['admitted_bytes']==r['unsent_bytes']<=1380 and r['new_sack_bytes']>0 and
                r['pipe_after']==r['pipe_before']+r['admitted_bytes'] and
                r['pipe_after']<=r['cwnd_bytes']+1380 and r['used_before']==0 and r['used_after']==1 and
                r['seq']+r['admitted_bytes']<=r['receiver_right_edge'] and r['cong_state']==1 and
                (r['close_on_empty'] or r['shutdown_send']) and r['time_ns']<r['deadline_ns']):
            raise ValueError('Tail admission boundary violation')
        if r['ordinary_window_bytes']>=r['unsent_bytes']:
            raise ValueError('Admission bypassed available ordinary allowance')
        episode=next((e for e in policy['episodes'] if e['epoch_ns']==r['epoch_ns']),None)
        if not episode or not episode['start_ns']<=r['time_ns']<episode['end_ns']:
            raise ValueError('Extra transmission outside an actual wait')
        if episode['deadline_ns']!=r['deadline_ns']: raise ValueError('Tail changed wait deadline')
    packets=run/'logs_ns3/tcp_flow_0_study_packets.csv'
    chosen={r['seq']:r for r in admissions}
    observed={seq:[] for seq in chosen}
    retrans={seq:[] for seq in chosen}
    for row in csv.DictReader(packets.open()):
        if row['event'] not in ['TX','RETX'] or not row['payload_bytes']:continue
        seq=int(row['seq'])
        if seq in chosen:
            (observed if row['event']=='TX' else retrans)[seq].append(
                {k:int(row[k]) for k in ['time_ns','seq','payload_bytes','tx_id','flags','cong_state']})
    joins=[]
    for r in admissions:
        rows=observed[r['seq']]
        actual=[p for p in rows if p['time_ns']==r['time_ns'] and p['payload_bytes']==r['admitted_bytes']]
        if len(actual)!=1 or any(p['time_ns']<r['time_ns'] for p in rows):
            raise ValueError('Admission is not an independently observed original new TX')
        if any(p['time_ns']==r['time_ns'] for p in retrans[r['seq']]):
            raise ValueError('Admission trace describes a retransmission')
        joins.append(dict(admission=r,actual_original_tx=actual[0],later_retransmissions=retrans[r['seq']]))
    return dict(enabled=enabled,events=events,event_counts=dict(collections.Counter(r['event'] for r in events)),
        admissions=joins,count=len(admissions),admitted_bytes=sum(r['admitted_bytes'] for r in admissions),
        per_epoch_maximum_one=True,pipe_receiver_window_original_tx_deadline_audit=True,
        source=receipt(trace),qualification='Only observed admissions are dynamically validated; untriggered zero-window, extra-tail-loss, ECN and RTO branches are not empirical safety proofs.')


def export(run,out):
    summary=base.export(run,out)
    manifest=json.loads((run/'manifest.json').read_text())
    summary['tail_policy']=tail_audit(run,manifest,summary['selective_policy'])
    dst=out/'cases'/manifest['case']
    (dst/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    trace=run/'logs_ns3/tcp_flow_0_orbit_loss_tail.csv'
    if trace.exists():shutil.copyfile(trace,dst/trace.name)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/tmp/orbit-tail'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    data=[export(a.root/n,a.out) for n in a.cases]
    columns=list(data[0]['metrics'])+['tail_admissions','tail_admitted_bytes']
    with (a.out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for s in data:w.writerow(dict(s['metrics'],tail_admissions=s['tail_policy']['count'],
            tail_admitted_bytes=s['tail_policy'].get('admitted_bytes',0)))
    (a.out/'receipt.json').write_text(json.dumps(dict(tool=receipt(Path(__file__)),
        dependency=receipt(REPO/'code/orbit-loss/analyze.py'),
        cases=[dict(case=s['metrics']['case'],manifest=s['provenance']['manifest'],
            full_analysis=s['provenance']['full_analysis']) for s in data]),indent=2)+'\n')
    print(json.dumps([dict(s['metrics'],tail_admissions=s['tail_policy']['count']) for s in data],indent=2))
