import concurrent.futures
import json
from pathlib import Path
import subprocess

matrix = json.loads(Path('/work/matrix_execution.json').read_text())
def analyze(case):
    name = case['case']
    run = Path('/tmp/cs30401-study')/name
    command = ['python3','-B','/work/analyze_study.py',str(run), '--include-bins',
               '--output',str(run/'study_analysis.json')]
    command += ['--events','10'] if name.startswith('micro-') else ['--path-truth','/work/path_truth_200s.csv']
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    data = json.loads((run/'study_analysis.json').read_text())
    flow = data['flows']['0']
    print(json.dumps({'case':name,'goodput_mbps':flow['receiver_application_goodput_mbps'],
                      'drop_count':flow['distinct_tagged_transmissions_dropped'],
                      'retx_count':flow['counts'].get('official_retransmission_rows',0),
                      'gap_classifications':flow['gap_classifications']}),flush=True)
    return name
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(analyze,matrix['cases']))
