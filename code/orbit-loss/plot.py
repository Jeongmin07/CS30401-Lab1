"""Standalone scientific figures from the seven final compact summaries."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def receipt(path):
    return dict(path=str(path),bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    sources={q.parent.name:q for q in (a.export/'cases').glob('*/summary.json')}
    data={n:json.loads(q.read_text()) for n,q in sources.items()}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors=['#355c7d','#b76537','#27837c']
    labels=['Baseline K3','Bounded K20','Selective K3']
    names=['leo10-base','leo10-bounded20','leo10-selective']
    fig,axes=plt.subplots(1,3,figsize=(13,4.6),layout='constrained')
    plotted=[]
    for ax,title,event in zip(axes,['Whole run [0,200) s','First window [25.7,28.2) s','Later window [74.5,77.0) s'],[None,26.2,75.0]):
        values=[]; counts=[]
        for n in names:
            s=data[n]
            row=s['metrics'] if event is None else next(w['flows']['0'] for w in s['path_event_windows'] if w['time_s']==event)
            values.append(row['receiver_goodput_mbps'] if event is None else row['receiver_application_goodput_mbps'])
            counts.append((row['retransmissions'],row['recovery_entries']) if event is None else
                          (row.get('official_retransmission_rows',0),row.get('recovery_state_entries',0)))
        ax.bar(labels,values,color=colors,width=.65)
        for i,(v,c) in enumerate(zip(values,counts)):
            ax.text(i,v+.12,f'{v:.6f}\nRETX/rec {c[0]}/{c[1]}',ha='center',fontsize=9)
        ax.set(title=title,ylabel='Ordered receiver goodput (Mbit/s)',ylim=(0,11.6))
        ax.tick_params(axis='x',labelrotation=18)
        ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
        plotted.append(dict(title=title,values=values,retx_recovery=counts))
    fig.suptitle('Natural LEO: small whole-run gain, a worse later window',fontsize=13)
    outputs=[]
    for ext in ['png','pdf']:
        path=a.out/('natural-leo.'+ext); fig.savefig(path,dpi=180); outputs.append(receipt(path))
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.7),layout='constrained')
    fct=[data[n]['metrics']['fct_s'] for n in ['micro-base','micro-selective']]
    delays=[data[n]['injected_actual_drop']['first_retransmission_after_drop_ns']/1e6
            for n in ['leo10-drop-base','leo10-drop-selective']]
    labels2=['Baseline K3','Selective K3']
    for ax,values,title,ylabel,limit,fmt in zip(axes,[fct,delays],
        ['Stable false hint + real first loss: 20 MSS','Same original packet lost during the LEO step'],
        ['Completed 27,600-byte transfer FCT (s)','Physical drop to first retransmission (ms)'],
        [(0,.43),(0,68)],['.9f','.6f']):
        ax.bar(labels2,values,color=[colors[0],colors[2]],width=.55)
        for i,v in enumerate(values): ax.text(i,v+limit[1]*.025,format(v,fmt),ha='center',fontsize=10)
        ax.set(title=title,ylabel=ylabel,ylim=limit)
        ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].text(.5,.95,'FCT +39.35%; RETX wait +6.631518 ms',transform=axes[0].transAxes,ha='center',fontsize=9)
    axes[1].text(.5,.95,'Extra interval 5.735961 ms; one matched loss',transform=axes[1].transAxes,ha='center',fontsize=9)
    fig.suptitle('Real-loss costs: bounded wait does not bound finite-flow completion cost',fontsize=12)
    for ext in ['png','pdf']:
        path=a.out/('actual-loss-cost.'+ext); fig.savefig(path,dpi=180); outputs.append(receipt(path))
    plt.close(fig)
    (a.out/'receipt.json').write_text(json.dumps(dict(tool=receipt(Path(__file__)),matplotlib_version=matplotlib.__version__,
        inputs=[receipt(sources[n]) for n in sorted(sources)],natural_panels=plotted,
        finite_fct_s=fct,physical_drop_to_first_retx_ms=delays,outputs=outputs,
        qualification='One deterministic matched case per condition. No confidence intervals; axes start at zero. LEO bulk flows have no FCT.'),indent=2)+'\n')
