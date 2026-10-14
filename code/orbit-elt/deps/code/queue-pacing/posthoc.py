"""After the fixed eight runs: whole served visits and original-delivery witnesses."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def receipt(p):
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h)


def rows(p):
    with p.open(newline='') as f:yield from csv.DictReader(f)


def whole(summary):
    q=summary['queue'];source=[r for r in q['queue_conservation'] if (r['node_id'],r['device_id'])==(1584,1)]
    count=sum(r['sojourn_samples'] for r in source);total=sum(r['sojourn_sum_ns'] for r in source)
    area=next(d for d in q['exact_state_area']['devices'] if (d['node_id'],d['device_id'])==(1584,1))['windows']['whole']
    return dict(source_served_visits=count,source_served_sojourn_sum_ns=total,
        source_mean_served_wait_ns=total/count if count else None,source_queue_area=area,
        all_device_queue_area=q['exact_state_area']['aggregate']['whole'],
        selective_wait_episodes=summary['selective_policy']['episodes'],
        qualification='Mean wait divides total served-visit sojourn by total served visits; never sum device means. Legacy guard_starts describes threshold setters, not selective K3 waiting.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--export',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    paths=list((a.export/'cases').glob('*/summary.json'));data={p.parent.name:json.loads(p.read_text()) for p in paths}
    assert len(data)==8 and all(json.loads((a.root/n/'manifest.json').read_text())['status']=='success' for n in data)
    logs=a.root/'capacity/logs_ns3';sender=list(rows(logs/'tcp_flow_0_study_packets.csv'))
    retx=[r for r in sender if r['event']=='RETX'];assert len(retx)==2
    seqs={int(r['seq']) for r in retx};originals={}
    for r in sender:
        seq=int(r['seq'])
        if r['event']=='TX' and seq in seqs and seq not in originals:originals[seq]=r
    received={seq:[] for seq in seqs}
    for r in rows(logs/'study_rx_node_1585_port_1024.csv'):
        seq=int(r['seq']);orig=originals.get(seq)
        if orig and all(r[f]==orig[f] for f in ['flow_id','tx_id','tx_time_ns','seq','payload_bytes']):received[seq].append(r)
    times={int(r['time_ns']) for matches in received.values() for r in matches};apps={t:[] for t in times}
    for r in rows(logs/'study_app_rx_node_1585_port_1024.csv'):
        t=int(r['time_ns'])
        if t in apps:apps[t].append(r)
    witness=[]
    for r in retx:
        seq=int(r['seq']);matches=[x for x in received[seq] if int(x['time_ns'])<int(r['time_ns'])]
        assert len(matches)==1
        rx=matches[0];frontier=apps[int(rx['time_ns'])]
        assert rx['expected_seq']==rx['seq'] and len(frontier)==1
        assert int(frontier[0]['connection_total_rx_bytes'])>=seq+int(rx['payload_bytes'])-1
        witness.append(dict(original_tx=originals[seq],original_rx=rx,
            same_time_receiver_app=frontier[0],later_retx=r,
            original_sequence_delivered_before_retransmission=True))
    lower=min(int(r['time_ns']) for r in retx)-10000000;upper=max(int(r['time_ns']) for r in retx)
    ack=[r for r in sender if r['event']=='RX_ACK' and lower<=int(r['time_ns'])<=upper and r['sack_blocks']]
    state=[r for r in rows(logs/'tcp_flow_0_study_events.csv') if lower<=int(r['time_ns'])<=upper and r['event']=='CONG']
    assert ack and any(r['new_value']=='3' for r in state)
    finite={}
    for name in ['micro-current','micro-selected']:
        log=a.root/name/'logs_ns3';tx=[r for r in rows(log/'tcp_flow_0_study_packets.csv') if r['event'] in ['TX','RETX'] and int(r['payload_bytes'] or 0)>0]
        finite[name]=dict(fct_s=data[name]['metrics']['fct_s'],policy=data[name]['selective_policy'],
            tail=data[name]['tail_policy'],native_rate_changes=list(rows(log/'tcp_flow_0_pacing.csv')),
            data_tx_and_retx_rows=tx,raw_sources=[receipt(log/f) for f in
                ['tcp_flow_0_study_packets.csv','tcp_flow_0_pacing.csv','tcp_flow_0_orbit_loss.csv','tcp_flow_0_orbit_loss_tail.csv']])
    drops=[data[n]['first_sequence_actual_loss'] for n in ['loss-current','loss-selected']]
    out=dict(schema=1,phase='Post-simulation explanatory audit; not part of the launch source or parameter selection.',
        tool=receipt(Path(__file__)),inputs=[receipt(p) for p in paths],
        whole_queue={n:whole(s) for n,s in data.items() if s['queue']},
        remaining_two_retransmissions=dict(witnesses=witness,trigger_rx_ack_sack_rows=ack,congestion_state_rows=state,
            sources=[receipt(logs/f) for f in ['tcp_flow_0_study_packets.csv','study_rx_node_1585_port_1024.csv','study_app_rx_node_1585_port_1024.csv','tcp_flow_0_study_events.csv']],
            qualification='Direct prior original delivery proves unnecessary retransmission. Reordering is around121.6s; geometric shortening is not established.'),
        finite_chronology=finite,actual_first_loss_pair=dict(selections=[d['selection'] for d in drops],
            observed_selection_identity_equal=drops[0]['selection']==drops[1]['selection'],
            drop_to_first_retx_ns=[d['drop_to_first_retx_ns'] for d in drops],
            qualification='Both runs satisfy the same first-sequence rule and their own physical-drop join. Equality here is observed; shared rules do not imply equality generally.'))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2)+'\n',newline='\n')
    print(json.dumps({'out':str(a.out),'whole_queue':{n:{k:v for k,v in q.items() if k.startswith('source_') and k!='source_queue_area'} for n,q in out['whole_queue'].items()},'unnecessary_retx_witnesses':len(witness),'first_loss_identity_equal':out['actual_first_loss_pair']['observed_selection_identity_equal']}))
