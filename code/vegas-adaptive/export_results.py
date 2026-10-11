"""Publish complete small analysis summaries and a window/flow results table."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--runs',type=Path,default=Path('/tmp/cs30401-vegas'))
p.add_argument('--analysis',type=Path,default=Path('/tmp/vegas-adaptive-analysis'))
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists(), 'Refuse existing publication output'
a.out.mkdir(parents=True)
results=[]
sources=[]
for family in ('leo','fixed-comp','fixed','step'):
    for mode in ('base','adaptive'):
        name=f'a1-{family}-{mode}'
        src=a.analysis/name/'summary.json'
        summary=json.loads(src.read_text())
        manifest=json.loads((a.runs/name/'case.json').read_text())
        assert manifest['status']=='complete' and manifest['exit_code']==0
        assert manifest['source_commit']=='7ac0751235dc1ecb14b3042622ac50990429f17c'
        assert manifest['policy']['adaptive_thresholds']==(mode=='adaptive')
        assert not manifest['policy']['recent_min_renewal']
        folder=a.out/'cases'/name
        folder.mkdir(parents=True)
        shutil.copy2(src,folder/'summary.json')
        shutil.copy2(a.runs/name/'case.json',folder/'case.json')
        shutil.copy2(a.analysis/name/'windows.csv',folder/'windows.csv')
        sources.append({'case':name,'full_analysis_sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
        for w in summary['windows']:
            values=[v['application_goodput_mbps'] for v in w['flows'].values()]
            all_active=len(values)>1 and all(v['active_duration_ns']==w['end_ns']-w['start_ns'] for v in w['flows'].values())
            jain=sum(values)**2/(len(values)*sum(v*v for v in values)) if len(values)>1 and sum(values) and all_active else None
            queues=[q for q in w.get('queue_sojourn',[]) if q['direction']=='forward' and q['group']=='all']
            occ=[q for q in w.get('queue_occupancy',[]) if q['direction']=='forward']
            for fid,v in w['flows'].items():
                results.append({'case':name,'family':family,'mode':mode,'window':w['window'],
                    'start_ns':w['start_ns'],'end_ns':w['end_ns'],'flow_id':fid,
                    'application_bytes':v['application_bytes'],'goodput_mbps':v['application_goodput_mbps'],
                    'aggregate_mbps':w['application_sum_goodput_mbps'],'jain':jain,
                    'forward_queue_mean_ms':queues[0]['mean_ns']/1e6 if queues else None,
                    'forward_queue_mean_packets':occ[0]['time_weighted_mean_packets'] if occ else None,
                    'retransmissions':v['official_retransmission_rows'],'recovery_entries':v['recovery_entries'],
                    'LOSS_entries':v['LOSS_entries'],'TcDrop_all_flows':w['drop_rows_by_layer'].get('TcDrop',0)})
with (a.out/'results.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(results[0]),lineterminator='\n')
    writer.writeheader(); writer.writerows(results)
(a.out/'export.json').write_text(json.dumps({'source_commit':'7ac0751235dc1ecb14b3042622ac50990429f17c',
    'full_analysis_sources':sources,'results_rows':len(results),'scope':'Unabridged small analysis JSON, original launch manifests, all analyzed window/flow rows. Raw traces remain in the release archive.'},indent=2)+'\n')
print(json.dumps({'cases':len(sources),'rows':len(results),'out':str(a.out)}))
