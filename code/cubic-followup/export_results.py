"""Analyze declared cases and export compact results, exact settings, and raw hashes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from run_controls import cases


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study-code",type=Path,required=True)
    p.add_argument("--runs-root",type=Path,default=Path("/tmp/cs30401-study"))
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--reuse-analysis",action="store_true",help="Use already generated followup_analysis.json files")
    a=p.parse_args()
    if a.out.exists():
        raise ValueError("Refusing to overwrite evidence directory")
    names=["q75-base","q75-guard-first"]+[n for n,_ in cases("all")]
    def analyze(name):
        run=a.runs_root/name
        m=json.loads((run/"case.json").read_text())
        if m["status"]!="complete" or m["exit_code"]!=0:
            raise ValueError(f"Incomplete case {name}")
        dest=run/"followup_analysis.json"
        if dest.exists():
            if a.reuse_analysis:
                return name
            raise ValueError(f"Existing follow-up analysis {dest}; use --reuse-analysis to preserve it")
        cmd=[sys.executable,str(a.study_code/"analyze_study.py"),str(run),"--duration-s",str(m["parameters"]["duration"]),
             "--include-bins","--max-cases","1000","--output",str(dest)]
        if m["parameters"]["kind"]=="leo":
            cmd.extend(["--path-truth",str(a.study_code/"path_truth_200s.csv")])
        else:
            cmd.extend(["--events",str(m["parameters"]["event_s"])])
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
        print("analyzed",name,flush=True)
        return name
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(analyze,names))
    a.out.mkdir(parents=True)
    rows=[]; hashes={}
    for name in names:
        run=a.runs_root/name
        m=json.loads((run/"case.json").read_text())
        analysis_path=run/"followup_analysis.json"
        z=json.loads(analysis_path.read_text()); f=z["flows"]["0"]
        c=f["counts"]; opts=m["parameters"]
        delivered=c["application_delivered_bytes"]
        finite=opts["max_bytes"]!=100000000000
        if finite and delivered!=opts["max_bytes"]:
            raise ValueError(f"Finite flow did not finish {name}: {delivered}")
        row=dict(case=name,kind=opts["kind"],rate_mbps=opts["rate"],queue_packets=opts["queue"],
                 flow_start_s=opts["flow_start_s"],duration_s=opts["duration"],max_bytes=opts["max_bytes"],
                 parameters=opts["parameters"],receiver_bytes=delivered,goodput_mbps=f["receiver_application_goodput_mbps"],
                 completion_s=f["last_receiver_application_delivery_time_s"] if finite else "",
                 retransmissions=c.get("official_retransmission_rows",0),recovery_entries=c.get("recovery_state_entries",0),
                 loss_entries=c.get("loss_state_entries",0),drop_rows=c.get("drop_trace_rows",0),
                 distinct_drop_tx=f["distinct_tagged_transmissions_dropped"],wall_time_s=m["wall_time_s"],
                 patch_sha256=m["patch_sha256"],binary_sha256=m["binary_sha256"],analysis_sha256=sha(analysis_path))
        for t in (26.2,121.6):
            events=[e for e in z["path_event_windows"] if abs(e["time_s"]-t)<1e-6]
            ef=events[0]["flows"].get("0",{}) if events else {}
            for key in ("application_delivered_bytes","official_retransmission_rows","recovery_state_entries"):
                row[f"event_{t:g}_{key}"]=ef.get(key,0) if events else ""
        rows.append(row)
        sources=[Path(i["path"]) for i in z["inputs"]]
        sources.append(run/"logs_ns3"/"study_drop_coverage.csv")
        sources += [run/"logs_ns3"/f"tcp_flow_0_{suffix}.csv" for suffix in ("cwnd","rtt","progress")]
        hashes[name]=[dict(file=s.name,bytes=s.stat().st_size,sha256=sha(s)) for s in sources]
        target=a.out/"cases"/name;target.mkdir(parents=True)
        for file in ("case.json","config_ns3.properties","schedule.csv"):
            if (run/file).exists():shutil.copyfile(run/file,target/file)
        compact=dict(counts=c,goodput_mbps=f["receiver_application_goodput_mbps"],
                     completion_s=row["completion_s"],gap_classifications=f["gap_classifications"],
                     protection_intervals=f["protection_intervals"],drop_coverage=z["drop_coverage"],
                     analysis_parameters=z["analysis_parameters"],full_analysis_sha256=row["analysis_sha256"],
                     full_analysis_omitted="Receiver time bins, full packet examples, and detailed recovery periods remain in Docker.")
        (target/"summary.json").write_text(json.dumps(compact,indent=2)+"\n")
        if name in ("q75-base","q75-guard-first"):
            gaps=[g for g in f["gap_case_samples"] if 121<=g["start_ns"]/1e9<122]
            (target/"event121_gaps.json").write_text(json.dumps(gaps,indent=2)+"\n")
    with (a.out/"results.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    (a.out/"raw_hashes.json").write_text(json.dumps(hashes,indent=2)+"\n")
    print(a.out,flush=True)


if __name__=="__main__":
    main()
