"""Run a declared Vegas case inside the official course image; stdlib only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

IMAGE = "sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4"
NS3 = Path("/home/ubuntu/ns-3.48")
REPO = Path("/work")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def record(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name")
    p.add_argument("--kind", choices=("micro", "leo"), default="micro")
    p.add_argument("--renewal", action="store_true")
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--min-rise-ms", type=float, default=1)
    p.add_argument("--duration", type=int, default=200)
    p.add_argument("--rate", type=float, default=100)
    p.add_argument("--queue", type=int, default=100)
    p.add_argument("--before-ms", type=float, default=45)
    p.add_argument("--after-ms", type=float, default=48)
    p.add_argument("--event-s", type=float, default=100)
    p.add_argument("--competitor", action="store_true")
    p.add_argument("--competitor-start", type=float, default=80)
    p.add_argument("--seed", type=int, default=123456789)
    p.add_argument("--initial-ssthresh-pkts", type=int, default=900)
    p.add_argument("--state", default="/home/ubuntu/lab/data/seoul_london/state")
    p.add_argument("--trace", type=int, choices=(0, 1), default=1)
    p.add_argument("--image-digest", required=True, help="Digest freshly checked by host operator")
    p.add_argument("--root", type=Path, default=Path("/tmp/cs30401-vegas"))
    a = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", a.name):
        p.error("Use an alphanumeric run ID with hyphens/underscores")
    if a.image_digest != IMAGE:
        p.error("Use the pinned official image, host-verified before running")
    if a.rounds < 2 or a.min_rise_ms <= 0 or a.duration <= 0 or a.rate <= 0 or a.queue < 1:
        p.error("Invalid policy/network parameters")
    if a.kind == "leo" and (a.competitor or a.seed != 123456789 or a.duration > 200):
        p.error("This LEO runner supports supplied state, one flow, seed123456789, duration<=200")
    if a.kind == "micro" and a.trace != 1:
        p.error("The micro queue diagnostic always records passive observations")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True)
    if dirty:
        raise SystemExit("Commit simulation code before launch; repository has local changes")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if sha(REPO / "code/vegas-study/vegas_micro.cc") != sha(NS3 / "scratch/vegas_micro/vegas_micro.cc"):
        raise SystemExit("Live micro driver differs from committed driver; copy and rebuild first")
    actual_patch = subprocess.check_output(["git", "diff", "--cached", "--binary", "cs30401-base"], cwd=NS3)
    if hashlib.sha256(actual_patch).hexdigest() != sha(REPO / "code/vegas-study/ns3.patch"):
        raise SystemExit("Live staged ns-3 patch differs from declared patch; export and rebuild first")
    subprocess.run(["git", "diff", "--quiet"], cwd=NS3, check=True)
    run = a.root / a.name
    if run.exists():
        raise SystemExit(f"Refusing existing run {run}")
    run.mkdir(parents=True)
    (run / "logs_ns3").mkdir()
    if a.kind == "leo":
        subprocess.run(["bash", "/home/ubuntu/lab/scripts/make_run.sh", str(run), a.state,
                        "TcpVegas", str(a.rate), str(a.queue), str(a.duration), "1584", "1585"], check=True)
        (run / "schedule.csv").write_text("0,1584,1585,100000000000,0,,\n")
        binary = NS3 / "build/scratch/main_satnet/ns3.48-main_satnet"
        command = [str(binary), f"--run_dir={run}"]
    else:
        binary = NS3 / "build/scratch/vegas_micro/ns3.48-vegas_micro"
        command = [str(binary), f"--run_dir={run}", f"--duration={a.duration}",
                   f"--rate={a.rate}", f"--queue_pkts={a.queue}", f"--before_ms={a.before_ms}",
                   f"--after_ms={a.after_ms}", f"--event_s={a.event_s}",
                   f"--competitor={int(a.competitor)}", f"--competitor_start_s={a.competitor_start}",
                   f"--seed={a.seed}", f"--initial_ssthresh_pkts={a.initial_ssthresh_pkts}",
                   f"--renewal={int(a.renewal)}", f"--renewal_rounds={a.rounds}",
                   f"--renewal_min_rise_ms={a.min_rise_ms}"]
    command += [f"--ns3::TcpVegas::RenewalRounds={a.rounds}",
                f"--ns3::TcpVegas::RenewalMinRise={round(a.min_rise_ms * 1e6)}ns"]
    if a.kind == "leo":
        command += [f"--ns3::TcpVegas::RecentMinRenewal={'true' if a.renewal else 'false'}"]
    env = dict(os.environ, CS30401_STUDY_TRACE=str(a.trace),
               CS30401_STUDY_TRACE_DIR=str(run / "logs_ns3"),
               CS30401_VEGAS_TRACE_DIR=str(run / "logs_ns3"))
    files = [Path(__file__), REPO / "code/vegas-study/ns3.patch",
             REPO / "code/vegas-study/vegas_micro.cc", REPO / "code/vegas-study/analyze_vegas.py",
             REPO / "code/kim-study/analyze_study.py", REPO / "code/kim-study/path_truth_200s.csv",
             NS3 / "src/internet/model/tcp-vegas.cc", NS3 / "src/internet/model/tcp-vegas.h",
             NS3 / "src/internet/model/tcp-socket-base.cc", NS3 / "scratch/vegas_micro/vegas_micro.cc"]
    sources = [record(path) for path in files]
    libs = [record(path) for path in sorted((NS3 / "build/lib").glob("libns3.48-*.so"))]
    parameters = {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()}
    parameters["cc"] = "TcpVegas"
    if a.kind == "leo":
        for key in ("before_ms", "after_ms", "event_s", "competitor_start", "initial_ssthresh_pkts"):
            parameters.pop(key)
    manifest = {"schema_version": 1, "case": a.name, "parameters": parameters,
                "source_commit": commit, "source_worktree_dirty": False,
                "official_image_digest": a.image_digest,
                "image_verification": "Host operator inspected Docker identity before launch; supplied to runner",
                "command": command, "trace_environment": {k: env[k] for k in
                    ("CS30401_STUDY_TRACE", "CS30401_STUDY_TRACE_DIR", "CS30401_VEGAS_TRACE_DIR")},
                "sources": sources, "shared_libraries": libs, "binary": record(binary),
                "patch_sha256": sha(REPO / "code/vegas-study/ns3.patch"),
                "binary_sha256": sha(binary), "status": "running", "start_time_unix": time.time(),
                "policy": {"recent_min_renewal": a.renewal, "rounds": a.rounds,
                           "min_rise_ns": round(a.min_rise_ms * 1e6), "alpha": 2, "beta": 4, "gamma": 1,
                           "input": "existing socket SRTT; loss/startup unchanged"},
                "state": a.state if a.kind == "leo" else None}
    for filename in ("config_ns3.properties", "schedule.csv"):
        if (run / filename).exists():
            manifest[filename + "_sha256"] = sha(run / filename)
    write(run / "case.json", manifest)
    start = time.monotonic()
    with (run / "console.log").open("w") as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    manifest.update(status="complete" if result.returncode == 0 else "failed", exit_code=result.returncode,
                    wall_time_s=round(time.monotonic() - start, 3), end_time_unix=time.time())
    if result.returncode == 0 and a.kind == "micro":
        cfg = json.loads((run / "config_driver.json").read_text())
        expected = {"renewal": a.renewal, "renewal_rounds": a.rounds,
                    "renewal_min_rise_ns": round(a.min_rise_ms * 1e6), "seed": a.seed,
                    "competitor": a.competitor, "duration_ns": a.duration * 1000000000,
                    "before_one_way_delay_ns": round(a.before_ms * 1e6),
                    "after_one_way_delay_ns": round(a.after_ms * 1e6),
                    "event_ns": round(a.event_s * 1e9), "queue_pkts_per_direction": a.queue}
        mismatches = {k: {"requested": v, "actual": cfg.get(k)} for k, v in expected.items() if cfg.get(k) != v}
        manifest["actual_driver_settings_checked"] = expected
        if mismatches:
            manifest.update(status="invalid", settings_mismatches=mismatches)
    for filename in ("config_ns3.properties", "schedule.csv", "config_driver.json"):
        if (run / filename).exists():
            manifest[filename + "_sha256"] = sha(run / filename)
    write(run / "case.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("case", "status", "exit_code", "wall_time_s", "source_commit")}))
    if result.returncode:
        print((run / "console.log").read_text()[-4000:])
    raise SystemExit(result.returncode if manifest["status"] != "invalid" else 2)


if __name__ == "__main__":
    main()
