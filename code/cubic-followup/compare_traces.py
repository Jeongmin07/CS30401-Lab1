"""Export matched delivery timelines and source trace excerpts (standard library)."""
import argparse
import bisect
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def read_case(root, name):
    run = root / name
    manifest = json.loads((run / "case.json").read_text())
    if manifest["status"] != "complete" or manifest["exit_code"] != 0:
        raise ValueError(f"Incomplete case: {name}")
    logs = run / "logs_ns3"
    app_paths = list(logs.glob("study_app_rx_*.csv"))
    if len(app_paths) != 1:
        raise ValueError("Expected one receiver application trace")
    app_times, cumulative = [], [0]
    with app_paths[0].open() as f:
        for r in csv.DictReader(f):
            if r["flow_id"] != "0":
                raise ValueError("Expected one flow")
            app_times.append(int(r["time_ns"]))
            cumulative.append(cumulative[-1] + int(r["payload_bytes"]))
    if app_times != sorted(app_times):
        raise ValueError("Unsorted application trace")
    with (logs / "study_drops.csv").open() as f:
        drops = list(csv.DictReader(f))
    with (logs / "tcp_flow_0_study_events.csv").open() as f:
        events = list(csv.DictReader(f))
    with (logs / "tcp_flow_0_study_packets.csv").open() as f:
        retx = [r for r in csv.DictReader(f) if r["event"] == "RETX"]
    with (logs / "tcp_flow_0_cwnd.csv").open() as f:
        cwnd = [(int(r[1]), int(r[2])) for r in csv.reader(f)]
    sources = [app_paths[0], logs / "study_drops.csv", logs / "tcp_flow_0_study_events.csv",
               logs / "tcp_flow_0_study_packets.csv", logs / "tcp_flow_0_cwnd.csv",
               logs / "tcp_flow_0_rtt.csv"]
    return dict(manifest=manifest, times=app_times, cumulative=cumulative,
                drops=drops, events=events, retx=retx, cwnd=cwnd,
                sources=[dict(file=p.name, bytes=p.stat().st_size, sha256=digest(p)) for p in sources])


def delivered(c, t):
    # [0,t): bins and checkpoints consistently exclude events at the right edge.
    return c["cumulative"][bisect.bisect_left(c["times"], round(t * 1e9))]


def counts(c, start, end):
    lo, hi = round(start * 1e9), round(end * 1e9)
    d = [r for r in c["drops"] if lo <= int(r["time_ns"]) < hi]
    return dict(drop_rows=len(d), distinct_drop_tx=len({(r["flow_id"], r["tx_id"]) for r in d}),
                retransmissions=sum(lo <= int(r["time_ns"]) < hi for r in c["retx"]),
                recovery_entries=sum(r["event"] == "CONG" and r["new_value"] == "3"
                                     and lo <= int(r["time_ns"]) < hi for r in c["events"]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
    p.add_argument("--baseline", default="q75-base")
    p.add_argument("--protected", default="q75-guard-first")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("Refusing to overwrite analysis directory")
    base, guard = [read_case(a.runs_root, n) for n in (a.baseline, a.protected)]
    bp, gp = base["manifest"]["parameters"], guard["manifest"]["parameters"]
    for k in bp:
        if k not in ("name", "parameters") and bp[k] != gp[k]:
            raise ValueError(f"Unmatched parameter {k}")
    for k in ("patch_sha256", "binary_sha256"):
        if base["manifest"][k] != guard["manifest"][k]:
            raise ValueError(f"Unmatched {k}")
    duration = bp["duration"]
    if duration != 200:
        raise ValueError("The fixed audit windows require the recorded 200-second case")
    a.out.mkdir(parents=True)
    timeline = []
    for start in range(duration):
        end = start + 1
        b = delivered(base, end) - delivered(base, start)
        g = delivered(guard, end) - delivered(guard, start)
        row = dict(start_s=start, end_s=end, baseline_bytes=b, protected_bytes=g,
                   delta_bytes=g-b, cumulative_delta_bytes=delivered(guard,end)-delivered(base,end))
        for label, c in (("baseline", base), ("protected", guard)):
            row.update({f"{label}_{k}": v for k, v in counts(c, start, end).items()})
        timeline.append(row)
    csv_write(a.out / "delivery_timeline.csv", timeline)
    bounds = [0, 25.7, 28.2, 120, 130, 160, 170, 200]
    windows = []
    for start, end in zip(bounds, bounds[1:]):
        row = dict(start_s=start, end_s=end)
        for label, c in (("baseline", base), ("protected", guard)):
            row[f"{label}_bytes"] = delivered(c,end)-delivered(c,start)
            row.update({f"{label}_{k}": v for k,v in counts(c,start,end).items()})
        row["delta_bytes"] = row["protected_bytes"] - row["baseline_bytes"]
        windows.append(row)
    csv_write(a.out / "delivery_windows.csv", windows)
    csv_write(a.out / "congestion_events.csv", [dict(case=n, **r) for n,c in ((a.baseline,base),(a.protected,guard)) for r in c["events"]])
    csv_write(a.out / "drop_events.csv", [dict(case=n, **r) for n,c in ((a.baseline,base),(a.protected,guard)) for r in c["drops"]])
    checkpoints=[]
    for t in (120, 121.6, 121.9, 125, 130, 160, 170, 200):
        for name, case in ((a.baseline,base),(a.protected,guard)):
            times=[r[0] for r in case["cwnd"]]
            i=bisect.bisect_right(times,round(t*1e9))-1
            if i<0:
                raise ValueError("No congestion-window observation before checkpoint")
            at, value=case["cwnd"][i]
            checkpoints.append(dict(case=name,checkpoint_s=t,last_change_ns=at,cwnd_bytes=value))
    csv_write(a.out / "cwnd_checkpoints.csv", checkpoints)
    (a.out / "provenance.json").write_text(json.dumps(dict(
        baseline=a.baseline, protected=a.protected, interval="[start,end)",
        metric="Unique ordered receiver application delivery; summed payload_bytes",
        final_delta_bytes=delivered(guard,duration)-delivered(base,duration),
        sources={a.baseline:base["sources"],a.protected:guard["sources"]},
        patch_sha256=base["manifest"]["patch_sha256"], binary_sha256=base["manifest"]["binary_sha256"]), indent=2)+"\n")
    print(json.dumps(windows, indent=2))


if __name__ == "__main__":
    main()
