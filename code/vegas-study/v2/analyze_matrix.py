"""Run two post-hoc analyzers on declared completed runs; never run ns-3.

python analyze_matrix.py --root /tmp/cs30401-vegas --out NEW_DIR --workers 2
Use --plan-only to inspect the plan without creating output files.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

LAUNCH = "82ad34a975d4b15f8a536527f8ea4f0cf6e41624"
SUFFIXES = tuple(condition + "-" + mode for condition in
                 ("fixed", "step", "fixed-comp", "step-comp", "leo")
                 for mode in ("base", "renew"))


def sha(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Input changed while hashing: {path}")
    return {"path": str(path), "bytes": after.st_size, "sha256": digest.hexdigest()}


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def git_identity(repo):
    result = {}
    for name, command in (("git_head", ["git", "rev-parse", "HEAD"]),
                          ("worktree_status", ["git", "status", "--porcelain"])):
        command = command[:1] + ["-c", f"safe.directory={repo}", "-c", "core.autocrlf=true"] + command[1:]
        run = subprocess.run(command, cwd=repo, text=True, capture_output=True)
        result[name] = run.stdout.strip() if run.returncode == 0 else None
    result["qualification"] = "Post-hoc helper checkout at analysis time; launch commit is separately read and validated from each original run. Dirty/untracked helpers are identified by their SHA256, not assumed to belong to git_head."
    return result


def plan_case(name, args, repo):
    run = args.root.resolve() / name
    manifest_path = run / "case.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("case") != name or manifest.get("status") != "complete" or manifest.get("exit_code") != 0:
        raise ValueError(f"Run is not declared complete/exit0: {name}")
    if manifest.get("source_commit") != args.launch_commit:
        raise ValueError(f"Unexpected simulation launch commit for {name}")
    p = manifest["parameters"]
    leo, competitor, renewal = "-leo-" in name, "-comp-" in name, name.endswith("-renew")
    if p.get("kind") != ("leo" if leo else "micro") or bool(p.get("competitor")) != competitor or bool(p.get("renewal")) != renewal or p.get("duration") != 200:
        raise ValueError(f"Run condition/name mismatch: {name}")
    if not leo and (p.get("event_s") != 100 or p.get("before_ms") != 45 or p.get("after_ms") != (45 if "-fixed-" in name else 48)):
        raise ValueError(f"Unexpected micro delay/event condition: {name}")
    if competitor and p.get("competitor_start") != 80:
        raise ValueError(f"Unexpected competitor start: {name}")
    output = args.out.resolve() / name
    study = output / "study-analysis.json"
    first = [sys.executable, str(repo / "code/kim-study/analyze_study.py"), str(run),
             "--include-bins", "--output", str(study)]
    second = [sys.executable, str(repo / "code/vegas-study/v2/analyze_vegas.py"), str(run),
              "--out", str(output / "vegas"), "--study-analysis", str(study)]
    if leo:
        first += ["--path-truth", str(repo / "code/kim-study/path_truth_200s.csv")]
        second += ["--event-s", "121.6", "--event-s", "187.4"]
    else:
        config = json.loads((run / "config_driver.json").read_text())
        if config.get("root_queue_disc") is not False or config.get("duration_ns") != 200_000_000_000:
            raise ValueError(f"Synthetic driver root-qdisc/duration contract not verified: {name}")
        first += ["--events", "100", "--root-qdisc-absence-audited"]
        second += ["--event-s", "100"]
        if competitor:
            second += ["--window", "competition:80:200"]
        if "-fixed-comp-" in name:
            second += ["--window", "first-false-renew:90.194745440:91.958450720"]
    return {"case": name, "run": str(run), "out": str(output),
            "simulation_launch_commit": manifest["source_commit"],
            "original_manifest": sha(manifest_path), "policy": manifest["policy"],
            "commands": [first, second], "status": "planned"}


def analyze_case(case):
    output = Path(case["out"])
    output.mkdir()
    started = time.monotonic()
    case.update(status="running", start_time_unix=time.time(), phases=[])
    try:
        for index, command in enumerate(case["commands"], 1):
            source_before = sha(command[1])
            phase_start = time.monotonic()
            phase_start_unix = time.time()
            process = subprocess.run(command, text=True, capture_output=True)
            console = output / f"phase-{index}.console.log"
            with console.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(process.stdout)
                stream.write(process.stderr)
            phase = {"phase": index, "command": command, "start_time_unix": phase_start_unix,
                     "end_time_unix": time.time(), "wall_time_s": round(time.monotonic() - phase_start, 6),
                     "exit_code": process.returncode, "analysis_source": source_before,
                     "analysis_source_after": sha(command[1]), "console": sha(console)}
            case["phases"].append(phase)
            if source_before["sha256"] != phase["analysis_source_after"]["sha256"]:
                raise ValueError("Analysis source changed during execution")
            if process.returncode != 0:
                raise ValueError(f"Analysis phase{index} exit{process.returncode}; see {console}")
        artifacts = [output / "study-analysis.json", output / "vegas/summary.json", output / "vegas/windows.csv"]
        for path in artifacts[:2]:
            json.loads(path.read_text())
        case.update(status="complete", output_artifacts=[sha(path) for path in artifacts])
    except Exception as error:
        case.update(status="failed", error=str(error))
    case.update(end_time_unix=time.time(), wall_time_s=round(time.monotonic() - started, 6))
    write(output / "analysis-execution.json", case)
    return case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-vegas-v2"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--prefix", default="v2", help="Run prefix, e.g. review-v1 for an immutable replay")
    parser.add_argument("--launch-commit", "--launchcommit", dest="launch_commit", required=True)
    parser.add_argument("--cases", nargs="+", help="Optional subset of the selected prefix's declared cases")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.prefix):
        parser.error("Use an alphanumeric/hyphen/underscore prefix")
    declared = [args.prefix + "-" + suffix for suffix in SUFFIXES]
    args.cases = args.cases if args.cases is not None else declared
    if any(name not in declared for name in args.cases):
        parser.error("--cases must be a subset of this prefix's ten declared conditions")
    if args.out.exists():
        parser.error(f"Refusing existing analysis output: {args.out}")
    if len(set(args.cases)) != len(args.cases):
        parser.error("Cases must not be duplicated")
    repo = Path(__file__).resolve().parents[3]
    cases = [plan_case(name, args, repo) for name in args.cases]
    sources = [sha(path) for path in (Path(__file__).resolve(), repo / "code/kim-study/analyze_study.py",
                                    repo / "code/vegas-study/v2/analyze_vegas.py", repo / "code/kim-study/path_truth_200s.csv")]
    record = {"schema_version": 1, "run_root": str(args.root.resolve()), "out": str(args.out.resolve()),
              "simulation_launch_commit": args.launch_commit, "run_prefix": args.prefix,
              "posthoc_helper_identity": git_identity(repo),
              "sources": sources, "workers": args.workers, "cases": cases,
              "method": "No simulations. Phase1 original analyzer with bins; Phase2 independent app/queue/Vegas validation against phase1. Micro root-qdisc absence is established by reviewed driver/actual config. All outputs are new, failures retained.",
              "extra_window": "Fixed-comp common first-false-renew window [90.194745440,91.958450720) is the first renewal's actual20-cycle history; end is excluded. Both modes use identical endpoints.",
              "status": "planned"}
    if args.plan_only:
        print(json.dumps(record, indent=2, sort_keys=True))
        return
    args.out.mkdir(parents=True)
    write(args.out / "analysis-plan.json", record)
    start = time.monotonic()
    record["start_time_unix"] = time.time()
    completed = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(analyze_case, case): case["case"] for case in cases}
        for future in as_completed(futures):
            result = future.result()
            completed[result["case"]] = result
            print(json.dumps({"case": result["case"], "status": result["status"], "wall_time_s": result["wall_time_s"]}), flush=True)
    record.update(cases=[completed[name] for name in args.cases], end_time_unix=time.time(),
                  wall_time_s=round(time.monotonic() - start, 6),
                  status="complete" if all(case["status"] == "complete" for case in completed.values()) else "failed")
    record["sources_after"] = [sha(path["path"]) for path in sources]
    if any(before["sha256"] != after["sha256"] for before, after in zip(sources, record["sources_after"])):
        record.update(status="failed", source_changed_during_analysis=True)
    write(args.out / "matrix.json", record)
    if record["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
