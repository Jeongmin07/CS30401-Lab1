"""Declared small BBR diagnostics; run inside the pinned course image.

Uses the course main_satnet and generated run configuration. This is shared
bottleneck admission on the supplied two-ground-station path, not natural
convergence of independent routes. Refuses to overwrite prior run directories.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


STATE = Path("/home/ubuntu/lab/data/seoul_london/state")
NS3 = Path("/home/ubuntu/ns-3.48")
REFERENCE = Path("/tmp/bbr-route-reference/build")
COURSE = Path("/home/ubuntu/lab/scripts")
CASES = {
    "reference-solo": {"reference": True, "observe": False, "starts": [0]},
    "patched-off-solo": {"reference": False, "observe": False, "starts": [0]},
    "observed-solo": {"reference": False, "observe": True, "starts": [0]},
    "observed-join10": {"reference": False, "observe": True, "starts": [0, 10]},
    "observed-together": {"reference": False, "observe": True, "starts": [0, 0]},
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def command_output(argv, cwd=None):
    return subprocess.check_output(argv, cwd=cwd, text=True).strip()


def run_case(name, root, timeout):
    definition = CASES[name]
    run = root / name
    run.mkdir(parents=True, exist_ok=False)
    subprocess.run([
        "bash", str(COURSE / "make_run.sh"), str(run), str(STATE),
        "TcpBbr", "100", "100", "40", "1584", "1585",
    ], check=True, capture_output=True, text=True)
    schedule = run / "schedule.csv"
    schedule.write_text("".join(
        f"{i},1584,1585,100000000000,{start * 1_000_000_000},,\n"
        for i, start in enumerate(definition["starts"])
    ))
    config = run / "config_ns3.properties"
    contents = config.read_text()
    contents = contents.replace("tcp_flow_enable_logging_for_tcp_flow_ids=set(0)",
                                "tcp_flow_enable_logging_for_tcp_flow_ids=set(" +
                                ",".join(str(i) for i in range(len(definition["starts"]))) + ")")
    config.write_text(contents)
    build = REFERENCE if definition["reference"] else NS3 / "build"
    binary = build / "scratch/main_satnet/ns3.48-main_satnet"
    env = os.environ.copy()
    # Copied binaries retain the original build's RUNPATH. Override it so the
    # reference process loads the copied unmodified libraries, not new ones.
    env["LD_LIBRARY_PATH"] = str(build / "lib")
    env["CS30401_BBR_OBSERVE"] = "1" if definition["observe"] else "0"
    env["CS30401_BBR_OBSERVE_DIR"] = str(run / "logs_ns3")
    argv = [str(binary), f"--run_dir={run}"]
    record = {
        "case": name, "definition": definition,
        "kind": "shared-bottleneck-admission-diagnostic-not-natural-route-merge",
        "repo_commit": command_output(["git", "-c", "safe.directory=/work", "rev-parse", "HEAD"], "/work"),
        "runner_sha256": sha(__file__),
        "ns3_head": command_output(["git", "rev-parse", "HEAD"], NS3),
        "effective_build_diff_sha256": hashlib.sha256(b"" if definition["reference"] else
            subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=NS3)).hexdigest(),
        "source_note": "Reference build copied before edits; its effective diff is empty."
                       if definition["reference"] else "Current installed source diff.",
        "observer_patch_sha256": None if definition["reference"] else
            sha(Path(__file__).parent / "ns3-observe.patch"),
        "config_sha256": sha(config), "schedule_sha256": sha(schedule),
        "command": argv, "environment": {key: env[key] for key in [
            "LD_LIBRARY_PATH", "CS30401_BBR_OBSERVE", "CS30401_BBR_OBSERVE_DIR"]},
        "runtime_files": {str(path.relative_to(build)): sha(path) for path in
                          [binary, *sorted((build / "lib").glob("*.so"))]},
        "state_static_sha256": {path.name: sha(path) for path in sorted(STATE.iterdir())
                                if path.is_file()},
        "state_note": "Unmodified supplied Seoul-London state; 100ms delta forwarding.",
        "image_digest": "ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4",
        "sim_seconds": 40, "rate_mbps": 100, "queue_packets": 100,
        "seed": 123456789, "primary_window_seconds": [10, 40],
        "event_window_seconds": [10, 15], "timeout_seconds": timeout,
        "status": "running",
    }
    manifest = run / "manifest.json"
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    started = time.monotonic()
    try:
        with (run / "out.txt").open("w") as out:
            completed = subprocess.run(argv, env=env, cwd=NS3, stdout=out,
                                       stderr=subprocess.STDOUT, timeout=timeout)
        record["returncode"] = completed.returncode
        record["status"] = "success" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        record["status"] = "timeout"
    record["wall_seconds"] = time.monotonic() - started
    record["outputs"] = {str(path.relative_to(run)): {
        "bytes": path.stat().st_size, "sha256": sha(path),
    } for path in sorted((run / "logs_ns3").glob("*")) if path.is_file()}
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ["case", "status", "wall_seconds"]}), flush=True)
    if record["status"] != "success":
        raise RuntimeError(f"{name}: {record['status']}; see {run / 'out.txt'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="+", choices=CASES)
    parser.add_argument("--root", type=Path, default=Path("/tmp/bbr-route-pilot"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    for name in args.cases:
        run_case(name, args.root, args.timeout)


if __name__ == "__main__":
    main()
