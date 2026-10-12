"""Analyze the independent CS30401 study traces using the Python standard library.

No cwnd-only causal inference is made. Receiver application delivery is goodput;
wire payload union is reported separately. Exact transmission tags distinguish
an original segment from another transmission of the same sequence range.

Example:
  python analyze_study.py RUN --path-truth path_truth_200s.csv --output summary.json

The default writes JSON to stdout. --output is an explicit output destination.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import heapq
import json
import math
from pathlib import Path
from typing import Iterable

SEQ_MOD = 1 << 32
STATE_NAMES = {0: "OPEN", 1: "DISORDER", 2: "CWR", 3: "RECOVERY", 4: "LOSS"}


def integer(value, default=None):
    return default if value in (None, "") else int(value)


def unwrap(value: int, reference: int | None) -> int:
    """Choose the serial-number epoch nearest an established sequence reference."""
    if reference is None:
        return value
    return value + round((reference - value) / SEQ_MOD) * SEQ_MOD


class Intervals:
    """A sorted union of half-open byte ranges, normally one contiguous interval."""

    def __init__(self):
        self.ranges = []
        self.total = 0

    def add(self, start: int, end: int) -> int:
        if end <= start:
            return 0
        ranges = self.ranges
        index = bisect.bisect_left(ranges, (start, -math.inf))
        if index and ranges[index - 1][1] >= start:
            index -= 1
        stop = index
        merged_start, merged_end = start, end
        removed = 0
        overlap = 0
        while stop < len(ranges) and ranges[stop][0] <= merged_end:
            left, right = ranges[stop]
            overlap += max(0, min(end, right) - max(start, left))
            merged_start = min(merged_start, left)
            merged_end = max(merged_end, right)
            removed += right - left
            stop += 1
        ranges[index:stop] = [(merged_start, merged_end)]
        self.total += merged_end - merged_start - removed
        return end - start - overlap


def read_rows(path: Path):
    previous = -1
    with path.open(newline="", encoding="utf-8-sig") as source:
        for line_number, row in enumerate(csv.DictReader(source), 2):
            time = integer(row.get("time_ns"))
            if time is None:
                raise ValueError(f"Missing time_ns: {path}:{line_number}")
            if time < previous:
                raise ValueError(f"Trace is not chronological: {path}:{line_number}")
            previous = time
            yield time, row


def merged_rows(sources: Iterable[tuple[str, Path]]):
    heap = []
    for index, (kind, path) in enumerate(sources):
        iterator = iter(read_rows(path))
        first = next(iterator, None)
        if first is not None:
            heapq.heappush(heap, (first[0], index, 0, kind, first[1], iterator))
    while heap:
        time, index, order, kind, row, iterator = heapq.heappop(heap)
        yield time, kind, row
        following = next(iterator, None)
        if following is not None:
            heapq.heappush(heap, (following[0], index, order + 1, kind,
                                  following[1], iterator))


def read_duration(run: Path, override: float | None) -> float:
    if override is not None:
        return override
    for line in (run / "config_ns3.properties").read_text().splitlines():
        if line.strip().startswith("simulation_end_time_ns="):
            return int(line.split("=", 1)[1]) / 1e9
    raise ValueError("Set --duration-s or provide simulation_end_time_ns in config.")


def read_path_events(path: Path | None, before: float, after: float, duration: float):
    if path is None:
        return []
    events = []
    with path.open(newline="", encoding="utf-8-sig") as source:
        previous = None
        for row in csv.DictReader(source):
            if previous and integer(row.get("path_changed"), 0):
                time = float(row["t_s"])
                if not 0 <= time < duration:
                    previous = row
                    continue
                old_rtt = float(previous["rtt_prop_ms"]) if previous["rtt_prop_ms"] else None
                new_rtt = float(row["rtt_prop_ms"]) if row["rtt_prop_ms"] else None
                events.append({"time_s": time,
                               "rtt_change_ms": None if old_rtt is None or new_rtt is None
                               else round(new_rtt - old_rtt, 6),
                               "forward_path_changed": row["path_fwd"] != previous["path_fwd"],
                               "window_start_s": max(0.0, time - before),
                               "window_end_s": min(duration, time + after),
                               "flows": {}})
            previous = row
    return events


def flow_data():
    return {"counts": collections.Counter(), "tx_union": Intervals(),
            "rx_union": Intervals(), "tx_reference": None, "rx_reference": None,
            "last_ack": None, "last_ack_ns": None, "ack_run": 0,
            "last_sack": "", "gaps": [], "active_gap": None,
            "state": 0, "recovery_start_ns": None, "recoveries": [],
            "retransmissions": [], "state_entries": [],
            "drops": [], "guard_start_ns": None, "guard_intervals": [],
            "guard_deferrals": 0, "guard_deadlines_missed": 0,
            "initial_threshold": None,
            "first_app_ns": None, "last_app_ns": None,
            "app_bins": collections.Counter()}


def sample_drop_rows(rows, limit):
    """Keep examples from every observed drop layer, then fill chronologically."""
    if limit <= 0:
        return []
    first_by_layer = {}
    for index, row in enumerate(rows):
        first_by_layer.setdefault(row["layer"], index)
    chosen = set(list(first_by_layer.values())[:limit])
    for index in range(len(rows)):
        if len(chosen) >= limit:
            break
        chosen.add(index)
    return [rows[index] for index in sorted(chosen)]


def smoothed_rtt_summary(path: Path, duration: float):
    """Time-weighted SRTT, not a quantile over irregular trace rows or packet RTT."""
    weights = collections.Counter()
    previous = None
    rows = 0
    duration_ns = int(duration * 1e9)
    with path.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.reader(source):
            time, value = int(row[1]), int(row[2])
            rows += 1
            if previous is not None:
                old_time, old_value = previous
                weight = max(0, min(time, duration_ns) - max(0, old_time))
                if old_value > 0 and weight:
                    weights[old_value] += weight
            previous = time, value
    if previous is not None and previous[1] > 0:
        final_weight = max(0, duration_ns - max(0, previous[0]))
        if final_weight:
            weights[previous[1]] += final_weight
    total = sum(weights.values())
    if not total:
        return {"trace_rows": rows, "covered_duration_s": 0.0}
    ordered = sorted(weights.items())
    quantiles = {}
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        for name, fraction in (("p50_ms", 0.5), ("p95_ms", 0.95), ("p99_ms", 0.99)):
            if name not in quantiles and cumulative >= fraction * total:
                quantiles[name] = value / 1e6
    return {"trace_rows": rows, "covered_duration_s": total / 1e9,
            "time_weighted_mean_ms": sum(value * weight for value, weight in weights.items()) / total / 1e6,
            "minimum_ms": ordered[0][0] / 1e6, "maximum_ms": ordered[-1][0] / 1e6,
            **quantiles,
            "qualification": "Smoothed sender RTT held between trace changes; excludes initial unknown/zero SRTT; not raw packet RTT or isolated queueing delay."}


def coverage_summary(paths):
    if not paths:
        return {"available": False, "connected": 0, "not_connected": [],
                "absence_of_drop_inference": "unsupported without coverage"}
    count = 0
    failed = []
    layers = collections.Counter()
    node_sets = collections.defaultdict(set)
    device_sets = collections.defaultdict(set)
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                layers[row.get("layer", "unknown")] += 1
                node_sets[row.get("layer", "unknown").lower()].add(row.get("node", "unknown"))
                device_sets[row.get("layer", "unknown").lower()].add((row.get("node", "unknown"),
                                                                       row.get("device", "unknown")))
                if row.get("connected", "").lower() in ("1", "true", "yes"):
                    count += 1
                else:
                    failed.append(row)
    tc_nodes = set().union(*(nodes for layer, nodes in node_sets.items()
                            if layer in ("tcdrop", "tc", "trafficcontrol")))
    ipv4_nodes = set().union(*(nodes for layer, nodes in node_sets.items()
                              if layer in ("ipv4", "ipv4l3drop")))
    tc_complete = bool(ipv4_nodes and ipv4_nodes <= tc_nodes)
    required_devices = device_sets.get("mactxdrop", set())
    qdisc_absence_devices = device_sets.get("root_queue_disc_absent", set())
    qdisc_complete = bool(required_devices and required_devices <= qdisc_absence_devices)
    return {"available": True, "connected": count, "not_connected": failed,
            "layer_entries": dict(layers),
            "traffic_control_drop_hook_present": any(layer.lower() in ("tcdrop", "tc", "trafficcontrol")
                                                     for layer in layers),
            "traffic_control_node_coverage_complete": tc_complete,
            "root_queue_disc_absence_coverage_complete": qdisc_complete,
            "devices_without_root_queue_disc_absence_check_count": len(required_devices - qdisc_absence_devices),
            "devices_without_root_queue_disc_absence_check": [list(item) for item in
                                                               sorted(required_devices - qdisc_absence_devices)[:20]],
            "ipv4_nodes_without_traffic_control_drop_hook": sorted(ipv4_nodes - tc_nodes),
            "absence_of_drop_inference": "listed hooks connected with matching IPv4/TcDrop node coverage"
            if not failed and tc_complete and qdisc_complete else
            "unsupported: missing hooks, TcDrop coverage or root queue-disc absence verification",
            "qualification": "Manifest coverage is not an independent audit of every loss path."}


def analyze(args):
    run = Path(args.run)
    duration = read_duration(run, args.duration_s)
    if duration <= 0 or args.bin_s <= 0:
        raise ValueError("Duration and bin size must be positive.")
    logs = run / "logs_ns3" if (run / "logs_ns3").is_dir() else run
    patterns = [("sender", "tcp_flow_*_study_packets.csv"),
                ("drop", "study_drops.csv"),
                ("receiver", "study_rx_node_*_port_*.csv"),
                ("app", "study_app_rx_node_*_port_*.csv"),
                ("state", "tcp_flow_*_study_events.csv")]
    sources = [(kind, path) for kind, pattern in patterns for path in sorted(logs.rglob(pattern))]
    if not sources and not args.allow_legacy:
        raise ValueError("No study trace files found; --allow-legacy permits ACK-only summary.")
    events = read_path_events(Path(args.path_truth) if args.path_truth else None,
                            args.before_s, args.after_s, duration)
    for marker in args.events:
        if not 0 <= marker < duration:
            continue
        events.append({"time_s": marker, "rtt_change_ms": None,
                       "forward_path_changed": None, "marker_source": "explicit",
                       "window_start_s": max(0.0, marker - args.before_s),
                       "window_end_s": min(duration, marker + args.after_s), "flows": {}})
    if any(event["window_start_s"] >= event["window_end_s"] for event in events):
        raise ValueError("A clipped event window has zero duration.")
    events.sort(key=lambda event: event["time_s"])
    coverage = coverage_summary(sorted(logs.rglob("study_drop_coverage.csv")))
    flows = collections.defaultdict(flow_data)
    global_counts = collections.Counter()
    drop_layers = collections.Counter()
    tx_records = collections.OrderedDict()
    dropped_tags = set()
    connections = {}
    dropped_unknown = 0
    retention_ns = int(args.tx_retention_s * 1e9)

    def bump(flow_id, name, amount, time):
        flows[flow_id]["counts"][name] += amount
        for event in events:
            if event["window_start_s"] * 1e9 <= time < event["window_end_s"] * 1e9:
                counter = event["flows"].setdefault(str(flow_id), collections.Counter())
                counter[name] += amount

    def connection_key(row):
        return (row.get("node_id"), row.get("connection_id"))

    def add_gap_evidence(flow, sequence, name, item):
        for gap in reversed(flow["gaps"]):
            if gap["start_ns"] < item["time_ns"] - retention_ns:
                break
            if sequence is None or sequence == gap["missing_sequence"]:
                gap[name].append(item)

    def confirm_gap(flow, time, proof):
        gap = flow["active_gap"]
        if gap is None:
            return
        candidate = gap["fill_candidates"][-1] if gap["fill_candidates"] else None
        gap["end_ns"] = candidate["time_ns"] if candidate else time
        gap["acceptance_observed_ns"] = time
        gap["acceptance_evidence"] = proof
        gap["fill_tx_id"] = candidate["tx_id"] if candidate else None
        gap["original_fill_confirmed"] = bool(candidate and candidate["original"])
        gap["fill_tag_cache_miss"] = candidate is None or candidate["tag_cache_miss"]
        flow["active_gap"] = None

    for time, kind, row in merged_rows(sources):
        global_counts[f"{kind}_rows"] += 1
        while tx_records:
            first_key = next(iter(tx_records))
            if tx_records[first_key]["time_ns"] >= time - retention_ns:
                break
            tx_records.popitem(last=False)
        fid = integer(row.get("flow_id"))
        if kind in ("receiver", "app"):
            key = connection_key(row)
            if fid is not None:
                connections[key] = fid
            else:
                fid = connections.get(key)
        if fid is None:
            global_counts[f"unmapped_{kind}_rows"] += 1
        payload = integer(row.get("payload_bytes"), 0)

        if kind == "drop":
            drop_layers[row.get("layer", "unknown")] += 1
            tag = integer(row.get("tx_id"))
            if fid is None or tag is None or tag <= 0:
                dropped_unknown += 1
            else:
                dropped_tags.add((fid, tag))
            if fid is not None:
                bump(fid, "drop_trace_rows", 1, time)
                if payload and row.get("seq"):
                    flow = flows[fid]
                    seq = unwrap(int(row["seq"]), flow["tx_reference"])
                    flow["drops"].append({"time_ns": time, "seq": seq,
                                          "end_seq": seq + payload, "tx_id": tag,
                                          "layer": row.get("layer"), "reason": row.get("reason")})
            continue
        if fid is None:
            continue
        flow = flows[fid]
        if kind == "app":
            bump(fid, "application_delivered_bytes", payload, time)
            flow["app_bins"][int(time / (args.bin_s * 1e9))] += payload
            if payload:
                if flow["first_app_ns"] is None:
                    flow["first_app_ns"] = time
                flow["last_app_ns"] = time
            gap = flow["active_gap"]
            if payload and gap and gap["fill_candidates"] and gap["fill_candidates"][-1]["time_ns"] == time:
                confirm_gap(flow, time, "same-time receiver application delivery after wire fill")
            continue
        if kind == "sender":
            event_kind = row.get("event", "").upper()
            if event_kind == "RX_ACK":
                ack = unwrap(integer(row.get("ack"), 0), flow["tx_reference"])
                flow["ack_run"] = flow["ack_run"] + 1 if ack == flow["last_ack"] else 0
                if flow["ack_run"]:
                    bump(fid, "repeated_cumulative_ack_rows", 1, time)
                if row.get("sack_blocks"):
                    bump(fid, "ack_rows_with_sack", 1, time)
                flow["last_ack"], flow["last_ack_ns"] = ack, time
                flow["last_sack"] = row.get("sack_blocks", "")
                add_gap_evidence(flow, ack, "ack_evidence",
                                 {"time_ns": time, "ack": ack,
                                  "repeated_ack_run": flow["ack_run"],
                                  "sack_blocks": flow["last_sack"]})
            elif event_kind in ("TX", "RETX") and payload:
                seq = unwrap(integer(row.get("seq"), 0), flow["tx_reference"])
                flow["tx_reference"] = max(flow["tx_reference"] or seq, seq + payload)
                tag = integer(row.get("tx_id"))
                record_key = (fid, tag)
                if event_kind == "TX":
                    unique = flow["tx_union"].add(seq, seq + payload)
                    bump(fid, "sender_payload_tx_bytes", payload, time)
                    bump(fid, "sender_new_sequence_bytes", unique, time)
                    record = {"time_ns": time, "seq": seq, "end_seq": seq + payload,
                              "original": unique == payload, "official_retx": False}
                    if tag is not None and tag > 0:
                        tx_records[record_key] = record
                    if unique < payload:
                        bump(fid, "overlapping_sequence_tx_rows", 1, time)
                else:
                    bump(fid, "official_retransmission_rows", 1, time)
                    if record_key in tx_records:
                        tx_records[record_key]["official_retx"] = True
                    item = {"time_ns": time, "tx_id": tag, "seq": seq,
                            "end_seq": seq + payload}
                    flow["retransmissions"].append(item)
                    add_gap_evidence(flow, seq, "retransmission_evidence", item)
            continue
        if kind == "receiver" and payload:
            seq = unwrap(integer(row.get("seq"), 0), flow["rx_reference"])
            expected = unwrap(integer(row.get("expected_seq"), seq), seq)
            flow["rx_reference"] = max(flow["rx_reference"] or seq, seq + payload)
            gap = flow["active_gap"]
            if gap and expected > gap["missing_sequence"]:
                confirm_gap(flow, time, "subsequent pre-processing expected_seq advanced")
            novel = flow["rx_union"].add(seq, seq + payload)
            bump(fid, "wire_payload_rx_bytes", payload, time)
            bump(fid, "wire_unique_sequence_bytes", novel, time)
            if seq > expected:
                bump(fid, "out_of_order_payload_rows", 1, time)
                if flow["active_gap"] is None or flow["active_gap"]["missing_sequence"] != expected:
                    gap = {"start_ns": time, "missing_sequence": expected,
                           "first_ahead_sequence": seq, "end_ns": None,
                           "ack_evidence": [], "retransmission_evidence": [],
                           "recovery_evidence": [], "fill_tx_id": None,
                           "fill_candidates": [], "acceptance_evidence": None,
                           "original_fill_confirmed": False, "fill_tag_cache_miss": False}
                    flow["gaps"].append(gap)
                    flow["active_gap"] = gap
            gap = flow["active_gap"]
            if gap and seq <= gap["missing_sequence"] < seq + payload:
                tag = integer(row.get("tx_id"))
                record = tx_records.get((fid, tag))
                gap["fill_candidates"].append({"time_ns": time, "tx_id": tag,
                                               "tag_cache_miss": record is None,
                                               "original": bool(record and record["original"]
                                                                and not record["official_retx"])})
            continue
        if kind == "state":
            event_kind = row.get("event", "").upper()
            if event_kind == "CONG":
                old = integer(row.get("old_value"), flow["state"])
                new = integer(row.get("new_value"), flow["state"])
                flow["state"] = new
                if new in (3, 4) and old != new:
                    bump(fid, "recovery_state_entries" if new == 3 else "loss_state_entries", 1, time)
                    item = {"time_ns": time, "state": STATE_NAMES.get(new, str(new)),
                            "preceding_ack": flow["last_ack"],
                            "repeated_ack_run": flow["ack_run"],
                            "sack_blocks": flow["last_sack"]}
                    flow["state_entries"].append(item)
                    add_gap_evidence(flow, flow["last_ack"], "recovery_evidence", item)
                    if flow["recovery_start_ns"] is None:
                        flow["recovery_start_ns"] = time
                if new == 0 and flow["recovery_start_ns"] is not None:
                    flow["recoveries"].append({"start_ns": flow["recovery_start_ns"],
                                               "end_ns": time,
                                               "duration_s": (time - flow["recovery_start_ns"]) / 1e9})
                    flow["recovery_start_ns"] = None
            elif event_kind == "THRESHOLD_SET":
                flow["guard_start_ns"] = time
            elif event_kind == "THRESHOLD_INIT":
                flow["initial_threshold"] = integer(row.get("new_value"))
            elif event_kind == "THRESHOLD_RESTORE" and flow["guard_start_ns"] is not None:
                flow["guard_intervals"].append({"start_ns": flow["guard_start_ns"],
                                                "end_ns": time,
                                                "duration_s": (time - flow["guard_start_ns"]) / 1e9})
                flow["guard_start_ns"] = None
            elif event_kind == "THRESHOLD_RESTORE_DEFERRED":
                flow["guard_deferrals"] += 1
            elif event_kind == "RESTORE_DEADLINE_MISSED":
                flow["guard_deadlines_missed"] += 1

    summaries = {}
    drop_exclusion_supported = (coverage["available"] and not coverage["not_connected"]
                                and coverage.get("traffic_control_node_coverage_complete", False)
                                and (coverage.get("root_queue_disc_absence_coverage_complete", False)
                                     or args.root_qdisc_absence_audited)
                                and dropped_unknown == 0)
    for fid, flow in sorted(flows.items()):
        counts = dict(flow["counts"])
        case_counts = collections.Counter()
        cases = []
        for gap in flow["gaps"]:
            drops = [drop for drop in flow["drops"]
                     if drop["seq"] <= gap["missing_sequence"] < drop["end_seq"]
                     and gap["start_ns"] - retention_ns <= drop["time_ns"]
                     <= (gap["end_ns"] or int(duration * 1e9)) + retention_ns]
            gap["observed_drop_rows_for_missing_sequence"] = len(drops)
            gap["observed_distinct_drop_tx_ids"] = sorted({drop["tx_id"] for drop in drops
                                                           if drop["tx_id"] is not None})
            gap["network_loss_exclusion_supported"] = bool(drop_exclusion_supported and not drops)
            fill_dropped = (fid, gap["fill_tx_id"]) in dropped_tags
            if gap["original_fill_confirmed"] and not fill_dropped:
                classification = "original_eventually_arrived_after_reordering"
                if gap["recovery_evidence"] and gap["retransmission_evidence"]:
                    classification = ("candidate_unnecessary_recovery_original_arrived"
                                      if gap["network_loss_exclusion_supported"] else
                                      "original_arrived_with_recovery_incomplete_drop_coverage")
            elif drops:
                classification = "gap_with_observed_actual_drop"
            else:
                classification = "unresolved_or_ambiguous_gap"
            gap["classification"] = classification
            if gap["original_fill_confirmed"] and gap["retransmission_evidence"]:
                case_counts["accepted_original_also_retransmitted_gaps"] += 1
                if gap["network_loss_exclusion_supported"]:
                    case_counts["loss_excluded_original_also_retransmitted_gaps"] += 1
            gap["drop_evidence_for_original_fill"] = fill_dropped
            gap["duration_s"] = None if gap["end_ns"] is None else (gap["end_ns"] - gap["start_ns"]) / 1e9
            for event in events:
                if event["window_start_s"] * 1e9 <= gap["start_ns"] < event["window_end_s"] * 1e9:
                    counter = event["flows"].setdefault(str(fid), collections.Counter())
                    counter[classification] += 1
            case_counts[classification] += 1
            if len(cases) < args.max_cases:
                sample = dict(gap)
                for key in ("ack_evidence", "retransmission_evidence", "recovery_evidence"):
                    sample[key] = gap[key][:args.max_evidence_rows]
                    sample[key + "_count"] = len(gap[key])
                cases.append(sample)
            for event in events:
                if event["window_start_s"] * 1e9 <= gap["start_ns"] < event["window_end_s"] * 1e9:
                    samples = event.setdefault("gap_case_samples", {}).setdefault(str(fid), [])
                    if len(samples) < args.max_cases:
                        sample = dict(gap)
                        for key in ("ack_evidence", "retransmission_evidence", "recovery_evidence"):
                            sample[key] = gap[key][:args.max_evidence_rows]
                            sample[key + "_count"] = len(gap[key])
                        samples.append(sample)
        dropped_flow_tags = {tag for flow_id, tag in dropped_tags if flow_id == fid}
        drop_cases = []
        # Drop hooks can report the same loss multiple times. Keep per-tag rows together.
        by_sequence = collections.defaultdict(list)
        for gap in flow["gaps"]:
            by_sequence[gap["missing_sequence"]].append(gap)
        for drop in sample_drop_rows(flow["drops"], args.max_cases):
            later = [gap for gap in by_sequence.get(drop["seq"], [])
                     if gap["end_ns"] is not None and gap["end_ns"] >= drop["time_ns"]]
            resolved = min(later, key=lambda gap: gap["end_ns"], default=None)
            retransmitted = min((tx for tx in flow["retransmissions"]
                                 if tx["seq"] <= drop["seq"] < tx["end_seq"]
                                 and tx["time_ns"] >= drop["time_ns"]),
                                key=lambda tx: tx["time_ns"], default=None)
            recovery = min((entry for entry in flow["state_entries"]
                            if entry["preceding_ack"] == drop["seq"] and entry["time_ns"] >= drop["time_ns"]),
                           key=lambda entry: entry["time_ns"], default=None)
            item = dict(drop)
            item["gap_resolution_delay_s"] = None if resolved is None else (resolved["end_ns"] - drop["time_ns"]) / 1e9
            item["first_matching_retransmission"] = retransmitted
            item["first_matching_recovery_state"] = recovery
            item["retransmission_delay_s"] = None if retransmitted is None else (retransmitted["time_ns"] - drop["time_ns"]) / 1e9
            item["accepted_fill_tx_id"] = resolved["fill_tx_id"] if resolved else None
            item["accepted_fill_is_matching_retransmission"] = bool(resolved and retransmitted
                                                                     and resolved["fill_tx_id"] == retransmitted["tx_id"])
            item["qualification"] = "Sequence-gap resolution, not proof that a particular retransmission repaired this drop."
            drop_cases.append(item)
        summary = {"counts": counts,
                   "receiver_application_goodput_mbps": round(counts.get("application_delivered_bytes", 0) * 8 / duration / 1e6, 9)
                   if global_counts["app_rows"] else None,
                   "first_receiver_application_delivery_time_s": None if flow["first_app_ns"] is None else flow["first_app_ns"] / 1e9,
                   "last_receiver_application_delivery_time_s": None if flow["last_app_ns"] is None else flow["last_app_ns"] / 1e9,
                   "wire_unique_payload_rate_mbps": round(flow["rx_union"].total * 8 / duration / 1e6, 9)
                   if global_counts["receiver_rows"] else None,
                   "distinct_tagged_transmissions_dropped": len(dropped_flow_tags),
                   "gap_classifications": dict(case_counts), "gap_case_samples": cases,
                   "gap_cases_total": len(flow["gaps"]),
                   "gap_case_samples_truncated": len(flow["gaps"]) > len(cases),
                   "drop_case_samples": drop_cases, "recovery_periods": flow["recoveries"],
                   "drop_trace_row_cases_total": len(flow["drops"]),
                   "drop_case_samples_truncated": len(flow["drops"]) > len(drop_cases),
                   "drop_sample_selection": "First example per observed drop layer, then chronological rows to sample cap.",
                   "unfinished_recovery_start_ns": flow["recovery_start_ns"],
                   "protection_intervals": flow["guard_intervals"],
                   "unfinished_protection_start_ns": flow["guard_start_ns"],
                   "restore_deferrals": flow["guard_deferrals"],
                   "restore_deadlines_missed": flow["guard_deadlines_missed"],
                   "initial_retransmission_threshold": flow["initial_threshold"],
                   "resolved_gap_tag_cache_misses": sum(gap["fill_tag_cache_miss"] for gap in flow["gaps"]
                                                          if gap["end_ns"] is not None)}
        if args.include_bins:
            summary["receiver_application_bins"] = [
                {"start_s": index * args.bin_s, "end_s": min(duration, (index + 1) * args.bin_s),
                 "bytes": flow["app_bins"].get(index, 0),
                 "goodput_mbps": flow["app_bins"].get(index, 0) * 8 /
                 (min(duration, (index + 1) * args.bin_s) - index * args.bin_s) / 1e6}
                for index in range(math.ceil(duration / args.bin_s))]
        rtt_path = logs / f"tcp_flow_{fid}_rtt.csv"
        if rtt_path.exists():
            summary["smoothed_rtt"] = smoothed_rtt_summary(rtt_path, duration)
        summaries[str(fid)] = summary
    for event in events:
        width = event["window_end_s"] - event["window_start_s"]
        for fid, counter in event["flows"].items():
            counter["receiver_application_goodput_mbps"] = counter.get("application_delivered_bytes", 0) * 8 / width / 1e6
    legacy = {}
    if args.allow_legacy:
        for path in sorted(logs.glob("tcp_flow_*_progress.csv")):
            last = None
            with path.open(newline="", encoding="utf-8-sig") as source:
                for row in csv.reader(source):
                    last = row
            if last is not None:
                legacy[last[0]] = {"last_sender_acknowledged_bytes": int(last[2]),
                                    "sender_ack_rate_over_whole_run_mbps": int(last[2]) * 8 / duration / 1e6,
                                    "last_progress_time_s": int(last[1]) / 1e9,
                                    "qualification": "Sender acknowledged progress; not receiver-measured application goodput."}
    return {"schema_version": 1, "run": run.name, "duration_s": duration,
            "analysis_parameters": {"event_before_s": args.before_s, "event_after_s": args.after_s,
                                    "bin_s": args.bin_s, "tx_identity_retention_s": args.tx_retention_s,
                                    "root_queue_disc_absence_independently_audited": args.root_qdisc_absence_audited,
                                    "maximum_case_samples": args.max_cases,
                                    "maximum_evidence_rows_per_sample": args.max_evidence_rows},
            "legacy_sender_ack_summary": legacy,
            "inputs": [{"kind": kind, "path": str(path)} for kind, path in sources],
            "trace_rows": dict(global_counts), "drop_rows_by_layer": dict(drop_layers),
            "drop_rows_without_usable_transmission_tag": dropped_unknown,
            "drop_coverage": coverage, "flows": summaries, "path_event_windows": events,
            "limitations": [
                "Path-truth propagation RTT includes both directions; RTT decreases alone do not prove forward-path overtaking.",
                "Repeated cumulative ACKs are observations, not an independent reconstruction of every duplicate-ACK predicate.",
                "Exact tx_id tags, not packet UIDs, identify transmission instances; joins are retained for a bounded time.",
                "Candidate unnecessary recovery associates a sequence gap, ACK evidence, retransmission and eventual original delivery; controlled comparisons are still needed for a causal performance claim.",
                "LOSS state is reported directly and is not automatically called an RTO without a dedicated timer trace.",
                "Drop trace rows can duplicate one physical loss; distinct tagged transmission counts and per-layer counts are separate.",
                "No observed drop is not proof of no drop when coverage or packet parsing is incomplete.",
                "Traffic-control TcDrop coverage is required before excluding network loss; pre-v3 coverage can omit this path.",
                "Root queue-disc absence must be verified per device or explicitly independently audited; TcDrop does not observe a root queue-disc's own losses.",
                "Receiver TCP window rejection and PAWS/input discards are not covered by queue/IP/device/traffic-control hooks.",
                "Pre-processing wire Rx does not prove acceptance: a gap fill requires subsequent expected_seq advancement or same-time application delivery.",
                "Application HandleRead bytes are ordered unique delivery; wire interval union is a separate metric.",
                "Sequence epochs assume adjacent relevant sequence references differ by less than 2^31 bytes.",
                "Static and dynamic path controls, actual loss tests and deployment-information errors remain separate experimental requirements."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--path-truth")
    parser.add_argument("--events", type=float, nargs="*", default=[],
                        help="Explicit event times in seconds, e.g. --events 10.")
    parser.add_argument("--duration-s", type=float)
    parser.add_argument("--before-s", type=float, default=0.5)
    parser.add_argument("--after-s", type=float, default=2.0)
    parser.add_argument("--bin-s", type=float, default=0.1)
    parser.add_argument("--tx-retention-s", type=float, default=10.0)
    parser.add_argument("--max-cases", type=int, default=100)
    parser.add_argument("--max-evidence-rows", type=int, default=12)
    parser.add_argument("--include-bins", action="store_true")
    parser.add_argument("--allow-legacy", action="store_true",
                        help="Permit uninstrumented ACK-progress summary, explicitly not receiver goodput.")
    parser.add_argument("--root-qdisc-absence-audited", action="store_true",
                        help="Use only after an independent source/runtime audit proves root queue discs absent.")
    parser.add_argument("--output", help="Write JSON here instead of stdout.")
    args = parser.parse_args()
    if args.before_s < 0 or args.after_s < 0 or args.before_s + args.after_s == 0:
        parser.error("Event windows must have positive total width and nonnegative sides.")
    if args.tx_retention_s <= 0:
        parser.error("--tx-retention-s must be positive.")
    result = json.dumps(analyze(args), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(args.output)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
