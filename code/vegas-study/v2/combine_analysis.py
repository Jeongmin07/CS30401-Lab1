"""Combine completed disjoint post-hoc matrices, preserving every original receipt."""
import argparse, hashlib, json
from pathlib import Path

def fingerprint(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path, nargs="+")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists(): p.error("Refusing existing output")
    matrices = [json.loads(x.read_text()) for x in a.inputs]
    first = matrices[0]
    source_ids = lambda m: [(x["path"], x["sha256"]) for x in m["sources"]]
    cases = []
    for matrix in matrices:
        assert matrix["status"] == "complete"
        for key in ("simulation_launch_commit", "run_root", "run_prefix"):
            assert matrix[key] == first[key], ("Input mismatch", key)
        assert source_ids(matrix) == source_ids(first), "Analysis source mismatch"
        assert source_ids({"sources":matrix["sources_after"]}) == source_ids(matrix)
        assert all(x["status"] == "complete" for x in matrix["cases"])
        cases.extend(matrix["cases"])
    assert len({x["case"] for x in cases}) == len(cases), "Duplicate cases"
    assert len(cases) == 10, "Expected exactly the declared five matched pairs"
    result = dict(first)
    result.update(cases=sorted(cases, key=lambda x:x["case"]), out=str(a.out.resolve()),
        status="complete", partial_matrix_receipts=[fingerprint(x) for x in a.inputs],
        partial_matrix_git_identities=[m["posthoc_helper_identity"] for m in matrices],
        combine_helper=fingerprint(__file__),
        extra_window="Legacy label first-false-renew [90.194745440,91.958450720) is the V1 first false-renewal history used as a common reference window, NOT the actual V2 renewal history. Original output labels/partial receipts remain unchanged.")
    for key in ("wall_time_s", "start_time_unix", "end_time_unix", "workers"):
        result.pop(key, None)
    result["execution_qualification"] = "Eight micro cases and two LEO cases were analyzed in separate overlapping matrices; their original runtimes and identities remain in the partial receipts and per-case phases. This is a merge of completed analysis receipts, not a new simulation or a measured combined analysis runtime."
    a.out.mkdir(parents=True)
    (a.out/"matrix.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status":"complete", "cases":len(cases), "out":str(a.out)}))

if __name__ == "__main__": main()
