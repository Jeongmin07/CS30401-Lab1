"""Small posthoc evidence export; immutable raw runs remain outside Git."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def mapping(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write(path,value):
    if path.exists():raise ValueError('Output exists: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',newline='\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('/tmp/queue-backpressure'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();data=json.loads(a.analysis.read_text())
    assert data['matched_inputs']['all_pass']
    table=[];case_paths={}
    for name,case in data['cases'].items():
        run=a.root/name;manifest=run/'manifest.json';m=json.loads(manifest.read_text())
        assert m['status']=='success' and m['exit_code']==0 and m['runtime_unchanged'] and m['source_unchanged']
        assert sha(manifest)==case['source']['manifest_sha256']
        for window,metrics in case['metrics'].items():
            row=dict(case=name,window=window,**metrics)
            for key,value in case['served_source_residence'][window].items():
                row['served_wait_'+key.replace('_ns','_ms')]=value/1000000 if key.endswith('_ns') and value is not None else value
            table.append(row)
        compact=dict(case=name,source_checkpoint=m['source_checkpoint'],launch_commit=m['launch_commit'],repo_dirty=m['repo_dirty'],
            command=m['command'],cwd=m['cwd'],environment=m['environment'],status=m['status'],exit_code=m['exit_code'],wall_seconds=m['wall_seconds'],
            source_unchanged=m['source_unchanged'],runtime_unchanged=m['runtime_unchanged'],
            source_files=m['source_files'],dependencies=m['dependencies'],image_ref=m['image_ref'],ns3_head=m['ns3_head'],
            patch_sha256=m['patch_sha256'],installed_diff_sha256=m['installed_diff_sha256'],runtime_files=m['runtime_files'],build_ready_sha256=m['build_ready_sha256'],
            input_files=m['input_files'],static_files=len(m['state_static_sha256']),dynamic_files=len(m['dynamic_input_sha256']),
            state_static_mapping_sha256=mapping(m['state_static_sha256']),dynamic_mapping_sha256=mapping(m['dynamic_input_sha256']),
            original_manifest_sha256=sha(manifest),original_output_files=m['output_files'],
            source_phase='Original complete manifest unchanged; this is a compact posthoc projection.',
            queue_mode=m['queue_mode'],physical_drop_first_original_seq1=m['physical_drop_first_original_seq1'],native_summary=case['native_summary'],qa=case['qa'])
        path=a.out/'cases'/(name+'.json');write(path,compact);case_paths[name]=dict(path=str(path),sha256=sha(path))
    path=a.out/'results.csv'
    if path.exists():raise ValueError('Output exists: '+str(path))
    fields=list(dict.fromkeys(key for row in table for key in row))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(table)
    write(a.out/'export.json',dict(schema=1,helper_sha256=sha(Path(__file__)),analysis_sha256=sha(a.analysis),
        actual_analysis_helper_sha256=data['helper_sha256'],launch_analysis_helper_sha256=data['matched_inputs']['launch_analyzer_sha256'],
        analysis_phase=data['posthoc_analysis_phase'],matched_inputs=data['matched_inputs'],
        cases=case_paths,results=dict(path=str(path),sha256=sha(path),rows=len(table)),
        raw_scope='All3 complete original run files preserved in the separate raw archive; no raw CSV is copied into this small export.',
        limitations=['Served residence windows use serialization-start event time; dropped and pending ages are separate in analysis.json.',
                    'Unique all-layer losses are tagged payload-bearing transmissions; unmapped ACK/control notifications are separate.',
                    'No Stage2 receiver-drop control or result-dependent parameter tuning was run.']))
    print(json.dumps(dict(out=str(a.out),rows=len(table),results_sha256=sha(path))))
