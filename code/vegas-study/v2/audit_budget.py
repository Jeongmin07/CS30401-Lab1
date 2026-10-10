#!/usr/bin/env python3
"""Independently audit completed Vegas beta-budget runs; no simulator or imports.

Only case manifests, optional small matrix manifests, and vegas_state.csv are
read. Histories and the integer-nanosecond candidate are reconstructed without
using the experiment analyzer. IEEE-double target truncation is checked using
the original ns-3 expression, separately from exact rational arithmetic.
"""

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import sys


STATE_FIELDS = (
    "time_ns,vegas_instance,event,base_rtt_ns,cycle_min_rtt_ns,rtt_samples,"
    "cwnd_before_bytes,cwnd_after_bytes,ssthresh_bytes,diff_pkts,cong_state,"
    "renewal_enabled,renewal_rounds,renewal_count,old_base_rtt_ns,recent_min_ns,"
    "history_rounds,history_elapsed_ns,valid_renewal_cycle,ssthresh_before_bytes,"
    "announced_state,renewal_preserve_beta,beta,renewal_candidate_ns"
).split(",")


def number(row, field):
    return int(row[field]) if row[field] != "" else None


def receipt(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("input changed while hashing: " + str(path))
    return {"bytes": before.st_size, "sha256": digest.hexdigest()}


def double_target(w, baseline_ns, minimum_ns):
    # Keep the C++ operation order: divide two GetSeconds() doubles, then
    # multiply by w; casting a nonnegative double truncates toward zero.
    return w * ((baseline_ns / 1e9) / (minimum_ns / 1e9))


def candidate_for(recent, w, beta, preserve, minimum):
    if recent is None:
        return None, None, False
    if not preserve:
        return recent, recent, False
    if w <= beta:
        return None, None, False
    raw = recent * (w - beta) // w  # Python integers cannot overflow.
    target = double_target(w, raw, minimum)
    rejected = (not math.isfinite(target) or target < 0 or target > w or
                w - int(target) < beta)
    return (None if rejected else raw), raw, rejected


class BudgetAudit:
    def __init__(self, root, mss):
        self.root, self.mss = root, mss
        self.errors, self.inputs = [], {}
        self.candidates, self.renewals, self.cases = [], [], {}

    def check(self, condition, label, message):
        if not condition:
            self.errors.append(label + ": " + message)

    def pin(self, path):
        key = str(path.relative_to(self.root))
        value = receipt(path)
        self.inputs[key] = value
        return value

    def audit_case(self, name):
        errors_before = len(self.errors)
        directory = self.root / name
        manifest_path = directory / "case.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.pin(manifest_path)
        policy = manifest["policy"]
        enabled = policy["recent_min_renewal"]
        preserve = policy.get("renewal_preserve_beta", policy.get("preserve_beta"))
        beta, rounds, rise = policy["beta"], policy["rounds"], policy["min_rise_ns"]
        self.check(type(enabled) is bool and type(preserve) is bool, name,
                   "policy renewal/preserve flags must be explicit booleans")
        self.check(type(beta) is int and beta >= 0 and type(rounds) is int and
                   rounds >= 2 and type(rise) is int and rise > 0, name,
                   "invalid declared beta/rounds/minimum rise")
        self.check(manifest.get("status") == "complete" and manifest.get("exit_code") == 0,
                   name, "case is not successfully complete")
        self.check(manifest.get("source_worktree_dirty") is False, name,
                   "launch source was not declared clean")
        self.check(bool(manifest.get("source_commit")) and bool(manifest.get("patch_sha256")),
                   name, "launch source commit/patch hash missing")
        if preserve is None:
            raise ValueError(name + ": manifest has no preserve-beta policy")

        trace_path = directory / "logs_ns3" / "vegas_state.csv"
        self.pin(trace_path)
        states, counts, clears = {}, collections.Counter(), collections.Counter()
        own_renewals, post_diffs, exact_diffs = [], [], []
        all_floors, rounding_differences = [], []
        full_windows = guard_rejections = small_windows = 0
        previous_time = -1
        with trace_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != STATE_FIELDS:
                raise ValueError(name + ": expected the 24-column beta-budget schema")
            for line, row in enumerate(reader, 2):
                label = f"{name}:state:{line}"
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(label + ": malformed CSV field count")
                n = lambda key: number(row, key)
                t, inst, event = n("time_ns"), n("vegas_instance"), row["event"]
                self.check(t >= previous_time, label, "timestamp moved backwards")
                previous_time = t
                counts[event] += 1
                state = states.setdefault(inst, {"active": False, "history": [],
                    "count": 0, "pending": None, "last_base": None})
                base, minimum = n("base_rtt_ns"), n("cycle_min_rtt_ns")
                before, after = n("cwnd_before_bytes"), n("cwnd_after_bytes")
                ss_before, samples = n("ssthresh_before_bytes"), n("rtt_samples")
                old, recent, traced_candidate = (n("old_base_rtt_ns"),
                    n("recent_min_ns"), n("renewal_candidate_ns"))
                w = before // self.mss
                self.check(n("renewal_enabled") == int(enabled) and
                           n("renewal_preserve_beta") == int(preserve) and
                           n("renewal_rounds") == rounds and n("beta") == beta,
                           label, "trace policy differs from case manifest")
                previous_base = state["last_base"]
                if base is not None:
                    all_floors.append(base)
                    self.check(base > 0, label, "nonpositive baseline")
                    if event != "RENEW" and previous_base is not None:
                        self.check(base <= previous_base, label,
                                   "baseline rose without a RENEW event")
                    state["last_base"] = base
                valid = (state["active"] and n("cong_state") == 0 and
                    before >= ss_before and samples > 2 and minimum is not None and
                    minimum > 0 and base is not None)
                if event in ("ENABLE", "DISABLE"):
                    self.check(state["pending"] is None, label,
                               "state transition intervened before renewal decision")
                    state["active"] = event == "ENABLE"
                    state["history"].clear()
                    clears[event] += 1
                    self.check(n("announced_state") is not None and
                        ((n("announced_state") == 0) == (event == "ENABLE")),
                        label, "announced congestion state differs")
                    self.check(n("valid_renewal_cycle") == 0 and old is None and
                               recent is None and traced_candidate is None,
                               label, "transition contains candidate/cycle fields")
                elif event == "RENEW" or event.startswith("CYCLE_"):
                    self.check(n("valid_renewal_cycle") == int(valid), label,
                               "CA eligibility does not reconstruct")
                    self.check(n("announced_state") is None, label,
                               "decision contains an announced state")
                    pending = state["pending"]
                    if event == "RENEW" or pending is None:
                        if enabled and valid:
                            state["history"].append((t, minimum))
                            state["history"] = state["history"][-rounds:]
                        else:
                            state["history"].clear()
                            clears["INVALID_OR_DISABLED"] += 1
                        history = state["history"]
                        expected_recent = min(v for _, v in history) if len(history) == rounds else None
                        candidate, raw_candidate, guard_rejected = candidate_for(
                            expected_recent, w, beta, preserve, minimum)
                        self.check(recent == expected_recent and traced_candidate == candidate,
                                   label, "recent minimum or integer/guarded candidate differs")
                        if expected_recent is not None:
                            full_windows += 1
                            guard_rejections += int(guard_rejected)
                            small_windows += int(preserve and w <= beta)
                            prior_base = old if event == "RENEW" else base
                            admissible = (candidate is not None and candidate > prior_base and
                                          candidate - prior_base >= rise)
                            self.check((event == "RENEW") == admissible, label,
                                       "renewal iff candidate passes rise condition differs")
                            record = {"case": name, "time_ns": t, "vegas_instance": inst,
                                "history_first_time_ns": history[0][0],
                                "history_elapsed_ns": t - history[0][0],
                                "cwnd_before_bytes": before, "cwnd_segments": w,
                                "ssthresh_before_bytes": ss_before, "beta": beta,
                                "preserve_beta": preserve, "old_base_rtt_ns": prior_base,
                                "recent_min_ns": expected_recent,
                                "raw_integer_candidate_ns": raw_candidate,
                                "guarded_candidate_ns": candidate,
                                "double_guard_rejected": guard_rejected,
                                "observed_renewal": event == "RENEW"}
                            self.candidates.append(record)
                        if event == "RENEW":
                            self.check(pending is None and enabled and valid and
                                       len(history) == rounds and old is not None,
                                       label, "renewal is not a valid full-history update")
                            self.check(base == candidate and recent <= minimum and before == after
                                       and n("diff_pkts") is None, label,
                                       "RENEW value or unchanged predecision cwnd differs")
                            if previous_base is not None and old is not None:
                                self.check(old <= previous_base, label,
                                           "pre-renew baseline rose without another renewal")
                            self.check(n("history_rounds") == len(history) and
                                       n("history_elapsed_ns") == t - history[0][0],
                                       label, "renewal history length/elapsed differs")
                            state["count"] += 1
                            renewal = dict(record)
                            renewal.update({"new_base_rtt_ns": base,
                                "cycle_min_rtt_ns": minimum, "rtt_samples": samples,
                                "renewal_count": state["count"]})
                            self.renewals.append(renewal)
                            own_renewals.append(renewal)
                            state["pending"] = {"time": t, "recent": recent,
                                "candidate": candidate, "before": before, "minimum": minimum,
                                "samples": samples, "ss_before": ss_before, "record": renewal}
                            state["history"].clear()
                    if event.startswith("CYCLE_"):
                        if pending is not None:
                            self.check((t, recent, traced_candidate, before, minimum, samples,
                                ss_before) == (pending["time"], pending["recent"],
                                pending["candidate"], pending["before"], pending["minimum"],
                                pending["samples"], pending["ss_before"]), label,
                                "RENEW does not match following same-time cycle")
                            self.check(base == pending["candidate"], label,
                                       "same-cycle baseline differs from renewal candidate")
                            state["pending"] = None
                        self.check(old is None and n("history_rounds") == len(state["history"]) and
                            n("history_elapsed_ns") == (t - state["history"][0][0]
                                if state["history"] else None), label,
                            "cycle history length/elapsed differs")
                        expected_event = ("CYCLE_INCREASE" if after > before else
                                          "CYCLE_DECREASE" if after < before else "CYCLE_HOLD")
                        self.check(event == expected_event, label, "cwnd decision label differs")
                        if samples > 2:
                            self.check(base is not None and minimum is not None and minimum > 0 and
                                       base <= minimum, label, "base <= cycle minimum violated")
                            target = double_target(w, base, minimum)
                            if not math.isfinite(target) or target < 0 or target > w:
                                raise ValueError(label + ": invalid ns-3 double target")
                            double_diff = w - int(target)
                            exact_diff = w - (w * base // minimum)
                            self.check(n("diff_pkts") == double_diff, label,
                                       "original double-cast diff does not reconstruct")
                            if exact_diff != double_diff:
                                rounding_differences.append({"time_ns": t,
                                    "vegas_instance": inst, "exact_diff": exact_diff,
                                    "double_diff": double_diff, "double_target": target})
                            if pending is not None:
                                record = pending["record"]
                                record.update({"postrenew_double_diff": double_diff,
                                    "postrenew_exact_diff": exact_diff,
                                    "cwnd_after_bytes": after, "decision": event})
                                post_diffs.append(double_diff)
                                exact_diffs.append(exact_diff)
                                if preserve:
                                    self.check(exact_diff >= beta and double_diff >= beta,
                                               label, "accepted renewal violated beta budget")
                        else:
                            self.check(n("diff_pkts") is None, label,
                                       "insufficient-sample cycle reports diff")
                else:
                    self.check(False, label, "unrecognized event " + event)
                self.check(n("renewal_count") == state["count"], label,
                           "renewal count does not reconstruct")
                if event in ("ENABLE", "DISABLE"):
                    self.check(n("history_rounds") == 0 and n("history_elapsed_ns") is None,
                               label, "transition did not clear history")
        self.check(all(s["pending"] is None for s in states.values()), name,
                   "renewal lacks same-cycle decision at EOF")
        self.check(receipt(trace_path) == self.inputs[str(trace_path.relative_to(self.root))],
                   name, "trace changed while auditing")
        parameters = manifest.get("parameters", {})
        fixed = (parameters.get("kind") == "micro" and
                 parameters.get("before_ms") == parameters.get("after_ms") and
                 parameters.get("before_ms") is not None)
        self.cases[name] = {"errors": len(self.errors) - errors_before,
            "policy": policy, "source_commit": manifest.get("source_commit"),
            "patch_sha256": manifest.get("patch_sha256"),
            "official_image_digest": manifest.get("official_image_digest"),
            "binary_sha256": manifest.get("binary_sha256"),
            "launch_sources": manifest.get("sources", []), "rows": sum(counts.values()),
            "event_counts": dict(counts), "history_clear_reasons": dict(clears),
            "instances": sorted(states), "full_history_candidates": full_windows,
            "w_le_beta_candidates": small_windows,
            "double_guard_rejections": guard_rejections,
            "renewal_count": len(own_renewals),
            "fixed_propagation_renewal_count": len(own_renewals) if fixed else None,
            "maximum_observed_baseline_ns": max(all_floors, default=None),
            "maximum_renewed_baseline_ns": max((x["new_base_rtt_ns"] for x in own_renewals), default=None),
            "min_postrenew_double_diff": min(post_diffs, default=None),
            "min_postrenew_exact_diff": min(exact_diffs, default=None),
            "double_vs_exact_diff_disagreements": rounding_differences}


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--cases", nargs="+", default=["v2*"], help="case names or glob patterns")
    parser.add_argument("--mss", type=int, default=1380, help="configured TCP MSS in bytes")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    if args.mss <= 0:
        parser.error("--mss must be positive")
    if out.exists():
        parser.error("--out must be a NEW directory; existing evidence is never overwritten")
    names = sorted({p.name for pattern in args.cases for p in root.glob(pattern)
                    if p.is_dir() and (p / "case.json").is_file()})
    if not names:
        parser.error("no case directories matched")
    audit = BudgetAudit(root, args.mss)
    for path in sorted(root.glob("*matrix*.json")):
        audit.pin(path)
    for name in names:
        try:
            audit.audit_case(name)
        except (KeyError, ValueError, TypeError, OSError, ZeroDivisionError) as exc:
            audit.errors.append(name + ": audit could not finish: " + str(exc))
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "pass" if not audit.errors else "fail",
        "configured_mss_bytes": args.mss, "cases": audit.cases, "errors": audit.errors,
        "limits": ["Only manifests and policy-state traces are audited; application delivery, queues, drops and routing are not recomputed.",
            "Configured MSS is an explicit audit input; it is not inferable solely from this state trace.",
            "The beta guarantee is for each accepted update's current decision, not a lasting congestion classifier or total queue-absorption bound.",
            "Launch source/binary/image identities are copied from manifests, not independently inspected in this post-run audit."]}
    identity = {"schema_version": 1, "root": str(root), "selected_cases": names,
        "configured_mss_bytes": args.mss, "auditor": receipt(Path(__file__)),
        "inputs": audit.inputs}
    (out / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out / "input-manifest.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    write_csv(out / "renewals.csv", audit.renewals)
    write_csv(out / "candidates.csv", audit.candidates)
    print(json.dumps({"status": report["status"], "cases": names,
                      "errors": len(audit.errors), "out": str(out)}))
    return 0 if not audit.errors else 1


if __name__ == "__main__":
    sys.exit(main())
