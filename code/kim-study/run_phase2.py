"""Finite-flow guard exemption and notification-error controls, patch v6."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('selected', nargs='*')
p.add_argument('--workers', type=int, choices=range(1,4), default=3)
p.add_argument('--patch', default=str(root/'ns3-v6.patch'))
p.add_argument('--execution-out', type=Path, default=root/'phase2_execution.json')
a = p.parse_args()
guard = 'study_threshold=20;study_windows=0:500000000'
exempt = guard+';study_short_flow_cutoff_pkts=21'
micro = ['--kind','micro','--rate','100','--queue','2000','--duration','4',
         '--before-ms','50','--after-ms','50','--event-s','2']
cases = []
for nominal in (3,4,8,20,21,22,80):
    base = micro+['--max-bytes',str(nominal*1380),'--loss-seq','1']
    for mode, parameters in (('base',''),('guard20',guard),('exempt21',exempt)):
        cases.append((f'p2-f{nominal}-{mode}-first', base+['--parameters',parameters],
                      {'family':'finite_actual_loss','nominal_mss':nominal,'mode':mode,'loss_position':'first'}))
cases.append(('p2-f20-guard8-first',micro+['--max-bytes','27600','--loss-seq','1',
             '--parameters',guard.replace('threshold=20','threshold=8')],
             {'family':'finite_actual_loss','nominal_mss':20,'mode':'guard8','loss_position':'first'}))
for nominal, position, sequence in ((20,'middle',13801),(20,'last',26221),(80,'last',109021)):
    for mode, parameters in (('base',''),('guard20',guard),('exempt21',exempt)):
        cases.append((f'p2-f{nominal}-{mode}-{position}',micro+['--max-bytes',str(nominal*1380),
                      '--loss-seq',str(sequence),'--parameters',parameters],
                      {'family':'finite_actual_loss','nominal_mss':nominal,'mode':mode,'loss_position':position}))
for mode, parameters in (('base',''),('guard20',guard),('exempt21',exempt)):
    cases.append((f'p2-f20-{mode}-no-loss',micro+['--max-bytes','27600','--parameters',parameters],
                  {'family':'finite_no_loss','nominal_mss':20,'mode':mode,'loss_position':'none'}))
for mode, parameters in (('base',''),('guard20',guard),('exempt21',exempt)):
    cases.append((f'p2-f80-{mode}-no-loss',micro+['--max-bytes','110400','--parameters',parameters],
                  {'family':'finite_no_loss','nominal_mss':80,'mode':mode,'loss_position':'none'}))
for nominal in (20,80):
    step = micro+['--max-bytes',str(nominal*1380),'--after-ms','45','--event-s','0.201']
    for mode, parameters in (('base',''),('guard20',guard),('exempt21',exempt)):
        cases.append((f'p2-step{nominal}-{mode}',step+['--parameters',parameters],
                      {'family':'finite_delay_step','nominal_mss':nominal,'mode':mode,'event_s':0.201}))
leo = ['--rate','10','--queue','100','--duration','200']
leo_guard = 'study_threshold=20;study_windows=26100000000:26500000000|74900000000:75300000000'
for mode, parameters in (('base',''),('guard20',leo_guard),('exempt21',leo_guard+';study_short_flow_cutoff_pkts=21')):
    cases.append((f'p2-leo-{mode}',leo+['--parameters',parameters], {'family':'bulk_leo','mode':mode}))
for offset in (-200,-100,100,200,250,300):
    delta = offset*1000000
    parameters = f'study_threshold=20;study_windows={26100000000+delta}:{26500000000+delta}|{74900000000+delta}:{75300000000+delta};study_short_flow_cutoff_pkts=21'
    name = ('early'+str(-offset)) if offset<0 else ('late'+str(offset))
    cases.append((f'p2-notify-{name}',leo+['--parameters',parameters],
                  {'family':'notification_error','notice_window_offset_ms':offset,'mode':'exempt21'}))
if a.selected:
    wanted = set(a.selected)
    cases = [row for row in cases if row[0] in wanted]
    if {row[0] for row in cases} != wanted: p.error('Unknown selected case')

def execute(row):
    name, args, question = row
    command = [sys.executable,str(root/'run_study.py'),name,'--patch',a.patch]+args
    result = subprocess.run(command,text=True,capture_output=True)
    record = {'case':name,'command':command,'question':question,'exit_code':result.returncode,
              'stdout':result.stdout,'stderr':result.stderr}
    print(json.dumps(record),flush=True)
    return record

start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
    records = list(pool.map(execute,cases))
a.execution_out.write_text(json.dumps({'cases':records,'elapsed_s':round(time.monotonic()-start,3)},indent=2)+'\n')
raise SystemExit(any(r['exit_code'] for r in records))
