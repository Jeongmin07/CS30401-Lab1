"""Independent per-row rule/input/reset audit, plus baseline/replay hash checks."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

def rows(path):
    with path.open(newline='') as f: yield from csv.DictReader(f)
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def audit(run):
    manifest = json.loads((run/'case.json').read_text())
    enabled = manifest['policy']['adaptive_thresholds']
    artifacts = [run/'case.json',run/'logs_ns3/vegas_state.csv']
    if enabled: artifacts.append(run/'logs_ns3/adaptive_state.csv')
    inputs = [{'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in artifacts]
    states = list(rows(run/'logs_ns3/vegas_state.csv'))
    assert all(r['event'] != 'RENEW' and r['renewal_enabled'] == '0' for r in states)
    last_base = {}
    expected_previous = {}
    cycles = {}
    for r in states:
        instance = r['vegas_instance']
        if r['base_rtt_ns']:
            base = int(r['base_rtt_ns'])
            assert base <= last_base.get(instance, base), 'Upward base RTT change'
            last_base[instance] = base
        if r['event'] in ('ENABLE', 'DISABLE'):
            expected_previous[instance] = None
        elif r['event'].startswith('CYCLE_'):
            valid = r['valid_renewal_cycle'] == '1'
            if not valid:
                expected_previous[instance] = None
            elif enabled:
                key = (r['time_ns'], instance)
                assert key not in cycles
                cycles[key] = (r, expected_previous.get(instance))
                # Store actual estimate from independent primitive fields.
                expected_previous[instance] = (int(r['cwnd_before_bytes'])//1380) * 1e9 / int(r['cycle_min_rtt_ns'])
    path = run/'logs_ns3/adaptive_state.csv'
    if not enabled:
        assert not path.exists()
        return {'case':run.name,'adaptive':False,'vegas_rows':len(states),'upward_base_changes':0,'inputs':inputs}
    assert path.exists()
    counts = {}
    checked = 0
    max_alpha = 0
    for r in rows(path):
        checked += 1
        key = (r['time_ns'],r['vegas_instance'])
        state, history = cycles.pop(key)
        a,b,an,bn = [int(r[k]) for k in ('alpha_before','beta_before','alpha_after','beta_after')]
        af,bf = int(r['alpha_floor']),int(r['beta_floor'])
        mss,wb,wa = [int(r[k]) for k in ('segment_size','cwnd_before_bytes','cwnd_after_bytes')]
        diff = int(r['diff_pkts'])
        minrtt,basertt = int(r['cycle_min_rtt_ns']),int(r['base_rtt_ns'])
        w = wb//mss
        assert mss == 1380 and int(r['cong_state']) == 0
        assert wb >= int(state['ssthresh_before_bytes']) and int(state['rtt_samples']) > 2
        assert wa == int(state['cwnd_after_bytes']) and wb == int(state['cwnd_before_bytes'])
        assert diff == int(state['diff_pkts']) == w-int(w*(basertt/1e9)/(minrtt/1e9))
        rate,prev = float(r['rate_pkts_s']),float(r['previous_rate_pkts_s'])
        assert math.isclose(rate,w*1e9/minrtt,rel_tol=1e-14)
        assert int(r['previous_valid']) == int(history is not None)
        if history is not None: assert math.isclose(prev,history,rel_tol=1e-14)
        delta = 0
        ea,eb = a,b
        rule = 'band-hold'
        if history is None:
            rule = 'seed-ordinary'
            delta = -1 if diff>b else (1 if diff<a else 0)
        elif diff>b:
            rule='above-beta'; delta=-1
            ea,eb=max(af,a-1),max(bf,b-1)
        elif diff<a:
            if a>af and rate<prev:
                rule='below-alpha-rate-fell'; delta=-1; ea,eb=a-1,max(bf,b-1)
            elif a==af or rate>prev:
                rule='below-alpha-grow'; delta=1
            else: rule='below-alpha-equal-hold'
        elif rate>prev:
            rule='band-rate-rose'; delta=1; ea,eb=a+1,b+1
        expected_cwnd = wb if delta==0 else max(2,w+delta)*mss
        assert (an,bn,wa,r['rule']) == (ea,eb,expected_cwnd,rule)
        assert an>=af==2 and bn>=bf==4 and bn-an==2
        max_alpha=max(max_alpha,an)
        counts[rule]=counts.get(rule,0)+1
    assert not cycles, 'Valid CA decisions missing from adaptive trace'
    return {'case':run.name,'adaptive':True,'checked_decisions':checked,'vegas_rows':len(states),'inputs':inputs,
            'rules':counts,'maximum_alpha':max_alpha,'upward_base_changes':0,'invalid_or_missing_decisions':0}

def compare(old,new):
    om,nm=[json.loads((p/'case.json').read_text()) for p in (old,new)]
    for key in ('source_commit','patch_sha256','official_image_digest','binary_sha256','policy'):
        assert om[key]==nm[key], key
    for key in ('sources','shared_libraries'):
        assert [(r['path'],r['sha256'],r['bytes']) for r in om[key]] == [(r['path'],r['sha256'],r['bytes']) for r in nm[key]], key
    assert {k:v for k,v in om['parameters'].items() if k not in ('name','root')} == {k:v for k,v in nm['parameters'].items() if k not in ('name','root')}
    records=[]
    for f in sorted((old/'logs_ns3').glob('*.csv')):
        if f.name == 'timing_results.csv': continue # Wall-clock metadata
        target=new/'logs_ns3'/f.name
        records.append({'file':f.name,'sha256':sha(f),'equal':target.exists() and sha(f)==sha(target)})
    assert records and all(r['equal'] for r in records), records
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',nargs='+',type=Path)
    p.add_argument('--compare',nargs=2,type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    assert not a.out.exists()
    result={'audit':[audit(r) for r in a.runs or []],
            'comparison':compare(*a.compare) if a.compare else None,
            'replay_source_binary_libraries_parameters_match':True if a.compare else None,
            'audit_source_sha256':sha(Path(__file__)),'status':'pass'}
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
