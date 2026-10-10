#!/usr/bin/env python3
"""Inventory or compare completed Vegas measurement CSVs without normalization.

Compatibility mode requires the same parameters/policy and preserve-beta off;
it intentionally permits changed launch code. Strict replay also compares all
recorded launch identities and requires the 24-column Vegas state CSV. This
post-run helper never invokes the simulator or changes a run directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


STATE_FIELDS = (
    "time_ns,vegas_instance,event,base_rtt_ns,cycle_min_rtt_ns,rtt_samples,"
    "cwnd_before_bytes,cwnd_after_bytes,ssthresh_bytes,diff_pkts,cong_state,"
    "renewal_enabled,renewal_rounds,renewal_count,old_base_rtt_ns,recent_min_ns,"
    "history_rounds,history_elapsed_ns,valid_renewal_cycle,ssthresh_before_bytes,"
    "announced_state,renewal_preserve_beta,beta,renewal_candidate_ns"
).split(",")
CONFIG_FILES = ("config_driver.json", "config_ns3.properties", "schedule.csv")
CASE_RE = re.compile(r"[A-Za-z0-9_-]+")
CSV_RE = re.compile(r"[A-Za-z0-9_.-]+\.csv")
SHA_RE = re.compile(r"[0-9a-f]{64}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), "input changed while hashing: " + str(path))
    return {"bytes": before.st_size, "sha256": digest.hexdigest()}


def invalid_constant(value):
    raise ValueError("Non-finite JSON number: " + value)


def read_json(path, inputs):
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), "input changed while reading: " + str(path))
    inputs[str(path.resolve())] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    # PowerShell's prepared v1 inventory has a UTF-8 BOM; it remains in its SHA.
    return json.loads(raw.decode("utf-8-sig"), parse_constant=invalid_constant)


def valid_receipt(value, label):
    require(isinstance(value, dict) and type(value.get("bytes")) is int and
            value["bytes"] >= 0 and isinstance(value.get("sha256"), str) and
            SHA_RE.fullmatch(value["sha256"]) is not None, "invalid receipt: " + label)
    return {"bytes": value["bytes"], "sha256": value["sha256"]}


def validate_manifest(manifest, label):
    require(isinstance(manifest, dict), label + ": case manifest must be an object")
    require(manifest.get("status") == "complete" and manifest.get("exit_code") == 0,
            label + ": case is not complete with exit code 0")
    require(manifest.get("source_worktree_dirty") is False,
            label + ": launch repository was not declared clean")
    require(isinstance(manifest.get("parameters"), dict) and
            isinstance(manifest.get("policy"), dict), label + ": parameters/policy missing")
    require(type(manifest["policy"].get("recent_min_renewal")) is bool,
            label + ": explicit renewal policy missing")


def hash_inputs(path, inputs):
    value = record(path)
    inputs[str(path.resolve())] = value
    return value


def inspect_run(root, name, include_state, inputs):
    require(CASE_RE.fullmatch(name) is not None, "invalid case name: " + name)
    directory = root / name
    manifest = read_json(directory / "case.json", inputs)
    validate_manifest(manifest, name)
    require(manifest.get("case") == name, name + ": manifest case name differs from directory")
    actual_configs = {}
    for filename in CONFIG_FILES:
        path = directory / filename
        declared = manifest.get(filename + "_sha256")
        if path.exists() or declared is not None:
            require(path.is_file() and isinstance(declared, str), name + ": config identity missing: " + filename)
            actual_configs[filename] = hash_inputs(path, inputs)
            require(actual_configs[filename]["sha256"] == declared,
                    name + ": actual config SHA differs from manifest: " + filename)
    if "actual_driver_settings_checked" in manifest:
        config = read_json(directory / "config_driver.json", inputs)
        require(all(config.get(k) == v for k, v in
                    manifest["actual_driver_settings_checked"].items()),
                name + ": saved actual driver settings differ from config")
    logs = directory / "logs_ns3"
    require(logs.is_dir(), name + ": logs_ns3 missing")
    excluded = {"timing_results.csv"}
    if not include_state:
        excluded.add("vegas_state.csv")
    paths = sorted(logs.glob("*.csv"))
    require(bool(paths), name + ": no CSV files")
    if include_state:
        state_path = logs / "vegas_state.csv"
        require(state_path.is_file(), name + ": strict replay requires vegas_state.csv")
        with state_path.open(encoding="utf-8", newline="") as stream:
            require(stream.readline().rstrip("\r\n").split(",") == STATE_FIELDS,
                    name + ": expected the 24-column v2 state schema")
    files, excluded_files = {}, {}
    for path in paths:
        require(CSV_RE.fullmatch(path.name) is not None and path.is_file(),
                name + ": invalid CSV filename: " + path.name)
        value = hash_inputs(path, inputs)
        (excluded_files if path.name in excluded else files)[path.name] = value
    require(bool(files), name + ": no selected measurement CSVs")
    require(inputs[str((directory / "case.json").resolve())] == record(directory / "case.json"),
            name + ": manifest changed while reading its run")
    return {"case_manifest": manifest, "files": files, "excluded_files": excluded_files,
            "actual_config_files": actual_configs}


def differences(left, right):
    missing = {"missing": True}
    return {key: {"reference": left.get(key, missing), "new": right.get(key, missing)}
            for key in sorted(left.keys() | right.keys()) if
            key not in left or key not in right or left[key] != right[key]}


def identity_map(items, label):
    require(isinstance(items, list) and bool(items), label + ": recorded identity list missing")
    result = {}
    for item in items:
        require(isinstance(item, dict) and isinstance(item.get("path"), str), label + ": identity path missing")
        path = item["path"]
        require(path not in result, label + ": duplicate identity path " + path)
        result[path] = valid_receipt(item, label + ": " + path)
    return result


def compare_manifests(old, new, strict):
    validate_manifest(old, "reference")
    validate_manifest(new, "new")
    excluded_params = {"name", "root"}
    if not strict:
        excluded_params.add("preserve_beta")
        require(old["parameters"].get("preserve_beta", False) is False and
                new["parameters"].get("preserve_beta", False) is False and
                old["policy"].get("preserve_beta", False) is False and
                new["policy"].get("preserve_beta", False) is False,
                "compatibility comparison requires preserve-beta off in both launches")
    params_old = {k: v for k, v in old["parameters"].items() if k not in excluded_params}
    params_new = {k: v for k, v in new["parameters"].items() if k not in excluded_params}
    policy_old, policy_new = dict(old["policy"]), dict(new["policy"])
    if not strict:
        policy_old.pop("preserve_beta", None)
        policy_new.pop("preserve_beta", None)
    checks = {"parameters": differences(params_old, params_new),
              "policy": differences(policy_old, policy_new)}
    if strict:
        identity_fields = ("source_commit", "patch_sha256", "official_image_digest", "binary_sha256")
        for field in identity_fields:
            require(isinstance(old.get(field), str) and bool(old[field]) and
                    isinstance(new.get(field), str) and bool(new[field]), field + ": launch identity missing")
        checks["launch_identity"] = differences({k: old[k] for k in identity_fields},
                                                {k: new[k] for k in identity_fields})
        for m, label in ((old, "reference"), (new, "new")):
            require(isinstance(m.get("binary"), dict) and isinstance(m["binary"].get("path"), str),
                    label + ": executable record missing")
            require(valid_receipt(m["binary"], label + ": executable")["sha256"] == m["binary_sha256"],
                    label + ": executable SHA fields disagree")
        checks["binary"] = differences({"path": old["binary"]["path"], **valid_receipt(old["binary"], "reference")},
                                       {"path": new["binary"]["path"], **valid_receipt(new["binary"], "new")})
        checks["sources"] = differences(identity_map(old.get("sources"), "reference sources"),
                                        identity_map(new.get("sources"), "new sources"))
        checks["shared_libraries"] = differences(identity_map(old.get("shared_libraries"), "reference libraries"),
                                                 identity_map(new.get("shared_libraries"), "new libraries"))
    return {"excluded_parameter_fields": sorted(excluded_params),
            "identity_scope": "recorded executable/source/library paths and content hashes" if strict else
                              "parameters/policy only; changed launch code is expected",
            "differences": checks, "all_match": not any(checks.values())}


def compare_files(old, new, strict):
    require(isinstance(old, dict) and bool(old), "reference measurement file map missing")
    require("timing_results.csv" not in old, "reference files must exclude wall-clock timing_results.csv")
    require(("vegas_state.csv" in old) == strict,
            "reference must include state for strict replay and exclude state for compatibility")
    reference = {}
    for filename, value in old.items():
        require(isinstance(filename, str) and CSV_RE.fullmatch(filename) is not None,
                "invalid reference CSV basename: " + str(filename))
        reference[filename] = valid_receipt(value, filename)
    checks = []
    for filename in sorted(reference.keys() | new.keys()):
        left, right = reference.get(filename), new.get(filename)
        checks.append({"file": filename, "reference": left, "new": right,
                       "match": left is not None and right is not None and left == right})
    return {"reference_count": len(reference), "new_count": len(new),
            "matched_count": sum(c["match"] for c in checks),
            "all_match": all(c["match"] for c in checks), "files": checks}


def git_observation():
    script = Path(__file__).resolve()
    repo = next((p for p in script.parents if (p / ".git").exists()), None)
    if repo is None and (Path("/work") / ".git").exists():
        # A fresh immutable replay checkout may receive this later-authored
        # helper under /tmp; observe its /work HEAD without editing the checkout.
        repo = Path("/work")
    if repo is None:
        return {"available": False, "reason": "helper is outside a Git checkout"}
    base = ["git", "-c", "safe.directory=" + str(repo), "-c", "core.autocrlf=true"]
    try:
        head = subprocess.check_output(base + ["rev-parse", "HEAD"], cwd=repo,
                                       text=True, stderr=subprocess.STDOUT).strip()
        status = subprocess.check_output(base + ["status", "--porcelain"], cwd=repo,
                                         text=True, stderr=subprocess.STDOUT)
        return {"available": True, "repository": str(repo), "head": head,
                "dirty": bool(status), "status_porcelain": status,
                "scope": "post-run helper observation; launch commits remain in case manifests"}
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"available": False, "reason": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="NEW JSON output; failures are retained")
    parser.add_argument("--inventory", action="store_true", help="write a reference inventory")
    parser.add_argument("--cases", nargs="+", help="explicit completed case names for inventory")
    parser.add_argument("--include-state", action="store_true", help="required when preparing a v2 replay inventory")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--map", dest="mappings", action="append", metavar="OLD_KEY=NEW_CASE")
    parser.add_argument("--strict-policy-replay", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be new; existing evidence is never overwritten")
    if args.inventory:
        if not args.cases or args.reference or args.mappings or args.strict_policy_replay:
            parser.error("--inventory requires --cases and forbids reference/map/strict comparison")
    elif not args.reference or not args.mappings or args.cases or args.include_state:
        parser.error("comparison requires --reference and repeated --map; cases/include-state are inventory options")
    root = args.root.resolve()
    report = {"schema_version": 1, "mode": "inventory" if args.inventory else
              "strict-policy-replay" if args.strict_policy_replay else "v1-compatibility",
              "root": str(root), "argv": sys.argv, "helper": {"path": str(Path(__file__).resolve()),
              **record(Path(__file__))}, "current_git": git_observation(), "input_receipts": {}, "errors": [],
              "method": "Compare original CSV byte sizes and SHA-256 hashes and complete file sets; no CSV row/column/value normalization.",
              "limits": ["timing_results.csv is excluded wall-clock metadata and retained separately when present.",
                         "Strict source/executable/library comparisons use launch-manifest hash records; live binaries or Docker identity are not independently inspected by this post-run helper.",
                         "Deterministic replay is not an independent statistical replication."]}
    report["current_git_head"] = report["current_git"].get("head")
    inputs, errors = report["input_receipts"], report["errors"]
    if args.inventory:
        report.update(include_state=args.include_state, cases={})
        for name in dict.fromkeys(args.cases):
            try:
                report["cases"][name] = inspect_run(root, name, args.include_state, inputs)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(name + ": " + str(exc))
                report["cases"][name] = {"error": str(exc)}
        report["measurement_file_count"] = sum(len(c.get("files", {})) for c in report["cases"].values())
    else:
        report.update(reference=str(args.reference.resolve()), comparisons=[])
        try:
            reference = read_json(args.reference, inputs)
            require(isinstance(reference.get("cases"), dict), "reference cases must be a mapping")
            require(reference.get("status", "pass") == "pass", "reference inventory did not pass")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append("reference: " + str(exc))
            reference = {"cases": {}}
        seen = set()
        for mapping in args.mappings:
            result = {"mapping": mapping, "match": False}
            report["comparisons"].append(result)
            try:
                require(mapping.count("=") == 1 and mapping not in seen, "invalid or duplicate mapping")
                seen.add(mapping)
                old_key, new_name = mapping.split("=")
                require(bool(old_key) and old_key in reference["cases"], "reference key missing: " + old_key)
                result.update(reference_key=old_key, new_case=new_name)
                old = reference["cases"][old_key]
                new = inspect_run(root, new_name, args.strict_policy_replay, inputs)
                result["new_case_manifest"] = new["case_manifest"]
                result["reference_case_manifest"] = old["case_manifest"]
                result["manifests"] = compare_manifests(old["case_manifest"], new["case_manifest"], args.strict_policy_replay)
                result["measurements"] = compare_files(old["files"], new["files"], args.strict_policy_replay)
                result["excluded_files"] = {"reference": old.get("excluded_files", {}), "new": new["excluded_files"]}
                result["match"] = result["manifests"]["all_match"] and result["measurements"]["all_match"]
                if not result["match"]:
                    errors.append(mapping + ": measurement or launch-contract mismatch")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                result["error"] = str(exc)
                errors.append(mapping + ": " + str(exc))
        report["measurement_file_count"] = sum(c.get("measurements", {}).get("new_count", 0) for c in report["comparisons"])
        report["matched_file_count"] = sum(c.get("measurements", {}).get("matched_count", 0) for c in report["comparisons"])
    report["status"] = "pass" if not errors else "fail"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "errors": len(errors), "out": str(args.out),
                      "measurement_file_count": report["measurement_file_count"],
                      "matched_file_count": report.get("matched_file_count"), "output": record(args.out)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
