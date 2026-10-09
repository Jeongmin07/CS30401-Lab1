"""Finite hypothesis-driven matrix; no teammate outputs are inputs."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import time

guard20 = 'study_threshold=20;study_windows=26100000000:26500000000|74900000000:75300000000'
guard64 = guard20.replace('threshold=20', 'threshold=64')
base = ['--rate','10','--queue','100','--duration','200']
high = ['--rate','100','--queue','1000','--duration','85']
micro = ['--kind','micro','--rate','100','--queue','2000','--duration','20']
cases = [
 ('leo10-base', base),
 ('leo10-static20', base+['--parameters','study_threshold=20']),
 ('leo10-guard20', base+['--parameters',guard20]),
 ('leo10-late20', base+['--parameters','study_threshold=20;study_windows=26400000000:26800000000|75200000000:75600000000']),
 ('leo10-guard8', base+['--parameters',guard20.replace('threshold=20','threshold=8')]),
 ('leo10-guard32', base+['--parameters',guard20.replace('threshold=20','threshold=32')]),
 ('leo100-base', high),
 ('leo100-static64', high+['--parameters','study_threshold=64']),
 ('leo100-guard64', high+['--parameters',guard64]),
 ('leo10-smallq-base', ['--rate','10','--queue','50','--duration','200']),
 ('leo10-smallq-guard20', ['--rate','10','--queue','50','--duration','200','--parameters',guard20]),
 ('leo10-vegas', base+['--cc','TcpVegas']),
 ('leo10-bbr', base+['--cc','TcpBbr']),
 ('micro-step-base', micro),
 ('micro-step-static64', micro+['--parameters','study_threshold=64']),
 ('micro-step-guard64', micro+['--parameters','study_threshold=64;study_windows=9990000000:10300000000']),
 ('micro-stable-base', micro+['--after-ms','50']),
 ('micro-loss-base', micro+['--after-ms','50','--loss-s','10.06']),
 ('micro-loss-static64', micro+['--after-ms','50','--loss-s','10.06','--parameters','study_threshold=64']),
 ('micro-loss-guard64', micro+['--after-ms','50','--loss-s','10.06','--parameters','study_threshold=64;study_windows=9990000000:10300000000']),
]
selected = set(sys.argv[1:])
if selected:
    cases = [(name, args) for name, args in cases if name in selected]
    if len(cases) != len(selected): raise SystemExit('Unknown selected case name')

def run_case(case):
    name, args = case
    command = ['python3','/work/run_study.py',name]+args
    result = subprocess.run(command, text=True, capture_output=True)
    print(json.dumps({'case':name,'exit_code':result.returncode,'output':result.stdout[-1000:],
                      'stderr':result.stderr[-1000:]}), flush=True)
    return {'case':name,'command':command,'exit_code':result.returncode}

start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(run_case, cases))
record = {'cases':results,'elapsed_s':round(time.monotonic()-start,3)}
Path('/work/matrix_execution.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(any(row['exit_code'] for row in results))
