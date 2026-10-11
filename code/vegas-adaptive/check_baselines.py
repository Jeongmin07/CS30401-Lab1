import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description='Compare measurement CSVs to pinned PR14 receipts; ignore wall-clock timing')
p.add_argument('--reference-root',type=Path,default=Path(__file__).parent/'evidence/pr14-baselines')
p.add_argument('--root',type=Path,default=Path('/tmp/cs30401-vegas'))
p.add_argument('--prefix',default='a1')
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists(), 'Refuse existing compatibility output'
out=[]
for oldcase in ('v1-leo-base','v1-fixed-comp-base','v1-fixed-base','v1-step-base'):
    original=json.loads((a.reference_root/(oldcase+'.json')).read_text(encoding='utf-8-sig'))
    newcase=oldcase.replace('v1-',a.prefix+'-')
    oldparams=original['original_manifest']['parameters']
    newparams=json.loads((a.root/newcase/'case.json').read_text())['parameters']
    omit={'name','root','adaptive'}
    assert {k:v for k,v in oldparams.items() if k not in omit}=={k:v for k,v in newparams.items() if k not in omit}
    checks=[]
    for r in original['all_original_regular_files']:
        rel=r['relative_path']
        if not rel.startswith('logs_ns3/') or not rel.endswith('.csv') or rel.endswith('timing_results.csv'): continue
        p=a.root/newcase/rel
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        checks.append({'file':rel,'reference_sha256':r['sha256'],'new_sha256':h.hexdigest(),
                       'reference_bytes':r['bytes'],'new_bytes':p.stat().st_size,
                       'match':h.hexdigest()==r['sha256'] and p.stat().st_size==r['bytes']})
    assert checks and all(c['match'] for c in checks),checks
    out.append({'reference_case':oldcase,'new_case':newcase,'checks':checks})
a.out.write_text(json.dumps({'cases':out,'status':'pass','parameters_match':True},indent=2)+'\n')
print(json.dumps({'status':'pass','measurement_csv_count':sum(len(c['checks']) for c in out)}))
