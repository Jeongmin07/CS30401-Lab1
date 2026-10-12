"""Three vector report figures from normalized, source-backed run evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig,path):
    # Omitting wall-clock metadata makes same-version PDF output repeatable.
    fig.savefig(path,metadata={'Creator':'CS30401 Team 5 figure builder','CreationDate':None,'ModDate':None})
    preview=path.with_suffix('.png');fig.savefig(preview,dpi=220)
    plt.close(fig)
    return [dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in [path,preview]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();data=json.loads(a.data.read_text());roles=data['report_roles'];cases=data['cases']
    required=['stock_bulk','tail_bulk','route_delayed','capacity_bulk','stock_finite','selective_finite','tail_finite','capacity_finite']
    assert all(name in roles and roles[name] in cases for name in required),'Missing report role/case'
    a.out.mkdir(parents=True,exist_ok=False)
    case=lambda role:cases[roles[role]]
    colors={'stock':'#4C596A','selective':'#007F78','delayed':'#B87528','paced':'#73559E'}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':9,'axes.labelsize':9,
        'xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8,'axes.spines.top':False,
        'axes.spines.right':False,'pdf.fonttype':42,'pdf.compression':6})
    outputs=[];plotted={}

    fig,ax=plt.subplots(figsize=(3.45,2.6),layout='constrained')
    episode={}
    for role,label,color in [('stock_bulk','Stock',colors['stock']),('tail_bulk','Selective + tail',colors['selective'])]:
        series=case(role)['figure_series']['cwnd']
        assert len(series)>=2 and all(len(row)==2 for row in series)
        assert all(series[i][0]<=series[i+1][0] for i in range(len(series)-1))
        xs=[row[0]/1e9 for row in series];ys=[row[1]/1380 for row in series]
        ax.step(xs,ys,where='post',label=label,color=color,linewidth=1.5)
        episode[roles[role]]=dict(cwnd_rows=len(series),cwnd=series)
    ax.axvline(26.2,color='#777777',linewidth=.8,linestyle='--')
    ax.set(xlim=(25.9,26.6),xlabel='Simulation time (s)',ylabel='Congestion window (MSS)')
    ax.grid(axis='y',alpha=.18);ax.legend(loc='best',frameon=False)
    ax.text(.02,.02,'Forecast shortening at 26.2 s',transform=ax.transAxes,fontsize=8,
            va='bottom',bbox=dict(facecolor='white',edgecolor='none',alpha=.9))
    outputs+=save(fig,a.out/'natural-event.pdf');plotted['natural-event']=episode

    fig,ax=plt.subplots(figsize=(3.45,2.45),layout='constrained')
    labels=['Stock','Selective','+ 1-MSS\ntail','+ Capacity\npacing']
    rolelist=['stock_finite','selective_finite','tail_finite','capacity_finite']
    vals=[float(case(role)['metrics']['fct_s'])*1000 for role in rolelist]
    assert all(float(case(role)['metrics']['receiver_bytes'])==27600 for role in rolelist),'Finite delivery incomplete'
    ax.bar(range(4),vals,color=[colors['stock'],'#B87528',colors['selective'],colors['paced']],width=.65)
    for i,value in enumerate(vals):ax.text(i,value+7,f'{value:.3f}',ha='center',fontsize=8.5)
    ax.set(xticks=range(4),xticklabels=labels,ylabel='File completion time (ms)',ylim=(0,max(vals)*1.16))
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    outputs+=save(fig,a.out/'finite-cost.pdf')
    plotted['finite-cost']={roles[role]:dict(fct_ms=value,delivered_bytes=case(role)['metrics']['receiver_bytes']) for role,value in zip(rolelist,vals)}

    fig,ax=plt.subplots(figsize=(3.45,2.85),layout='constrained');queue_data={}
    queue_roles=[('stock_bulk','Stock',colors['stock'],'-'),('tail_bulk','Selective',colors['selective'],'-'),
                 ('route_delayed','Selective; route at 78 s',colors['delayed'],'--'),('capacity_bulk','+ Capacity pacing',colors['paced'],':')]
    for role,label,color,style in queue_roles:
        bins=case(role)['figure_series']['source_queue_bins'];assert len(bins)==30,'Expected all30 focus bins including zero bins'
        assert all(row['end_ns']-row['start_ns']==100000000 for row in bins)
        assert bins[0]['start_ns']==74500000000 and bins[-1]['end_ns']==77500000000
        assert all(bins[i]['end_ns']==bins[i+1]['start_ns'] for i in range(29))
        xs=[row['start_ns']/1e9 for row in bins]+[77.5]
        ys=[row['packet_ns']/(row['end_ns']-row['start_ns']) for row in bins]
        assert all(value>=0 for value in ys)
        ax.step(xs,ys+[ys[-1]],where='post',label=label,color=color,linestyle=style,linewidth=1.4)
        queue_data[roles[role]]=bins
    ax.axvline(75,color='#777777',linewidth=.8,linestyle='--')
    ax.set(xlim=(74.5,77.5),ylim=(0,105),xlabel='Simulation time (s)',ylabel='Mean source queue (packets)')
    ax.legend(loc='lower center',bbox_to_anchor=(.5,1.02),frameon=False,ncol=1);ax.grid(axis='y',alpha=.18)
    outputs+=save(fig,a.out/'queue-causality.pdf');plotted['queue-causality']=queue_data

    receipt=dict(schema=1,data=dict(path=str(a.data),bytes=a.data.stat().st_size,sha256=digest(a.data)),
        helper_sha256=digest(Path(__file__)),python=sys.version,matplotlib=matplotlib.__version__,
        output=outputs,plotted_values=plotted,
        contract=['Actual cwnd samples use step interpolation; source queue curves are exact100ms packet-time averages.',
                  'Final fixed-data parity checks are external to figure generation; this helper never runs a simulation.',
                  'PDF clock metadata omitted; numeric values come from supplied evidence, not hardcoded result bars.'])
    (a.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',newline='\n')
    print(json.dumps(dict(out=str(a.out),outputs=len(outputs),data_sha256=digest(a.data))))


if __name__=='__main__':main()
