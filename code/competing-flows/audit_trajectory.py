"""Check whether a guarded late flow changes the measured network trajectory.

The six declared comparisons retain raw row identities, including transmission
tags and packet UIDs. Only the sender's threshold column and THRESHOLD_* control
events are removed. Runtime profiling is excluded explicitly. This is trace
equality, not an instrumented proof of
each internal TCP decision.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path


EXCLUDED_FILES = {"timing_results.csv"}
PAIRS = (("join10-dd", "join10-dg"), ("join10-gd", "join10-gg"),
         ("same-start-dd", "same-start-gd-later"),
         ("same-start-gd", "same-start-gd-first"),
         ("join10-dd", "join10-gd-later"),
         ("join10-gd", "join10-gd-first"))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rows(path):
    named = "study" in path.name and path.name != "study_drop_coverage.csv"
    with path.open(newline="") as source:
        if named:
            reader = csv.DictReader(source)
            if "time_ns" not in reader.fieldnames:
                raise ValueError(f"Missing named time column: {path}")
            previous = -1
            for row in reader:
                current = int(row["time_ns"])
                if current < previous:
                    raise ValueError(f"Unordered trace: {path}")
                previous = current
                if path.name.endswith("_study_events.csv") and row["event"].startswith("THRESHOLD_"):
                    continue
                # Retain all other fields, including time, state, UID and tags.
                yield {key: value for key, value in row.items() if key != "threshold"}
        else:
            yield from csv.reader(source)


def compare_file(left, right):
    hashes = [hashlib.sha256(), hashlib.sha256()]
    counts = [0, 0]
    first = None
    sentinel = object()
    for index, pair in enumerate(itertools.zip_longest(rows(left), rows(right), fillvalue=sentinel)):
        for side, row in enumerate(pair):
            if row is not sentinel:
                hashes[side].update((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
                counts[side] += 1
        if first is None and pair[0] != pair[1]:
            first = {"normalized_row_index_zero_based": index,
                     "left": None if pair[0] is sentinel else pair[0],
                     "right": None if pair[1] is sentinel else pair[1]}
    fingerprints = [value.hexdigest() for value in hashes]
    raw = [digest(left), digest(right)]
    return {"path": "logs_ns3/" + left.name, "normalized_rows": counts,
            "normalized_sha256": fingerprints, "raw_sha256": raw,
            "raw_equal": raw[0] == raw[1], "normalized_equal": first is None,
            "first_difference": first}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-competing"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"Refusing to overwrite {args.out}")
    comparisons = []
    for a, b in PAIRS:
        manifests = [json.loads((args.root / name / "case.json").read_text()) for name in (a, b)]
        if any(m["status"] != "complete" or m["exit_code"] != 0 for m in manifests):
            raise ValueError("Requires completed cases")
        for key in ("patch_sha256", "binary_sha256", "runner_sha256",
                    "official_image_digest", "make_run_sha256"):
            if manifests[0][key] != manifests[1][key]:
                raise ValueError(f"Different provenance field {key}")
        for key in ("rate", "queue", "duration", "start0_s", "start1_s", "state", "trace"):
            if manifests[0]["parameters"][key] != manifests[1]["parameters"][key]:
                raise ValueError(f"Different simulation parameter {key}")
        config_hashes = [digest(args.root / name / "config_ns3.properties") for name in (a, b)]
        if config_hashes[0] != config_hashes[1] or any(
                m["config_ns3.properties_sha256"] != value for m, value in zip(manifests, config_hashes)):
            raise ValueError("Actual configuration hashes differ or contradict the manifests")
        folders = [args.root / name / "logs_ns3" for name in (a, b)]
        inventories = [{p.name for p in folder.glob("*.csv")} for folder in folders]
        if inventories[0] != inventories[1] or not EXCLUDED_FILES <= inventories[0]:
            raise ValueError("Different or incomplete CSV inventory")
        files = [compare_file(folders[0] / name, folders[1] / name)
                 for name in sorted(inventories[0] - EXCLUDED_FILES)]
        comparisons.append({"left": a, "right": b,
                            "source_commits": [m["source_commit"] for m in manifests],
                            "actual_config_sha256": config_hashes[0],
                            "verified_equal_simulation_hashes": {
                                key: manifests[0][key] for key in ("patch_sha256", "binary_sha256", "runner_sha256")},
                            "files": files,
                            "all_normalized_equal": all(item["normalized_equal"] for item in files)})
    output = {"schema_version": 1, "script_sha256": digest(Path(__file__)),
              "excluded_files": sorted(EXCLUDED_FILES),
              "normalization": "Ignore threshold column in named study traces and THRESHOLD_* sender control events only; retain every other row/field, UID and transmission tag.",
              "limitation": "Matching traced outputs does not expose duplicate-ACK counters, SACK scoreboard state or every internal loss-decision invocation.",
              "comparisons": comparisons}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "pairs_equal": [c["all_normalized_equal"] for c in comparisons]}))
    if not all(c["all_normalized_equal"] for c in comparisons):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
