"""Generate numerical Table II and an inspectable section/specification map."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path,records):
    fields=list(dict.fromkeys(k for record in records for k in record))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(records)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--spec',type=Path,default=Path(__file__).resolve().parent.parent/'common.py')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    data=json.loads(a.data.read_text());cases=data['cases'];roles=data['report_roles']
    finite=[('stock_finite','Stock'),('selective_finite','Selective'),('tail_finite','Selective + tail'),('capacity_finite','+ Capacity pacing')]
    bulk=[('stock_bulk','Stock'),('tail_bulk','Selective + tail'),('capacity_bulk','+ Capacity pacing')]
    rows=[];tex=[r'\begin{table}[t]',r'\caption{Effect magnitudes and costs in the matched controls}',r'\label{tab:magnitudes}',
        r'\centering',r'\begin{tabular}{lrr}',r'\toprule',r'\multicolumn{3}{l}{Completed 20-MSS first-loss transfer}\\',
        r'Policy & FCT (ms) & Tail TX\\',r'\midrule']
    for role,label in finite:
        name=roles[role];case=cases[name];m=case['metrics']
        assert m['transfer_complete'] and m['receiver_bytes']==m['expected_finite_bytes'],'Finite data incomplete'
        value=m['fct_s']*1000;admissions=case['tail_admissions']
        rows.append(dict(family='finite20',role=role,case=name,policy=label,fct_ms=value,tail_admissions=admissions))
        tex.append(f'{label} & {value:.6f} & {admissions}'+r'\\')
    tex += [r'\midrule',r'\multicolumn{3}{l}{Natural 200 s bulk; no finite FCT}\\',r'Policy & Goodput (Mbps) & Data losses\\',r'\midrule']
    for role,label in bulk:
        name=roles[role];m=cases[name]['metrics'];assert m['fct_s'] is None
        rows.append(dict(family='natural200',role=role,case=name,policy=label,goodput_mbps=m['receiver_goodput_mbps'],data_losses=m['distinct_tagged_drops']))
        tex.append(f"{label} & {m['receiver_goodput_mbps']:.7f} & {m['distinct_tagged_drops']}"+r'\\')
    tex += [r'\bottomrule',r'\end{tabular}',r'\end{table}']
    (a.out/'magnitudes.tex').write_text('\n'.join(tex)+'\n',newline='\n');write_csv(a.out/'table-II.csv',rows)

    # Table I is a fixed specification overview, not a measured performance table.
    # Record the exact executable case declarations separately from numerical results.
    spec=importlib.util.spec_from_file_location('report_fixed_spec',a.spec);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    declarations=module.CASES
    fixed=[]
    for name,item in declarations.items():
        fixed.append(dict(case=name,profile=item['profile'],category=item['category'],
            definition=json.dumps(item['definition'],sort_keys=True,separators=(',',':')),
            source_queue_mode=item.get('queue_mode',''),source_device_max=item.get('device_max',''),source_qdisc_max=item.get('qdisc_max','')))
    write_csv(a.out/'table-I-spec-map.csv',fixed)
    metrics={name:case['metrics'] for name,case in cases.items()}
    windows={name:case.get('windows',{}) for name,case in cases.items()}
    actual_losses={name:case['actual_drop'] for name,case in cases.items() if case.get('actual_drop')}
    compact_queues={}
    for name,case in cases.items():
        queue=case.get('queue')
        if not queue:continue
        source=queue.get('source',{})
        if 'windows' in source:
            source={w:{k:v for k,v in values.items() if k in ['occupancy','served_sojourn','visits','serialization_busy_fraction','tc_drop_count','stop_count','wake_count']}
                    for w,values in source['windows'].items()}
        compact_queues[name]=dict(source=source,whole_source_served_wait=queue.get('whole_source_served_wait'),
            source_residence=queue.get('source_residence'),native_summary=queue.get('native_summary'))
    stock=cases[roles['stock_bulk']]['metrics'];tail=cases[roles['tail_bulk']]['metrics'];cap=cases[roles['capacity_bulk']]['metrics']
    values=dict(schema=1,phase=data['phase'],data_sha256=sha(a.data),helper_sha256=sha(Path(__file__)),
        table_I_fixed_spec=dict(source=str(a.spec),sha256=sha(a.spec),cases=declarations,aliases=module.ALIASES,
            qualification='Specification overview is grounded in immutable executable declarations; fresh analyzer checks actual manifest definitions against them.'),
        table_II=rows,metrics=metrics,windows=windows,actual_losses=actual_losses,queues=compact_queues,
        selective_episodes={name:case.get('selective_episodes',[]) for name,case in cases.items()},
        tail_admissions={name:case.get('tail_admissions') for name,case in cases.items()},
        derived=dict(natural_selective_extra_bytes=tail['receiver_bytes']-stock['receiver_bytes'],
            natural_selective_goodput_change_pct=100*(tail['receiver_goodput_mbps']/stock['receiver_goodput_mbps']-1),
            capacity_vs_current_goodput_change_pct=100*(cap['receiver_goodput_mbps']/tail['receiver_goodput_mbps']-1)),
        section_numeric_map={
            'Introduction/Problem Statement':'Verified trace acceptance and source mechanisms; no general performance number is inferred from geometry.',
            'Proposed Ideas':'Executable forward-hint rule and tail eligibility; configuration equations, not fitted result values.',
            'Experiment Setup/Table I':'table-I-spec-map.csv and immutable common.py case declarations; actual commands/input hashes in each fresh manifest.',
            'Evaluation A/Fig1':'stock_bulk and tail_bulk metrics, windows.first/windows.legacy, selective_episodes; figure_series.cwnd.',
            'Evaluation B/Fig2/Table II':'stock/selective/tail/capacity_finite metrics and tail_admissions; leo10-drop-base/tail actual_drop; micro21 boundary metrics.',
            'Evaluation C/Fig3':'source queue pre/post/focus fields, route_delayed source bins and exact prefix/input receipts; no SRTT queue proxy.',
            'Evaluation D/Table II':'capacity/native/tail bulk metrics, all-layer loss accounting; loss-current/loss-selected actual_drop, micro-selected native_pacing.'})
    (a.out/'values.json').write_text(json.dumps(values,indent=2,allow_nan=False)+'\n',newline='\n')
    receipt=dict(data=dict(path=str(a.data),sha256=sha(a.data)),helper_sha256=sha(Path(__file__)),
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in a.out.iterdir() if p.is_file()})
    (a.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',newline='\n')
    print(json.dumps(dict(out=str(a.out),numerical_rows=len(rows),fixed_conditions=len(fixed),data_sha256=sha(a.data))))


if __name__=='__main__':main()
