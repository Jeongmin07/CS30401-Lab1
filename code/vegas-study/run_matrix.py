"""Run the declared matched Vegas controls; no random search or silent retries."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
IMAGE = "sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prefix", default="v1")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--image-digest", required=True)
    p.add_argument("--out", type=Path, default=Path("/tmp/cs30401-vegas/matrix-v1.json"))
    p.add_argument("--only", nargs="*", choices=("fixed", "step", "fixed-comp", "step-comp", "leo"))
    a = p.parse_args()
    if a.image_digest != IMAGE or not 1 <= a.workers <= 3:
        p.error("Pinned image and 1–3 workers required")
    if a.out.exists():
        raise SystemExit("Refusing existing matrix record")
    families = [("fixed", ["--after-ms", "45"]), ("step", []),
                ("fixed-comp", ["--after-ms", "45", "--competitor"]),
                ("step-comp", ["--competitor"]), ("leo", ["--kind", "leo"])]
    tasks = []
    for family, extra in families:
        if a.only and family not in a.only:
            continue
        for enabled in (False, True):
            name = f"{a.prefix}-{family}-{'renew' if enabled else 'base'}"
            cmd = [sys.executable, str(ROOT / "run_case.py"), name, "--image-digest", a.image_digest, *extra]
            if enabled:
                cmd.append("--renewal")
            tasks.append({"case": name, "family": family, "renewal": enabled, "command": cmd})
    record = {"schema_version": 1, "status": "running", "workers": a.workers,
              "declared_tasks_before_launch": tasks, "results": [], "start_time_unix": time.time()}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    def save():
        a.out.write_text(json.dumps(record, indent=2) + "\n")
    def run(task):
        started = time.monotonic()
        result = subprocess.run(task["command"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return {**task, "runner_exit_code": result.returncode,
                "runner_wall_s": round(time.monotonic() - started, 3), "output": result.stdout}
    save()
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(run, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            record["results"].append(result)
            save()
            print(result["output"].strip(), flush=True)
    record.update(status="complete" if all(r["runner_exit_code"] == 0 for r in record["results"]) else "failed",
                  wall_time_s=round(time.monotonic() - start, 3), end_time_unix=time.time())
    save()
    print(json.dumps({"matrix": str(a.out), "status": record["status"], "cases": len(tasks),
                      "wall_time_s": record["wall_time_s"]}), flush=True)
    raise SystemExit(0 if record["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
