"""Read frozen completed raw runs to prepare report figures before fresh replay."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REPO=Path(__file__).resolve().parents[3]
PROBE=r'''
import csv,hashlib,json,pathlib,sys
run=pathlib.Path(sys.argv[1]);kind=sys.argv[2];mp=run/'manifest.json';m=json.loads(mp.read_text())
assert m['status']=='success' and m['exit_code']==0 and m['runtime_unchanged']
assert m.get('source_unchanged',True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()
sources=[]
def file(name):
 p=run/'logs_ns3'/name;k='logs_ns3/'+name;r=m['output_files'][k]
 assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],k
 sources.append(dict(path=str(p),bytes=p.stat().st_size,sha256=r['sha256']))
 return p
out=dict(manifest=dict(path=str(mp),bytes=mp.stat().st_size,sha256=sha(mp)),
 provenance=dict(patch_sha256=m['patch_sha256'],runtime_mapping_sha256=hashlib.sha256(json.dumps(m['runtime_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
 launch_commit=m.get('launch_commit',m.get('repo_commit')),runtime_unchanged=m['runtime_unchanged'],source_unchanged_recorded=m.get('source_unchanged')))
if kind=='cwnd':
 series=[];held=None;end=26600000000
 for row in csv.reader(file('tcp_flow_0_cwnd.csv').open()):
  assert len(row)==3 and row[0]=='0'
  t,w=int(row[1]),int(row[2])
  if t<25900000000:held=[t,w]
  elif t<end:series.append([t,w])
 assert held is not None
 series=[held]+series;series.append([end,series[-1][1]])
 out['cwnd']=series;out['held_endpoint_ns']=end
elif kind=='occupancy':
 lo,hi,step=74500000000,77500000000,100000000;areas={t:0 for t in range(lo,hi,step)}
 records=[r for r in csv.DictReader(file('queue_occupancy.csv').open()) if (r['node_id'],r['device_id'])==('1584','1')]
 assert records and int(records[0]['time_ns'])==lo and records[0]['event']=='FOCUS_START_HELD'
 last=lo;held=int(records[0]['new_packets'])
 def integrate(a,b,value):
  while a<b:
   key=a//step*step;stop=min(b,key+step);areas[key]+=value*(stop-a);a=stop
 for row in records[1:]:
  t=int(row['time_ns']);assert last<=t<=hi
  integrate(last,t,held)
  assert int(row['old_packets'])==held
  held=int(row['new_packets']);last=t
 integrate(last,hi,held)
 out['source_queue_bins']=[dict(start_ns=t,end_ns=t+step,packet_ns=v) for t,v in areas.items()]
elif kind=='area':
 lo,hi,step=74500000000,77500000000,100000000;areas={t:0 for t in range(lo,hi,step)}
 for row in csv.DictReader(file('queue_area_bins.csv').open()):
  if (row['node_id'],row['device_id'])!=('1584','1'):continue
  t=int(row['bin_start_ns'])
  if lo<=t<hi:
   assert int(row['bin_end_ns'])==t+step;areas[t]+=int(row['q_packet_ns'])
 out['source_queue_bins']=[dict(start_ns=t,end_ns=t+step,packet_ns=v) for t,v in areas.items()]
else:raise ValueError(kind)
out['sources']=sources;print(json.dumps(out))
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(container,run,kind):
    value=json.loads(subprocess.check_output(['docker','exec',container,'python3','-B','-c',PROBE,run,kind],text=True))
    value['container']=container;return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Output exists')
    cases={};inputs=[]
    def summary(name,folder):
        path=REPO/folder/name/'summary.json';value=json.loads(path.read_text())
        inputs.append(dict(path=str(path.relative_to(REPO)),bytes=path.stat().st_size,sha256=sha(path)))
        windows={}
        for item in value.get('path_event_windows',[]):
            label='first' if item['window_start_s']==25.7 and item['window_end_s']==28.2 else 'legacy' if item['window_start_s']==74.5 and item['window_end_s']==77.0 else None
            if label:
                flow=item['flows']['0'];counts=flow.get('counts',flow)
                windows[label]=dict(app_bytes=counts.get('application_delivered_bytes',0),app_goodput_mbps=flow['receiver_application_goodput_mbps'],
                    retx_packets=counts.get('official_retransmission_rows',0),recovery_entries=counts.get('recovery_state_entries',0))
        cases[name]=dict(metrics=value['metrics'],windows=windows,tail_admissions=value['tail_policy']['count'],
            selective_episodes=value['selective_policy']['episodes'],actual_drop=value.get('injected_actual_drop') or value.get('first_sequence_actual_loss'),
            native_pacing=value.get('native_pacing'),figure_series={},provenance=dict(summary_sha256=sha(path)))
    core='docs/experiments/assets/20261013-orbit-tail/final/cases'
    pace='docs/experiments/assets/20261013-queue-pacing/final/cases'
    for name in ['leo10-base','leo10-selective','leo10-tail','micro-base','micro-selective','micro-tail',
                 'micro21-selective','micro21-tail','leo10-drop-base','leo10-drop-tail']:summary(name,core)
    for name in ['capacity','native','micro-selected','loss-current','loss-selected']:summary(name,pace)
    roles=dict(stock_bulk='leo10-base',selective_bulk='leo10-selective',tail_bulk='leo10-tail',capacity_bulk='capacity',route_delayed='selective-route75-delayed78',
        stock_finite='micro-base',selective_finite='micro-selective',tail_finite='micro-tail',capacity_finite='micro-selected')
    receipts={}
    for name in ['leo10-base','leo10-tail']:
        rec=fetch('lab1-orbit-tail-20261013','/tmp/orbit-tail/'+name,'cwnd');receipts[name+'/cwnd']=rec
        cases[name]['figure_series']['cwnd']=rec['cwnd']
    for name,raw in [('leo10-base','base-natural'),('leo10-tail','selective-natural')]:
        rec=fetch('lab1-orbit-queue-20261013','/tmp/orbit-queue/'+raw,'occupancy');receipts[name+'/queue']=rec
        cases[name]['figure_series']['source_queue_bins']=rec['source_queue_bins']
    cf='selective-route75-delayed78'
    rec=fetch('lab1-orbit-queue-20261013','/tmp/orbit-queue-cf/'+cf,'occupancy');receipts[cf+'/queue']=rec
    cfpath=REPO/'docs/experiments/assets/20261013-orbit-queue/counterfactual.json';cfdata=json.loads(cfpath.read_text())['counterfactual'];whole=cfdata['measurements']['whole']
    inputs.append(dict(path=str(cfpath.relative_to(REPO)),bytes=cfpath.stat().st_size,sha256=sha(cfpath)))
    cases[cf]=dict(metrics=dict(receiver_bytes=whole['app_bytes'],receiver_goodput_mbps=whole['app_goodput_mbps'],duration_s=(whole['end_ns']-whole['start_ns'])/1e9,
        fct_s=None,retransmissions=whole['retx_packets'],recovery_entries=whole['recovery_entries'],ca_loss_entries=whole['loss_state_entries'],distinct_tagged_drops=whole['tagged_drop_count']),
        windows=cfdata['measurements'],figure_series=dict(source_queue_bins=rec['source_queue_bins']),provenance=rec['provenance'])
    rec=fetch('lab1-queue-pacing-20261013','/tmp/queue-pacing/capacity','area');receipts['capacity/queue']=rec
    cases['capacity']['figure_series']['source_queue_bins']=rec['source_queue_bins']
    bppath=REPO/'docs/experiments/assets/20261013-queue-backpressure/analysis.json';bp=json.loads(bppath.read_text())
    inputs.append(dict(path=str(bppath.relative_to(REPO)),bytes=bppath.stat().st_size,sha256=sha(bppath)))
    for name,value in bp['cases'].items():
        whole=value['metrics']['whole']
        cases[name]=dict(metrics=dict(receiver_bytes=whole['app_bytes'],receiver_goodput_mbps=whole['app_goodput_mbps'],
            duration_s=(whole['end_ns']-whole['start_ns'])/1e9,fct_s=None,retransmissions=whole['retx_packets'],recovery_entries=whole['recovery_entries'],
            ca_loss_entries=whole['loss_state_entries'],distinct_tagged_drops=whole['unique_all_layer_tx_losses']),
            windows=value['metrics'],tail_admissions=0,queue=dict(source=value['metrics'],source_residence=value['served_source_residence'],native_summary=value['native_summary']),provenance=value['source'])
    record=dict(schema=1,phase='Preflight from frozen historical raw; not fresh-package replay.',report_roles=roles,cases=cases,
        helper_sha256=sha(Path(__file__)),summary_inputs=inputs,raw_extraction_receipts=receipts,
        interpolation='Actual held cwnd state plus endpoint hold; queue state integrated exactly into all30 focus100ms bins including zero bins.',
        fresh_parity='Final package must separately compare normalized values/series with fresh replay; source paths/hashes remain phase-specific.')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(record,indent=2)+'\n',newline='\n')
    print(json.dumps(dict(out=str(a.out),sha256=sha(a.out),cases=len(cases),source_reads=len(receipts))))


if __name__=='__main__':main()
