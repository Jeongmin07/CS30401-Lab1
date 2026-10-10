"""Run the declared follow-up controls in the course container; never overwrite runs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time

FIRST = "26100000000:26500000000"
LATER = "121500000000:121900000000"


def protection(k, windows, exempt=False):
    text = f"study_threshold={k};study_windows={windows}"
    return text + (";study_short_flow_cutoff_pkts=21" if exempt else "")


def cases(stage):
    rows = []
    def add(name, **options):
        rows.append((name, options))
    if stage == "originals":
        add("q75-base", queue=75)
        add("q75-guard-first", queue=75, parameters=protection(20,FIRST))
    if stage in ("all", "core"):
        add("fup75-later20", queue=75, parameters=protection(20,LATER))
        add("fup75-first-later20", queue=75, parameters=protection(20,FIRST+"|"+LATER))
        add("fup75-first4", queue=75, parameters=protection(4,FIRST))
        add("fup75-first-later4", queue=75, parameters=protection(4,FIRST+"|"+LATER))
    if stage in ("all", "robustness"):
        for family, common in (("start1",dict(queue=75,flow_start_s=1)),("q50",dict(queue=50))):
            add("fup-"+family+"-base", **common)
            for k in (4,20):
                add(f"fup-{family}-k{k}", **common, parameters=protection(k,FIRST+"|"+LATER))
    if stage in ("all", "micro"):
        for size in (20,22):
            common = dict(kind="micro",rate=100,queue=2000,duration=4,
                          before_ms=50,after_ms=50,max_bytes=size*1380,loss_s=0.15)
            add(f"fup-loss{size}-base", **common)
            add(f"fup-loss{size}-k4", **common,parameters=protection(4,"0:500000000"))
            add(f"fup-loss{size}-k20", **common,parameters=protection(20,"0:500000000"))
            add(f"fup-loss{size}-exempt21", **common,parameters=protection(20,"0:500000000",True))
        common = dict(kind="micro",rate=100,queue=2000,duration=4,
                      before_ms=50,after_ms=45,max_bytes=80*1380,event_s=0.201)
        add("fup-step80-base", **common)
        for k in (4,20):
            add(f"fup-step80-k{k}", **common,parameters=protection(k,"0:500000000"))
    if stage in ("all", "refinement"):
        for k in (8,9):
            add(f"fup75-both-k{k}-exempt21",queue=75,parameters=protection(k,FIRST+"|"+LATER,True))
            common=dict(kind="micro",rate=100,queue=2000,duration=4,before_ms=50)
            add(f"fup-loss22-k{k}-exempt21",**common,after_ms=50,max_bytes=22*1380,loss_s=0.15,
                parameters=protection(k,"0:500000000",True))
            add(f"fup-step80-k{k}-exempt21",**common,after_ms=45,max_bytes=80*1380,event_s=0.201,
                parameters=protection(k,"0:500000000",True))
        add("fup-start1-k8-exempt21",queue=75,flow_start_s=1,parameters=protection(8,FIRST+"|"+LATER,True))
        add("fup-q50-k8-exempt21",queue=50,parameters=protection(8,FIRST+"|"+LATER,True))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study-code",type=Path,required=True)
    p.add_argument("--stage",choices=("all","core","robustness","micro","refinement","originals"),default="all")
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():
        raise ValueError("Refusing to overwrite execution record")
    declared=cases(a.stage)
    for n,_ in declared:
        if (Path("/tmp/cs30401-study")/n).exists():
            raise ValueError(f"Existing run: {n}; use a fresh container")
    started=time.monotonic()
    def execute(item):
        name,opts=item
        cmd=[sys.executable,str(a.study_code/"run_study.py"),name,"--patch",str(a.study_code/"ns3.patch")]
        for key,value in opts.items():
            cmd.extend(["--"+key.replace("_","-"),str(value)])
        result=subprocess.run(cmd,text=True,capture_output=True)
        return dict(case=name,command=cmd,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
    results=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(execute,item) for item in declared]
        for f in as_completed(futures):
            row=f.result();results.append(row)
            print(row["case"],row["exit_code"],flush=True)
    record=dict(stage=a.stage,workers=a.workers,wall_time_s=round(time.monotonic()-started,3),
                cases=sorted(results,key=lambda r:r["case"]))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(record,indent=2)+"\n")
    if any(r["exit_code"] for r in results):
        raise SystemExit("One or more simulations failed; inspect execution record")


if __name__=="__main__":
    main()
