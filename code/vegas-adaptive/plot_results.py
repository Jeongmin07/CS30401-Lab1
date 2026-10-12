"""Figure uses exported app delivery and direct queue measurements, no fitting."""
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path(__file__).parent/'evidence'
ours=list(csv.DictReader((root/'results.csv').open()))
prior=list(csv.DictReader((root/'pr14-results.csv').open()))
def current(family,mode,window='whole',flow='0'):
    return next(r for r in ours if (r['family'],r['mode'],r['window'],r['flow_id'])==(family,mode,window,flow))
def reference(family,window='whole',flow='0'):
    return next(r for r in prior if r['case']==f'v1-{family}-renew' and r['window']==window and r['flow_id']==flow)
colors=['#475569','#2563eb','#d97706']; labels=['Original Vegas','Recent-min renewal (PR14)','Adaptive CA (PR15)']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,3,figsize=(13,4),gridspec_kw={'width_ratios':[1.3,1.1,0.85]})
x=np.arange(3); width=.24
families=['leo','fixed','step']
for i,mode in enumerate(['base','renew','adaptive']):
    vals=[float(reference(f)['application_goodput_mbps']) if mode=='renew' else float(current(f,mode)['goodput_mbps']) for f in families]
    bars=axs[0].bar(x+(i-1)*width,vals,width,color=colors[i],label=labels[i])
    axs[0].bar_label(bars,fmt='%.1f',padding=3,fontsize=8)
axs[0].set_xticks(x,['LEO solo','Fixed solo','RTT-step solo']); axs[0].set_ylabel('App goodput (Mbps), 0–200 s'); axs[0].set_ylim(0,100)
axs[0].set_title('Solo benefit depends on scenario')
fg=[float(current('fixed-comp','base','common')['goodput_mbps']),float(reference('fixed-comp','competition')['application_goodput_mbps']),float(current('fixed-comp','adaptive','common')['goodput_mbps'])]
bg=[float(current('fixed-comp','base','common','1')['goodput_mbps']),float(reference('fixed-comp','competition','1')['application_goodput_mbps']),float(current('fixed-comp','adaptive','common','1')['goodput_mbps'])]
for i,(v,c) in enumerate(zip(fg,bg)):
    axs[1].bar(i,v,color=colors[i]); axs[1].bar(i,c,bottom=v,color=colors[i],alpha=.35,hatch='//')
    axs[1].text(i,v/2,f'{v:.1f}',ha='center',color='white',weight='bold')
    axs[1].text(i,v+c/2,f'{c:.1f}',ha='center')
axs[1].set_xticks(range(3),['Original','Renewal','Adaptive']); axs[1].set_ylim(0,105)
axs[1].set_ylabel('Common 80–200 s app goodput (Mbps)'); axs[1].set_title('Fixed path: solid Vegas, hatched CUBIC')
priorq=json.loads((root/'pr14-fixed-comp-queue.json').read_text())['forward_queue_mean_ms']
q=[float(current('fixed-comp','base','common')['forward_queue_mean_ms']),priorq,float(current('fixed-comp','adaptive','common')['forward_queue_mean_ms'])]
bars=axs[2].bar(range(3),q,color=colors); axs[2].bar_label(bars,fmt='%.2f',padding=3)
axs[2].set_xticks(range(3),['Original','Renewal','Adaptive']); axs[2].set_ylim(0,6)
axs[2].set_ylabel('Forward queue mean wait (ms)'); axs[2].set_title('Fixed competition: queue cost')
fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,-.01))
fig.suptitle('Matched 100 Mbps / queue100 controls: adaptive gain has a sharing cost',fontsize=13)
fig.tight_layout(rect=[0,.07,1,.93])
out=root/'figures'; out.mkdir(exist_ok=True)
fig.savefig(out/'comparison.png',dpi=170,bbox_inches='tight'); fig.savefig(out/'comparison.pdf',bbox_inches='tight')
(out/'sources.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'results.csv',root/'pr14-results.csv',root/'pr14-fixed-comp-queue.json',Path(__file__)]},indent=2)+'\n')
