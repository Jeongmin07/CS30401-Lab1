"""Generate sensitivity figure from verified compact results; existing uv lock."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
rows=list(csv.DictReader((a.evidence/'results.csv').open()))
r={x['case']:x for x in rows if x['window']==('common' if 'fixed-comp' in x['case'] else 'whole')}
a.out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(1,3,figsize=(12.6,3.8))
rounds=[10,20,40]
for fam,label,color in [('leo','100 Mbps links','#176a97'),('rate50','50 Mbps links','#d37a22')]:
    values=[float(r[f's1-{fam}-r{x}']['vegas_mbps']) for x in rounds]
    ax[0].plot(range(3),values,'o-',label=label,color=color)
    for i,v in enumerate(values): ax[0].annotate(f'{v:.2f}',(i,v),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
ax[0].axhline(41.5113384,ls=':',color='#176a97',alpha=.6)
base50=float(r['s1-rate50-base']['vegas_mbps'])
ax[0].axhline(base50,ls=':',color='#d37a22',alpha=.6)
ax[0].set(xticks=range(3),xticklabels=rounds,xlabel='Renewal history (valid CA cycles)',ylabel='Receiver app goodput (Mbps)',title='LEO solo, full 200 seconds',ylim=(0,90))
ax[0].legend(loc='upper center',ncol=2,fontsize=9)
ax[0].text(.02,.03,'Dotted: original Vegas at each rate',transform=ax[0].transAxes,fontsize=8)
v=[float(r[f's1-fixed-comp-r{x}']['vegas_mbps']) for x in rounds]
c=[float(r[f's1-fixed-comp-r{x}']['cubic_mbps']) for x in rounds]
ax[1].bar(range(3),v,color='#176a97',label='Vegas')
ax[1].bar(range(3),c,bottom=v,color='#aaa',label='CUBIC')
for i in range(3):
    ax[1].text(i,v[i]/2,f'{v[i]:.1f}',ha='center',color='white')
    ax[1].text(i,v[i]+c[i]/2,f'{c[i]:.1f}',ha='center')
ax[1].set(xticks=range(3),xticklabels=rounds,xlabel='Renewal history (valid CA cycles)',ylabel='Receiver app goodput (Mbps)',title='Fixed path + CUBIC, 80-200 s',ylim=(0,110))
ax[1].legend(ncol=2,fontsize=9,loc='upper center')
q=[float(r[f's1-fixed-comp-r{x}']['queue_mean_ms']) for x in rounds]
ax[2].bar(range(3),q,color=['#81b5ce','#176a97','#81b5ce'])
for i,x in enumerate(rounds):
    j=float(r[f's1-fixed-comp-r{x}']['jain'])
    ax[2].text(i,q[i]+.08,f'{q[i]:.2f}\nJain {j:.3f}',ha='center',fontsize=9)
ax[2].set(xticks=range(3),xticklabels=rounds,xlabel='Renewal history (valid CA cycles)',ylabel='Mean forward queue wait (ms)',title='Competition cost, 80-200 s',ylim=(0,max(q)+1.4))
fig.tight_layout()
for ext in ('png','pdf'): fig.savefig(a.out/f'sensitivity.{ext}',dpi=180,bbox_inches='tight')
(a.out/'sources.json').write_text(json.dumps({'results_sha256':hashlib.sha256((a.evidence/'results.csv').read_bytes()).hexdigest(),'original_100mbps_baseline':41.5113384,'original_100mbps_source':'../evidence/results.csv a1-leo-base whole; verified against PR14'},indent=2)+'\n')
