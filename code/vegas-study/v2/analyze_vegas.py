"""Summarize existing Vegas experiment logs without running a simulation.

Application delivery is independently summed over exact [start_ns, end_ns)
windows. Queue sojourn is packet weighted; queue occupancy is time weighted.
Examples:
  python analyze_vegas.py RUN --out NEW_DIR --event-s 100
  python analyze_vegas.py RUN --out NEW_DIR --study-analysis RUN/analysis.json
  python analyze_vegas.py OLD_RUN --out NEW_DIR --allow-legacy --event-s 5 \
      --window post:5:20 --window last5:15:20
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re

NS = 1_000_000_000
SEQ_MOD = 1 << 32


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return None if value in (None, "") else int(value)


def ns(value):
    scaled = Decimal(str(value)) * NS
    require(scaled.is_finite() and scaled == scaled.to_integral_value(),
            f"Time must be finite and exact to a nanosecond: {value}")
    return int(scaled)


def fingerprint(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), f"File changed while hashing: {path}")
    return {"path": str(path), "bytes": after.st_size, "sha256": digest.hexdigest()}


def rows(path, time_column="time_ns", required=()):
    previous = -1
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(set(required).issubset(reader.fieldnames or []),
                f"Missing columns in {path}: {set(required) - set(reader.fieldnames or [])}")
        for line, row in enumerate(reader, 2):
            time = number(row.get(time_column))
            require(time is not None and time >= previous,
                    f"Nonchronological/missing time at {path}:{line}")
            previous = time
            yield time, row


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def duration_ns(run, manifest):
    config = run / "config_ns3.properties"
    if config.exists():
        for line in config.read_text().splitlines():
            if line.strip().startswith("simulation_end_time_ns="):
                result = int(line.split("=", 1)[1])
                require(result > 0, "Nonpositive run duration")
                return result
    for key in ("duration", "duration_s"):
        value = manifest.get("parameters", {}).get(key, manifest.get(key))
        if value is not None:
            result = ns(value)
            require(result > 0, "Nonpositive run duration")
            return result
    raise ValueError("No actual simulation duration in config/manifest")


def nested_items(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield path, item
            yield from nested_items(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from nested_items(item, f"{prefix}[{index}]")


def manifest_validation(run, manifest, allow_legacy):
    require(manifest.get("status") == "complete" and manifest.get("exit_code") == 0,
            "Manifest must report completed simulation with exit_code=0")
    commits = {key: value for key, value in nested_items(manifest)
               if "commit" in key.lower() and isinstance(value, str)
               and re.fullmatch(r"[0-9a-f]{40}", value)}
    require(commits or allow_legacy, "Manifest has no full launch/source commit; use --allow-legacy only for old runs")
    declared_hashes = {key: value for key, value in nested_items(manifest)
                       if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)}
    require(declared_hashes, "Manifest has no declared artifact SHA256")
    checked = []
    for name in ("config_ns3.properties", "schedule.csv", "config_driver.json"):
        expected = manifest.get(name + "_sha256")
        if expected:
            actual = fingerprint(run / name)
            require(actual["sha256"] == expected, f"Original config/schedule changed: {name}")
            checked.append(name)
    current = []
    for key, record in nested_items(manifest):
        if isinstance(record, dict) and "path" in record and "sha256" in record:
            path = Path(record["path"])
            if path.is_file():
                actual = fingerprint(path)
                current.append({"manifest_key": key, **actual,
                                "matches_launch_declaration": actual["sha256"] == record["sha256"]})
    return {"completed_exit_zero": True, "launch_commit_fields": commits,
            "declared_artifact_hashes": declared_hashes,
            "checked_original_config_schedule": checked,
            "currently_present_declared_artifacts": current,
            "qualification": "Source/binary declarations describe launch provenance. Current-file hashes are separate; later rebuilding/editing does not rewrite the original run. Missing old launch commit is explicit in legacy mode."}


class Union:
    """Union of unwrapped TCP payload byte intervals, independent of app delivery."""
    def __init__(self):
        self.intervals = []
        self.total = 0
        self.reference = None

    def add(self, sequence, size):
        start = sequence if self.reference is None else sequence + round(
            (self.reference - sequence) / SEQ_MOD) * SEQ_MOD
        end = start + size
        self.reference = max(self.reference or end, end)
        left = 0
        while left < len(self.intervals) and self.intervals[left][1] < start:
            left += 1
        right, removed = left, 0
        while right < len(self.intervals) and self.intervals[right][0] <= end:
            old_start, old_end = self.intervals[right]
            start, end = min(start, old_start), max(end, old_end)
            removed += old_end - old_start
            right += 1
        self.intervals[left:right] = [(start, end)]
        self.total += end - start - removed


class Distribution:
    def __init__(self):
        self.values = Counter()
        self.count = 0
        self.total = 0
        self.bytes = 0

    def add(self, value, size):
        self.values[value] += 1
        self.count += 1
        self.total += value
        self.bytes += size

    def result(self):
        if not self.count:
            return {"packet_count": 0, "packet_bytes": 0,
                    "mean_ns": None, "p95_ns": None, "p99_ns": None, "max_ns": None}
        quantiles, cumulative = {}, 0
        for value, count in sorted(self.values.items()):
            cumulative += count
            for name, numerator in (("p95_ns", 95), ("p99_ns", 99)):
                if name not in quantiles and cumulative * 100 >= self.count * numerator:
                    quantiles[name] = value
        return {"packet_count": self.count, "packet_bytes": self.bytes,
                "mean_ns": self.total / self.count, "minimum_ns": min(self.values),
                "max_ns": max(self.values), **quantiles}


def make_windows(duration, events, extras):
    result = [("whole", 0, duration), ("late20", max(0, duration - 20 * NS), duration)]
    for event in events:
        require(0 < event < duration, f"Event outside open run interval: {event / NS}")
        tag = format(Decimal(event) / NS, "f")
        result.append(("prestep_" + tag, max(0, event - 20 * NS), event))
        start, end = event + 10 * NS, min(duration, event + 30 * NS)
        if start < end:
            result.append(("poststep_" + tag, start, end))
    for item in extras:
        label, start, end = item.split(":")
        result.append((label, ns(start), ns(end)))
    require(len({item[0] for item in result}) == len(result), "Window labels must be unique")
    require(all(0 <= start < end <= duration for _, start, end in result),
            "Window must satisfy 0 <= start < end <= duration")
    return [{"window": label, "start_ns": start, "end_ns": end,
             "start_s": start / NS, "end_s": end / NS,
             "flows": defaultdict(Counter), "drop_rows_by_layer": Counter()}
            for label, start, end in result]


def in_windows(windows, time):
    return [window for window in windows if window["start_ns"] <= time < window["end_ns"]]


def connection_key(row):
    return tuple(row.get(name) for name in
                 ("node_id", "local_ip", "local_port", "connection_id", "peer_ip", "peer_port"))


def app_and_tcp(logs, windows, duration):
    inputs, connections, totals = [], {}, Counter()
    wire = defaultdict(Union)
    app_rows = 0
    paths = sorted(logs.glob("study_app_rx_node_*_port_*.csv"))
    require(paths, "Receiver application traces are required")
    for path in paths:
        inputs.append(path)
        for time, row in rows(path, required=("payload_bytes", "flow_id", "connection_total_rx_bytes")):
            require(0 <= time <= duration, f"App delivery beyond run duration: {path}")
            fid, size = number(row["flow_id"]), number(row["payload_bytes"])
            require(fid is not None and size is not None and size > 0, "App flow/payload must be explicit positive delivery")
            key = connection_key(row)
            before = connections.get(key, {"flow_id": fid, "bytes": 0, "rows": 0})
            require(before["flow_id"] == fid, "Connection changed flow identity")
            before["bytes"] += size
            before["rows"] += 1
            require(before["bytes"] == number(row["connection_total_rx_bytes"]),
                    f"App connection cumulative bytes disagree: {path}:{time}")
            connections[key] = before
            totals[fid] += size
            app_rows += 1
            for window in in_windows(windows, time):
                window["flows"][fid]["application_bytes"] += size
    for path in sorted(logs.glob("tcp_flow_*_study_packets.csv")):
        inputs.append(path)
        for time, row in rows(path):
            fid, size = number(row.get("flow_id")), number(row.get("payload_bytes")) or 0
            require(fid is not None, "Sender flow ID is missing")
            kind = row.get("event", "").upper()
            if kind not in ("TX", "RETX") or size <= 0:
                continue
            for window in in_windows(windows, time):
                count = window["flows"][fid]
                prefix = "sender_payload_tx" if kind == "TX" else "official_retransmission"
                count[prefix + "_rows"] += 1
                count[prefix + "_bytes"] += size
    for path in sorted(logs.glob("tcp_flow_*_study_events.csv")):
        inputs.append(path)
        for time, row in rows(path):
            if row.get("event") != "CONG":
                continue
            fid, old, new = number(row["flow_id"]), number(row["old_value"]), number(row["new_value"])
            if new != old and new in (3, 4):
                for window in in_windows(windows, time):
                    window["flows"][fid]["recovery_entries" if new == 3 else "LOSS_entries"] += 1
    for path in sorted(logs.glob("study_rx_node_*_port_*.csv")):
        inputs.append(path)
        for time, row in rows(path):
            size = number(row.get("payload_bytes")) or 0
            if not size or not 0 <= time < duration:
                continue
            fid = number(row.get("flow_id"))
            if fid is None:
                fid = connections.get(connection_key(row), {}).get("flow_id")
            require(fid is not None, "Unmapped positive wire payload")
            wire[fid].add(int(row["seq"]), size)
    drop_path = logs / "study_drops.csv"
    drop_unique = defaultdict(set)
    unmapped_drops = Counter()
    if drop_path.exists():
        inputs.append(drop_path)
        for time, row in rows(drop_path):
            fid, tx = number(row.get("flow_id")), number(row.get("tx_id"))
            for window in in_windows(windows, time):
                window["drop_rows_by_layer"][row.get("layer", "unknown")] += 1
                if fid is not None:
                    window["flows"][fid]["drop_trace_rows"] += 1
                if fid is not None and tx is not None and tx > 0:
                    drop_unique[(window["window"], fid)].add(tx)
                else:
                    unmapped_drops[window["window"]] += 1
    fids = sorted(set(totals) | set(wire) | {fid for window in windows for fid in window["flows"]})
    fields = ("application_bytes", "sender_payload_tx_rows", "sender_payload_tx_bytes",
              "official_retransmission_rows", "official_retransmission_bytes",
              "recovery_entries", "LOSS_entries", "drop_trace_rows")
    for window in windows:
        flows = {}
        for fid in fids:
            count = {key: window["flows"][fid].get(key, 0) for key in fields}
            count["distinct_tagged_transmissions_dropped"] = len(drop_unique[(window["window"], fid)])
            count["application_goodput_mbps"] = count["application_bytes"] * 8 * NS / (
                window["end_ns"] - window["start_ns"]) / 1e6
            flows[str(fid)] = count
        window["flows"] = flows
        window["application_sum_bytes"] = sum(item["application_bytes"] for item in flows.values())
        window["application_sum_goodput_mbps"] = sum(item["application_goodput_mbps"] for item in flows.values())
        window["drop_rows_without_transmission_identity"] = unmapped_drops[window["window"]]
    whole = windows[0]["flows"]
    require(sum(item["application_bytes"] for item in whole.values()) == sum(totals.values()),
            "App rows at the excluded duration endpoint or inconsistent whole-run sum")
    return inputs, {"app_trace_rows": app_rows,
                    "connections": [{"identity": list(key), **value} for key, value in connections.items()],
                    "wire_application_terminal": {str(fid): {
                        "wire_unique_payload_bytes": wire[fid].total,
                        "application_bytes": totals[fid],
                        "wire_unique_minus_application_bytes": wire[fid].total - totals[fid]}
                        for fid in fids}}


def coverage(path):
    if not path.exists():
        return {"available": False, "absence_of_loss_inference": "unsupported: coverage unavailable"}
    result, failed = Counter(), []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            result[row.get("layer", "unknown")] += 1
            if row.get("connected", "").lower() not in ("1", "true"):
                failed.append(row)
    return {"available": True, "rows_by_layer": dict(result), "failed_hooks": failed,
            "qualification": "Per-hook records are preserved. TcDrop and per-device root_queue_disc_absent are required in addition to queue/device/IP drops before asserting complete modeled network-drop coverage."}


def queue_metrics(logs, windows, duration):
    sojourn = logs / "queue_sojourn.csv"
    occupancy = logs / "queue_occupancy.csv"
    events = logs / "queue_events.csv"
    cover = logs / "queue_coverage.csv"
    pending_path = logs / "queue_pending.csv"
    summary_path = logs / "queue_summary.csv"
    inputs = [path for path in (sojourn, occupancy, events, cover, pending_path, summary_path) if path.exists()]
    if not sojourn.exists():
        return inputs, {"available": False, "qualification": "No actual queue-sojourn trace; SRTT is not substituted for queue delay."}
    require(all(path.exists() for path in (occupancy, events, cover, pending_path, summary_path)),
            "Incomplete queue instrumentation")
    removed = set()
    event_counts = Counter()
    device_events = defaultdict(Counter)
    for time, row in rows(events):
        event_counts[row["event"]] += 1
        device_events[(row["node_id"], row["device_id"], row["direction"])][row["event"]] += 1
        if row["event"] == "DropAfterDequeue":
            removed.add((time, row["node_id"], row["device_id"], row["packet_uid"], row.get("tx_id", "")))
    distributions = defaultdict(Distribution)
    excluded = Counter()
    device_sojourn = defaultdict(Counter)
    for time, row in rows(sojourn, "dequeue_time_ns"):
        enqueue, value, size = int(row["enqueue_time_ns"]), int(row["sojourn_ns"]), int(row["packet_bytes"])
        require(0 <= enqueue <= time <= duration and value == time - enqueue and size > 0,
                "Queue sojourn/time contract failed")
        identity = (time, row["node_id"], row["device_id"], row["packet_uid"], row.get("tx_id", ""))
        direction = row["direction"]
        device_key = (row["node_id"], row["device_id"], direction)
        device_sojourn[device_key]["dequeued"] += 1
        device_sojourn[device_key]["zero_sojourn"] += value == 0
        fid = row.get("flow_id", "") if row.get("tagged", "") in ("1", "true") else ""
        group = "flow" + fid if fid else "untagged_or_control"
        for window in in_windows(windows, time):
            if identity in removed:
                excluded[window["window"]] += 1
            else:
                distributions[(window["window"], direction, "all")].add(value, size)
                distributions[(window["window"], direction, group)].add(value, size)
    states, areas = {}, defaultdict(lambda: [0, 0, 0])
    def integrate(key, start, end, packets, byte_count):
        for window in windows:
            overlap = max(0, min(end, window["end_ns"]) - max(start, window["start_ns"]))
            areas[(window["window"], key)][0] += packets * overlap
            areas[(window["window"], key)][1] += byte_count * overlap
            areas[(window["window"], key)][2] = max(areas[(window["window"], key)][2], packets if overlap else 0)
    for time, row in rows(occupancy):
        key = (row["node_id"], row["device_id"], row["direction"])
        old, new, byte_count = int(row["old_packets"]), int(row["new_packets"]), int(row["queue_bytes"])
        require(0 <= time <= duration and min(old, new, byte_count) >= 0, "Invalid queue occupancy")
        if key in states:
            previous_time, packets, previous_bytes = states[key]
            require(old == packets, f"Queue occupancy continuity failed: {key}")
            integrate(key, previous_time, time, packets, previous_bytes)
        else:
            require(time == 0 and old == new, f"Queue needs an initial t=0 snapshot: {key}")
        states[key] = time, new, byte_count
    for key, (time, packets, byte_count) in states.items():
        require(time == duration, f"Queue needs a final duration snapshot: {key}")
    pending_rows, pending_counts = [], Counter()
    for time, row in rows(pending_path, "observation_end_ns"):
        require(time == duration and int(row["age_ns"]) == time - int(row["enqueue_time_ns"])
                and int(row["age_ns"]) >= 0, "Pending queue age contract failed")
        key = (row["node_id"], row["device_id"], row["direction"])
        pending_counts[key] += 1
        pending_rows.append({key: number(value) if key not in ("direction",) else value
                             for key, value in row.items()})
    summaries = []
    with summary_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["node_id"], row["device_id"], row["direction"])
            require(key in states, "Queue summary device missing occupancy trace")
            item = {name: int(row[name]) for name in (
                "enqueued", "dequeued", "drop_before_enqueue", "drop_after_dequeue", "pending", "zero_sojourn")}
            require(item["enqueued"] == item["dequeued"] + item["pending"]
                    and item["pending"] == pending_counts[key] == states[key][1],
                    "Queue enqueue/dequeue/pending conservation failed")
            require(item["dequeued"] == device_sojourn[key]["dequeued"]
                    and item["zero_sojourn"] == device_sojourn[key]["zero_sojourn"],
                    "Queue summary disagrees with actual sojourn rows")
            for metric, event in (("enqueued", "Enqueue"), ("dequeued", "Dequeue"),
                                  ("drop_before_enqueue", "DropBeforeEnqueue"),
                                  ("drop_after_dequeue", "DropAfterDequeue")):
                require(item[metric] == device_events[key][event], "Queue summary/event counts differ")
            require(item["drop_after_dequeue"] == 0, "Driver DropTail service contract violated by Remove")
            summaries.append({"node_id": key[0], "device_id": key[1], "direction": key[2], **item})
    require(len(summaries) == len(states), "Queue summary is missing a device")
    queue_coverage = coverage(cover)
    require(not queue_coverage["failed_hooks"], "Queue coverage has an unconnected hook")
    for window in windows:
        name, width = window["window"], window["end_ns"] - window["start_ns"]
        window["queue_sojourn"] = [{"direction": direction, "group": group, **dist.result()}
                                    for (label, direction, group), dist in sorted(distributions.items()) if label == name]
        window["queue_removed_after_dequeue_excluded"] = excluded[name]
        window["queue_occupancy"] = [{"node_id": key[0], "device_id": key[1], "direction": key[2],
                                      "time_weighted_mean_packets": area[0] / width,
                                      "time_weighted_mean_bytes": area[1] / width,
                                      "maximum_packets_held_for_positive_time": area[2]}
                                     for (label, key), area in sorted(areas.items()) if label == name]
    return inputs, {"available": True, "event_rows_by_kind": dict(event_counts),
                    "coverage": queue_coverage, "enqueue_dequeue_pending_conservation": True,
                    "device_summaries": summaries, "pending_packets_at_stop": pending_rows,
                    "final_queue_states": [
                        {"node_id": key[0], "device_id": key[1], "direction": key[2],
                         "packets": state[1], "bytes": state[2]} for key, state in sorted(states.items())],
                    "qualification": "Sojourn is exact Enqueue-to-Dequeue waiting time, including zero waits, grouped by dequeue timestamps; excludes link serialization/propagation. Remove/DropAfterDequeue rows are excluded. Quantiles use packet counts (nearest rank), not byte or time weighting. Untagged ACK/control traffic is not assigned to a TCP flow. Occupancy holds the post-change snapshot between trace rows."}


def vegas_metrics(path, duration, allow_legacy, policy):
    if not path.exists():
        require(allow_legacy, "vegas_state.csv is required; --allow-legacy permits old screening logs")
        return {"available": False, "qualification": "Legacy run has no direct internal Vegas state observation."}
    instances, renewals, counts = {}, [], Counter()
    for time, row in rows(path, required=("vegas_instance", "event", "base_rtt_ns", "renewal_count")):
        require(0 <= time <= duration, "Vegas state trace beyond run duration")
        ident = row["vegas_instance"]
        parsed = {key: number(row.get(key)) for key in (
            "base_rtt_ns", "cycle_min_rtt_ns", "rtt_samples", "cwnd_before_bytes", "cwnd_after_bytes",
            "ssthresh_bytes", "diff_pkts", "cong_state", "renewal_enabled", "renewal_rounds",
            "renewal_count", "old_base_rtt_ns", "recent_min_ns", "history_rounds", "history_elapsed_ns")}
        parsed.update({key: number(row.get(key)) for key in (
            "valid_renewal_cycle", "ssthresh_before_bytes", "announced_state",
            "renewal_preserve_beta", "beta", "renewal_candidate_ns")})
        if policy:
            require(parsed["renewal_enabled"] == int(policy["recent_min_renewal"])
                    and parsed["renewal_rounds"] == policy["rounds"],
                    "Actual Vegas trace mode/rounds differs from launch policy")
            require(parsed["renewal_preserve_beta"] == int(policy["preserve_beta"])
                    and parsed["beta"] == policy["beta"], "Budget mode/beta mismatch")
        require(parsed["renewal_count"] is not None, "Missing Vegas renewal counter")
        prior = instances.get(ident)
        if prior is None:
            prior = {"first": {"time_ns": time, "event": row["event"], **parsed},
                     "last": None, "event_counts": Counter(), "previous_count": 0,
                     "base_rtt_min_ns": None, "base_rtt_max_ns": None}
            instances[ident] = prior
        previous_count = prior["previous_count"]
        require(previous_count <= parsed["renewal_count"] <= previous_count + 1,
                "Vegas renewal count decreased or skipped a trace-observed transition")
        event = {"time_ns": time, "vegas_instance": ident, "event": row["event"], **parsed}
        if parsed["renewal_count"] > previous_count:
            require(parsed["renewal_enabled"] == 1 and parsed["cong_state"] == 0
                    and (parsed["rtt_samples"] or 0) > 2
                    and parsed["cwnd_before_bytes"] is not None
                    and parsed["valid_renewal_cycle"] == 1
                    and parsed["ssthresh_before_bytes"] is not None
                    and parsed["cwnd_before_bytes"] >= parsed["ssthresh_before_bytes"],
                    "Renewal was recorded outside valid CA_OPEN congestion-avoidance cycle")
            require(parsed["old_base_rtt_ns"] is not None and parsed["recent_min_ns"] is not None
                    and parsed["base_rtt_ns"] <= parsed["recent_min_ns"]
                    and parsed["base_rtt_ns"] > parsed["old_base_rtt_ns"],
                    "Renewal base/history contract failed")
            require(parsed["base_rtt_ns"] == parsed["renewal_candidate_ns"], "New base differs from actual candidate")
            if not policy.get("preserve_beta"):
                require(parsed["base_rtt_ns"] == parsed["recent_min_ns"], "Ungated renewal contract failed")
            if policy:
                require(parsed["base_rtt_ns"] - parsed["old_base_rtt_ns"] >= policy["min_rise_ns"],
                        "Renewal rise is below declared policy gate")
            if parsed["history_rounds"] is not None:
                require(parsed["history_rounds"] == parsed["renewal_rounds"], "Renewal used incorrect history rounds")
            renewals.append(event)
        base = parsed["base_rtt_ns"]
        if base is not None:
            require(0 < base < (1 << 63) - 1, "Time::Max must be blank, not a measured RTT")
            prior["base_rtt_min_ns"] = min(base, prior["base_rtt_min_ns"] or base)
            prior["base_rtt_max_ns"] = max(base, prior["base_rtt_max_ns"] or base)
        prior["last"] = event
        prior["previous_count"] = parsed["renewal_count"]
        prior["event_counts"][row["event"]] += 1
        counts[row["event"]] += 1
    return {"available": True, "event_counts": dict(counts), "renewal_events": renewals,
            "renewal_count": len(renewals), "instances": instances,
            "qualification": "Actual internal state trace. Instance IDs are retained; the driver must establish that flow0 alone uses Vegas. Histories are cycle based; history_elapsed_ns is recorded rather than assumed equal to a fixed number of RTTs."}


def study_check(path, windows):
    if path is None:
        return {"available": False, "qualification": "No original analyzer JSON supplied; app/counters were independently read from raw CSV."}
    study = read_json(path)
    require(ns(study["duration_s"]) == windows[0]["end_ns"], "Original analyzer duration mismatch")
    for fid, flow in windows[0]["flows"].items():
        require(fid in study["flows"], "Original analyzer missing observed flow")
        expected = study["flows"][fid]
        require(expected["counts"].get("application_delivered_bytes", 0) == flow["application_bytes"],
                f"Original analyzer app total differs for flow{fid}")
        require(math.isclose(expected["receiver_application_goodput_mbps"], flow["application_goodput_mbps"],
                             rel_tol=1e-10, abs_tol=1e-9), "Original analyzer whole app goodput differs")
        if "receiver_application_bins" in expected:
            require(sum(item["bytes"] for item in expected["receiver_application_bins"]) == flow["application_bytes"],
                    "Original analyzer app bins differ")
    return {"available": True, "artifact": fingerprint(path), "whole_app_totals_goodput_and_available_bins_match": True,
            "qualification": "Independent raw app sums checked against supplied full analysis. Analysis source hash is separately recorded; full original JSON is not duplicated."}


def driver_check(run, windows, manifest, allow_legacy):
    """Check directly observed delay, socket class and post-Destroy app totals."""
    logs = run / "logs_ns3"
    path = run / "config_driver.json"
    if not path.exists():
        require(manifest.get("parameters", {}).get("kind") == "leo" or allow_legacy,
                "Micro run requires config_driver.json")
        return [], {"available": False, "qualification": "No synthetic driver runtime metadata (LEO or legacy screening run)."}
    config = read_json(path)
    policy = manifest.get("policy", {})
    require(config["duration_ns"] == windows[0]["end_ns"] and config["cc"] == "ns3::TcpVegas",
            "Driver duration/foreground CC mismatch")
    require(config["renewal"] == policy["recent_min_renewal"]
            and config["renewal_rounds"] == policy["rounds"]
            and config["renewal_min_rise_ns"] == policy["min_rise_ns"],
            "Actual driver configuration differs from launch renewal policy")
    paths = [path, logs / "socket_types.csv", logs / "delay_events.csv", logs / "flow_summary.csv"]
    actual_sockets = []
    for time, row in rows(paths[1]):
        require(row["expected_cc"] == row["actual_cc"], "Sender uses a different actual congestion class")
        fid = int(row["flow_id"])
        expected = "ns3::TcpVegas" if fid == 0 else "ns3::TcpCubic"
        require(row["actual_cc"] == expected, "Foreground/competitor congestion-class contract failed")
        actual_sockets.append(row)
    require({int(row["flow_id"]) for row in actual_sockets} == ({0, 1} if config["competitor"] else {0}),
            "Runtime socket verification missing/duplicated flow")
    delays = [row for time, row in rows(paths[2])]
    require(delays and int(delays[0]["new_one_way_delay_ns"]) == config["before_one_way_delay_ns"]
            and int(delays[-1]["new_one_way_delay_ns"]) == config["after_one_way_delay_ns"],
            "Actual channel delay events differ from driver config")
    for row in delays:
        require(int(row["propagation_rtt_ns"]) == 2 * int(row["new_one_way_delay_ns"]),
                "Actual propagation RTT/delay relation differs")
    flow_records = []
    with paths[3].open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            fid = str(int(row["flow_id"]))
            require(int(row["application_rx_bytes"]) == windows[0]["flows"][fid]["application_bytes"],
                    "Driver app total differs from independent original app CSV sum")
            start, end = int(row["start_ns"]), int(row["observation_end_ns"])
            expected = int(row["application_rx_bytes"]) * 8 * NS / (end - start) / 1e6
            require(math.isclose(float(row["application_goodput_mbps"]), expected, rel_tol=1e-12),
                    "Driver flow-life goodput differs from its actual active duration")
            for window in windows:
                overlap = max(0, window["end_ns"] - max(window["start_ns"], start))
                window["flows"][fid]["active_duration_ns"] = overlap
                window["flows"][fid]["active_interval_application_goodput_mbps"] = (
                    window["flows"][fid]["application_bytes"] * 8 * NS / overlap / 1e6 if overlap else None)
            flow_records.append(row)
    return paths, {"available": True, "actual_driver_config": config,
                   "actual_sender_socket_classes": actual_sockets, "actual_delay_events": delays,
                   "driver_app_totals_match_independent_csv": True, "driver_flow_life_summary": flow_records,
                   "qualification": "Matched-window app rate uses full window width; active-interval rate separately excludes time before that flow starts. Whole-run rates and whole-life rates differ for the late competitor."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="New output directory; existing paths are refused")
    parser.add_argument("--study-analysis", type=Path)
    parser.add_argument("--event-s", action="append", default=[], help="Repeat for explicit event windows; defaults to manifest event_s when present")
    parser.add_argument("--window", action="append", default=[], metavar="LABEL:START:END")
    parser.add_argument("--allow-legacy", action="store_true", help="Permit old manifests without launch commit and without Vegas state trace, explicitly qualified")
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing to overwrite output: {args.out}")
    run = args.run.resolve()
    manifest_path = run / "case.json"
    manifest = read_json(manifest_path)
    validation = manifest_validation(run, manifest, args.allow_legacy)
    duration = duration_ns(run, manifest)
    events = [ns(value) for value in args.event_s]
    if not events:
        value = (manifest.get("parameters", {}).get("event_s")
                 if manifest.get("parameters", {}).get("kind") != "leo" else None)
        if value is not None and 0 < ns(value) < duration:
            events = [ns(value)]
    windows = make_windows(duration, events, args.window)
    logs = run / "logs_ns3"
    inputs, delivery = app_and_tcp(logs, windows, duration)
    drop_coverage_path = logs / "study_drop_coverage.csv"
    drop_coverage = coverage(drop_coverage_path)
    if drop_coverage_path.exists():
        inputs.append(drop_coverage_path)
    queue_inputs, queues = queue_metrics(logs, windows, duration)
    inputs.extend(queue_inputs)
    vegas_path = logs / "vegas_state.csv"
    vegas = vegas_metrics(vegas_path, duration, args.allow_legacy, manifest.get("policy", {}))
    if vegas_path.exists():
        inputs.append(vegas_path)
    original_check = study_check(args.study_analysis, windows)
    driver_inputs, driver_validation = driver_check(run, windows, manifest, args.allow_legacy)
    inputs.extend(driver_inputs)
    inputs.append(manifest_path)
    for name in ("config_ns3.properties", "schedule.csv", "config_driver.json", "delay_events.csv"):
        if (run / name).exists():
            inputs.append(run / name)
        elif (logs / name).exists():
            inputs.append(logs / name)
    if args.study_analysis:
        inputs.append(args.study_analysis)
    study_source = Path(__file__).resolve().parents[2] / "kim-study" / "analyze_study.py"
    result = {"schema_version": 1, "case": manifest.get("case", run.name), "run": str(run),
              "duration_ns": duration, "event_times_ns": events, "windows": windows,
              "validation": validation, "application_and_terminal_validation": delivery,
              "drop_coverage": drop_coverage, "queue_instrumentation": queues,
              "driver_validation": driver_validation,
              "vegas_internal_state": vegas, "original_study_analysis_check": original_check,
              "input_artifacts": [fingerprint(path) for path in sorted(set(inputs), key=str)],
              "analysis_sources": {"helper": fingerprint(__file__),
                                   "original_analyzer_current": fingerprint(study_source) if study_source.exists() else None},
              "method": {"windows": "Exact half-open [start_ns,end_ns) on each observation's timestamp; event-time delivery belongs to post-event interval. Whole includes startup; late20/pre20/post(+10,+30) are matched between cases.",
                         "application": "Positive receiver HandleRead payload, per-connection cumulative sum checked. Connection key includes local port to distinguish two sinks each numbered connection0. Flow1 app goodput measures actual competitor delivery, not offered/sender-ACKed bytes.",
                         "loss_recovery": "Official RETX rows and bytes; CA_RECOVERY and CA_LOSS entries are separately counted. LOSS is not automatically an RTO. Drop layer rows may duplicate a physical loss, so distinct (flow,tx_id) counts are separate; untagged drops remain explicit.",
                         "terminal": "Wire payload interval union minus actual app delivery at stop time; wire Rx is pre-TCP and does not prove acceptance or eventual delivery. Sequence unwrapping assumes adjacent references differ by less than2^31 bytes.",
                         "scope": "Fixed propagation plus persistent queue is a falsification control for recent-min renewal. Increased foreground delivery alone does not establish total service improvement or fairness; examine competitor app, queue delay, drops, and terminal gap. A synthetic delay step is distinct from the multi-hop LEO model."}}
    args.out.mkdir(parents=True)
    with (args.out / "summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    columns = ["case", "window", "start_ns", "end_ns", "flow_id", "application_bytes", "application_goodput_mbps",
               "sender_payload_tx_rows", "sender_payload_tx_bytes", "official_retransmission_rows",
               "official_retransmission_bytes", "recovery_entries", "LOSS_entries", "drop_trace_rows",
               "distinct_tagged_transmissions_dropped", "application_sum_bytes", "application_sum_goodput_mbps"]
    columns += ["active_duration_ns", "active_interval_application_goodput_mbps"]
    with (args.out / "windows.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for window in windows:
            for fid, metrics in window["flows"].items():
                writer.writerow({"case": result["case"], "window": window["window"],
                                 "start_ns": window["start_ns"], "end_ns": window["end_ns"], "flow_id": fid,
                                 "application_sum_bytes": window["application_sum_bytes"],
                                 "application_sum_goodput_mbps": window["application_sum_goodput_mbps"], **metrics})
    print(json.dumps({"case": result["case"], "out": str(args.out), "windows": len(windows),
                      "flows": sorted(windows[0]["flows"]), "renewals": vegas.get("renewal_count"),
                      "whole_app_goodput_mbps": windows[0]["application_sum_goodput_mbps"],
                      "queue_sojourn_available": queues["available"], "validation": "passed"}))


if __name__ == "__main__":
    main()
