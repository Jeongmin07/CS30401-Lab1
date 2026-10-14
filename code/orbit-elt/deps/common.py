"""Portable provenance and the fixed course-package condition map."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
NS3=Path('/home/ubuntu/ns-3.48')
STATE=Path('/home/ubuntu/lab/data/seoul_london/state')
IMAGE='ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
PATCHES={'pace':'ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808',
         'bp':'90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f'}
BASE='99bc6f733274475b7a6e804128651e17ee2a2536'
ROOTS={p:Path('/tmp/lab1-final-'+p) for p in PATCHES}


def module(name,rel):
    spec=importlib.util.spec_from_file_location(name,HERE/rel)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj


tail=module('final_frozen_tail_runner','code/orbit-tail/run.py')
pace=module('final_frozen_pacing_runner','code/queue-pacing/run.py')
CASES={n:dict(profile='pace',category='core',definition=d) for n,d in tail.CASES.items()}
for n in ['native','capacity','micro-selected','loss-current','loss-selected']:
    CASES[n]=dict(profile='pace',category='pacing',definition=pace.definition(n,'capacity'))
CF='selective-route75-delayed78'
CASES[CF]=dict(profile='pace',category='counterfactual',definition=dict(tail.CASES['leo10-selective']))
for n,mode,dm,qm in [('control100','off',100,0),('fifo4-96','fifo',4,96),('codel4-96','codel',4,96)]:
    CASES[n]=dict(profile='bp',category='backpressure',queue_mode=mode,device_max=dm,qdisc_max=qm,
                 definition=dict(kind='leo',mode='selective',rate=10,queue=100,duration=200,tail=True))
ALIASES={'pacing-off':'leo10-tail','safety-micro-original':'micro-base','safety-micro-current':'micro-tail'}
ROLES=dict(stock_bulk='leo10-base',selective_bulk='leo10-selective',tail_bulk='leo10-tail',capacity_bulk='capacity',
    route_delayed=CF,stock_finite='micro-base',selective_finite='micro-selective',tail_finite='micro-tail',capacity_finite='micro-selected')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def receipt(path):return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def git(*args,cwd=NS3):
    return subprocess.check_output(['git','-c',f'safe.directory={cwd}','-c','core.autocrlf=false',*args],cwd=cwd)


def identity():
    try:
        base=['git','-c',f'safe.directory={HERE}']
        call=lambda *args:subprocess.check_output(base+list(args),cwd=HERE,stderr=subprocess.DEVNULL)
        return dict(commit=call('rev-parse','HEAD').decode().strip(),dirty=bool(call('status','--porcelain')))
    except subprocess.CalledProcessError:return dict(commit=None,dirty=None,qualification='Standalone extracted package has no Git checkout.')


def source_files():
    return {str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file()
            and not(set(p.relative_to(HERE).parts)&{'report','.venv','__pycache__'})
            and p.suffix in ['.py','.csv','.json','.patch','.sh','.toml','.lock']}


def runtime():
    return {str(p.relative_to(NS3/'build')):sha(p) for p in [NS3/'build/scratch/main_satnet/ns3.48-main_satnet',
        NS3/'build/scratch/study_micro/ns3.48-study_micro',*sorted((NS3/'build/lib').glob('*.so'))]}


def validate_build(profile,ready):
    for process in ['cc1plus','ninja','cmake','make']:
        if subprocess.run(['pgrep','-x',process],stdout=subprocess.DEVNULL).returncode==0:raise ValueError('Build active: '+process)
    artifact=HERE/'runtimes'/(profile+'.patch');assert sha(artifact)==PATCHES[profile]
    assert git('rev-parse','HEAD').decode().strip()==BASE
    diff=git('diff','--binary','HEAD');assert diff==artifact.read_bytes(),'Installed staged+unstaged source differs'
    data=json.loads(ready.read_text());assert data['build_status']=='success' and data['patch_sha256']==sha(artifact)
    assert data['official_export_byte_equal'] and data['source_files_unchanged'] and runtime()==data['runtime_files']
    return diff,data


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',newline='\n')
