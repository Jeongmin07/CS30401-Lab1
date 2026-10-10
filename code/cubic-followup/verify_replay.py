"""Compare independently exported raw hashes, settings, and deterministic metrics."""
import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path


def rows(path):
    with (path / "results.csv").open(newline="") as f:
        items = list(csv.DictReader(f))
    result = {r["case"]: r for r in items}
    if len(result) != len(items):
        raise ValueError("Duplicate case in results")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("Refusing to overwrite verification record")
    ref, replay = rows(a.reference), rows(a.replay)
    if set(ref) != set(replay) or len(ref) != 31:
        raise ValueError("Expected the same 31 declared cases")
    hashes = [json.loads((root / "raw_hashes.json").read_text()) for root in (a.reference, a.replay)]
    if any(set(h) != set(ref) for h in hashes):
        raise ValueError("Raw hash case set differs from results")
    differences = []
    raw_count = 0
    for name in sorted(ref):
        if set(ref[name]) != set(replay[name]):
            raise ValueError(f"Result columns differ: {name}")
        for key, value in ref[name].items():
            other = replay[name][key]
            equal = Decimal(value) == Decimal(other) if key == "rate_mbps" else value == other
            if key != "wall_time_s" and not equal:
                differences.append(dict(case=name, field=key, reference=value, replay=replay[name][key]))
        for field in ("parameters", "patch_sha256", "binary_sha256", "status", "exit_code"):
            manifests = [json.loads((root / "cases" / name / "case.json").read_text())
                         for root in (a.reference, a.replay)]
            values = [m[field] for m in manifests]
            if field == "parameters":
                # Patch locations depend on the bind mount; the patch content is checked separately.
                values = [{k: v for k, v in opts.items() if k != "patch"} for opts in values]
            if values[0] != values[1]:
                differences.append(dict(case=name, field=field, reference=values[0], replay=values[1]))
        file_maps = [{r["file"]: r for r in h[name]} for h in hashes]
        if any(len(m) != len(h[name]) for m, h in zip(file_maps, hashes)):
            raise ValueError(f"Duplicate raw filename: {name}")
        if set(file_maps[0]) != set(file_maps[1]):
            differences.append(dict(case=name, field="raw_file_set"))
            continue
        for file, record in file_maps[0].items():
            raw_count += 1
            if record != file_maps[1][file]:
                differences.append(dict(case=name, field="raw_file", file=file))
    record = dict(verdict="PASS" if not differences else "FAIL", cases=len(ref),
                  raw_files_compared=raw_count, analysis_hashes_compared=len(ref),
                  comparison="Exact SHA-256 and result/settings equality; wall time and patch location excluded",
                  numeric_comparison_fields=["rate_mbps"],
                  differences=differences)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
