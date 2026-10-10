"""Audit DD/GG terminal sequence holes from existing traces; no simulator runs.

Run in the patched official container, whose TCP/application source contracts are
checked and hashed. Wire Rx occurs before TCP processing: received ranges are not
automatically labelled accepted TCP-buffer occupancy. SACK proves a subset.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class Union:
    def __init__(self):
        self.ranges = []

    def add(self, start, end):
        require(end >= start, "Invalid sequence range")
        if start == end:
            return
        index = bisect.bisect_left(self.ranges, (start, -1))
        if index and self.ranges[index - 1][1] >= start:
            index -= 1
        stop = index
        while stop < len(self.ranges) and self.ranges[stop][0] <= end:
            start = min(start, self.ranges[stop][0])
            end = max(end, self.ranges[stop][1])
            stop += 1
        self.ranges[index:stop] = [(start, end)]

    @property
    def total(self):
        return sum(right - left for left, right in self.ranges)


def rows(path, cutoff):
    previous = -1
    with path.open(newline="", encoding="utf-8-sig") as source:
        for line, row in enumerate(csv.DictReader(source), 2):
            time = int(row["time_ns"])
            require(previous <= time < cutoff and time >= 0,
                    f"Out-of-order/out-of-window row: {path}:{line}")
            previous = time
            yield line, row


def evidence(path, line, row, fields):
    return {"file": path.name, "line": line,
            **{key: int(row[key]) if key in (
                "time_ns", "seq", "tx_id", "tx_time_ns", "payload_bytes", "threshold", "cong_state",
                "expected_seq", "connection_total_rx_bytes") else row[key]
               for key in fields}}


def source_contracts():
    root = Path("/home/ubuntu/ns-3.48")
    contracts = {
        "src/internet/model/tcp-socket-base.cc": [
            "SetNextRxSequence(tcpHeader.GetSequenceNumber() + SequenceNumber32(1));",
            "m_rxTrace(packet, tcpHeader, this);",
            "if (!m_tcb->m_rxBuffer->Add(p, tcpHeader))",
            "if (expectedSeq < m_tcb->m_rxBuffer->NextRxSequence())",
            "NotifyDataRecv();"],
        "src/network/model/socket.cc": ["m_receivedData(this);"],
        "src/internet/model/tcp-rx-buffer.cc": [
            "else if (i->first > m_nextRxSeq)",
            "m_nextRxSeq = i->first + SequenceNumber32(i->second->GetSize());"],
        "contrib/basic-sim/model/apps/tcp-flow-sink.cc": [
            "socket->GetRxBuffer()->NextRxSequence().GetValue()",
            "while ((packet = socket->RecvFrom(from)))",
            "connection.appRxBytes += packet->GetSize();"],
    }
    records = []
    for relative, fragments in contracts.items():
        path = root / relative
        require(path.is_file(), "Run this audit inside the patched official ns-3 container")
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = {}
        for fragment in fragments:
            found = [index for index, line in enumerate(lines, 1) if fragment in line]
            require(found, f"TCP/application source contract not found: {relative}: {fragment}")
            matches[fragment] = found
        records.append({"path": str(path), "sha256": digest(path), "verified_fragments": matches})
    return records


def audit_case(run, expected_mode):
    manifest = json.loads((run / "case.json").read_text())
    require(manifest["status"] == "complete" and manifest["exit_code"] == 0, "Incomplete run")
    require(manifest["parameters"]["mode"] == expected_mode, f"Expected {expected_mode} run")
    config = dict(line.split("=", 1) for line in (run / "config_ns3.properties").read_text().splitlines()
                  if "=" in line and not line.lstrip().startswith("#"))
    cutoff = int(config["simulation_end_time_ns"])
    ids = tuple(str(flow["flow_id"]) for flow in manifest["flows"])
    require(ids == ("0", "1"), "Expected exactly flow IDs 0/1")
    logs = run / "logs_ns3"
    app_paths = sorted(logs.glob("study_app_rx_node_*_port_*.csv"))
    rx_paths = sorted(logs.glob("study_rx_node_*_port_*.csv"))
    require(app_paths and rx_paths, "Receiver application and wire traces are required")
    app_bytes = {fid: 0 for fid in ids}
    app_last, connections, totals = {}, {}, {}
    app_marks = {fid: [] for fid in ids}
    app_last_time_rows = {fid: [] for fid in ids}
    for path in app_paths:
        for line, row in rows(path, cutoff):
            fid, size = row["flow_id"], int(row["payload_bytes"])
            require(fid in ids and size > 0, "Invalid receiver application identity/payload")
            key = (row["node_id"], row["local_port"], row["connection_id"])
            identity = (fid, row["peer_ip"], row["peer_port"])
            require(key not in connections or connections[key] == identity, "Connection identity changed")
            connections[key] = identity
            totals[key] = totals.get(key, 0) + size
            require(totals[key] == int(row["connection_total_rx_bytes"]), "Application connection total mismatch")
            app_bytes[fid] += size
            item = evidence(path, line, row, (
                "flow_id", "time_ns", "payload_bytes", "connection_total_rx_bytes"))
            require(not app_marks[fid] or app_marks[fid][-1][0] <= item["time_ns"],
                    "Application time order changed across trace files")
            app_marks[fid].append((item["time_ns"], app_bytes[fid] + 1))
            if fid not in app_last or app_last[fid]["time_ns"] != item["time_ns"]:
                app_last_time_rows[fid] = []
            app_last_time_rows[fid].append(item)
            app_last[fid] = item
    require(len(connections) == 2 and all(sum(v[0] == fid for v in connections.values()) == 1 for fid in ids),
            "Expected one application connection per flow")
    wire = {fid: Union() for fid in ids}
    rx_last = {}
    app_times = {fid: [time for time, _ in app_marks[fid]] for fid in ids}
    app_frontiers = {fid: [frontier for _, frontier in app_marks[fid]] for fid in ids}
    rx_validation = {fid: {"validated_payload_rows": 0, "last_timestamp_payload_rows": 0} for fid in ids}
    for path in rx_paths:
        for line, row in rows(path, cutoff):
            size = int(row["payload_bytes"])
            if not size:
                continue
            fid, seq = row["flow_id"], int(row["seq"])
            require(fid in ids and row["tagged"] == "1", "Untagged/unmapped receiver payload")
            require(0 < seq < seq + size < (1 << 31), "This audit does not support sequence wrap")
            key = (row["node_id"], row["local_port"], row["connection_id"])
            identity = (fid, row["peer_ip"], row["peer_port"])
            require(connections.get(key) == identity, "Wire/application connection identities differ")
            time, expected = int(row["time_ns"]), int(row["expected_seq"])
            earlier = bisect.bisect_left(app_times[fid], time)
            through = bisect.bisect_right(app_times[fid], time)
            before = app_frontiers[fid][earlier - 1] if earlier else 1
            after = app_frontiers[fid][through - 1] if through else 1
            # Rx is before processing; a callback may subsequently drain data
            # at the same timestamp. Bound it by the actual app history rather
            # than equating a pre-processing observation to the final frontier.
            require(before <= expected <= after, "Pre-processing receiver sequence disagrees with application history")
            if expected > before:
                index = bisect.bisect_left(app_frontiers[fid], expected, earlier, through)
                require(index < through and app_frontiers[fid][index] == expected,
                        "Receiver sequence is not an observed application frontier at this timestamp")
            previous = rx_last.get(fid)
            require(previous is None or previous["time_ns"] <= time and previous["expected_seq"] <= expected,
                    "Receiver time/expected sequence moved backwards")
            if previous is None or previous["time_ns"] != time:
                require(expected == before, "First payload at timestamp does not match prior drained application frontier")
                rx_validation[fid]["last_timestamp_payload_rows"] = 0
            rx_validation[fid]["last_timestamp_payload_rows"] += 1
            rx_validation[fid]["validated_payload_rows"] += 1
            wire[fid].add(seq, seq + size)
            rx_last[fid] = evidence(path, line, row, (
                "flow_id", "time_ns", "seq", "expected_seq", "payload_bytes", "tx_id"))
    inputs = list(app_paths) + list(rx_paths)
    result = {}
    for fid in ids:
        require(fid in rx_last and fid in app_last, "Missing receiver payload/application delivery")
        # The source increments the peer SYN sequence by one; trace checks below
        # additionally require SYN seq 0 and first payload seq 1 before using it.
        frontier = app_bytes[fid] + 1
        require(wire[fid].ranges[0][0] == 1, "Receiver did not observe first data byte seq 1")
        cursor, above, holes = frontier, [], []
        for left, right in wire[fid].ranges:
            if right <= frontier:
                continue
            left = max(left, frontier)
            if cursor < left:
                holes.append((cursor, left))
            above.append((left, right))
            cursor = right
        require(not any(left < frontier and right <= frontier and left > 1 for left, right in wire[fid].ranges),
                "Unexpected missing data below application frontier")
        prefix = wire[fid].ranges[0]
        require(prefix[0] == 1 and prefix[1] >= frontier, "Wire trace does not cover delivered sequence prefix")
        excess = sum(right - left for left, right in above)
        require(wire[fid].total - app_bytes[fid] == excess, "Wire/app frontier accounting mismatch")
        last_rx = rx_last[fid]
        require(app_last[fid]["time_ns"] <= last_rx["time_ns"], "Application delivery occurs after final receiver payload")
        last_time = last_rx["time_ns"]
        earlier = bisect.bisect_left(app_times[fid], last_time)
        before = app_frontiers[fid][earlier - 1] if earlier else 1
        same_time_apps = app_last_time_rows[fid] if app_last[fid]["time_ns"] == last_time else []
        advance = frontier - last_rx["expected_seq"]
        require(advance >= 0, "Final application frontier precedes last pre-processing receiver sequence")
        if advance:
            require(same_time_apps and last_rx["seq"] <= last_rx["expected_seq"] < last_rx["seq"] + last_rx["payload_bytes"],
                    "Final frontier advance lacks same-time application delivery and a payload covering the prior hole")
            if rx_validation[fid]["last_timestamp_payload_rows"] == 1:
                require(sum(row["payload_bytes"] for row in same_time_apps) == advance,
                        "Unique final receiver payload and same-time drained-byte advance disagree")
        terminal_observation = {
            "pre_processing_expected_seq": last_rx["expected_seq"],
            "application_frontier_before_timestamp": before,
            "application_frontier_after_timestamp": frontier,
            "final_frontier_minus_pre_processing_expected_seq": advance,
            "same_time_application_delivery_rows": same_time_apps,
            **rx_validation[fid],
            "qualification": "Wire expected_seq is before processing. Same-time app delivery can advance the final frontier; app UIDs are not joined to wire packets."}
        packet_path = logs / f"tcp_flow_{fid}_study_packets.csv"
        inputs.append(packet_path)
        syn_sequences, first_data, selected = set(), None, []
        sacks = Union()
        ack_last = None
        for line, row in rows(packet_path, cutoff):
            require(row["flow_id"] == fid, "Sender trace belongs to a different flow")
            size, seq = int(row["payload_bytes"]), int(row["seq"])
            if row["event"] == "TX" and int(row["flags"]) & 2:
                require(size == 0, "SYN-with-data unsupported")
                syn_sequences.add(seq)
            if row["event"] == "TX" and size and first_data is None:
                first_data = seq
            if row["event"] in ("TX", "RETX") and size and any(seq < right and seq + size > left for left, right in holes):
                selected.append(evidence(packet_path, line, row, (
                    "flow_id", "time_ns", "event", "seq", "payload_bytes", "tx_id", "tx_time_ns", "threshold", "cong_state")))
            if row["event"] == "RX_ACK":
                ack_last = evidence(packet_path, line, row, ("time_ns", "ack", "sack_blocks", "threshold", "cong_state"))
                for block in filter(None, row["sack_blocks"].split("|")):
                    left, right = map(int, block.split(":"))
                    if right > frontier:
                        sacks.add(max(frontier, left), right)
        require(syn_sequences == {0} and first_data == 1, "SYN seq0/data seq1 frontier assumption failed")
        require(sacks.total <= excess and all(any(a <= left and right <= b for a, b in above)
                                            for left, right in sacks.ranges), "SACK evidence outside received ranges")
        result[fid] = {"application_bytes": app_bytes[fid], "wire_unique_bytes": wire[fid].total,
                       "wire_minus_application_bytes": excess, "first_data_sequence": first_data,
                       "syn_sequences": sorted(syn_sequences), "application_sequence_frontier": frontier,
                       "last_application_delivery": app_last[fid], "last_receiver_payload": rx_last[fid],
                       "terminal_frontier_observation": terminal_observation,
                       "received_ranges_above_frontier": above, "unreceived_holes_below_highest_received_end": holes,
                       "sack_confirmed_ranges_above_frontier": sacks.ranges, "sack_confirmed_bytes_above_frontier": sacks.total,
                       "wire_bytes_above_frontier_without_sender_sack_confirmation": excess - sacks.total,
                       "last_sender_ack": ack_last, "hole_sender_evidence": selected, "hole_drop_evidence": []}
    drop_path = logs / "study_drops.csv"
    inputs.append(drop_path)
    for line, row in rows(drop_path, cutoff):
        fid = row.get("flow_id")
        if fid in result and row.get("seq") and int(row["payload_bytes"]):
            seq, size = int(row["seq"]), int(row["payload_bytes"])
            if any(seq < right and seq + size > left for left, right in result[fid]["unreceived_holes_below_highest_received_end"]):
                result[fid]["hole_drop_evidence"].append(evidence(drop_path, line, row, (
                    "flow_id", "time_ns", "layer", "node", "device", "seq", "payload_bytes", "tx_id", "tx_time_ns")))
    for fid, flow in result.items():
        verified = []
        retransmission_tags = {(row["tx_id"], row["tx_time_ns"])
                               for row in flow["hole_sender_evidence"] if row["event"] == "RETX"}
        for left, right in flow["unreceived_holes_below_highest_received_end"]:
            originals = [row for row in flow["hole_sender_evidence"]
                         if row["event"] == "TX" and (row["tx_id"], row["tx_time_ns"]) not in retransmission_tags
                         and row["seq"] <= left and right <= row["seq"] + row["payload_bytes"]]
            require(originals, "Missing original transmission for terminal hole")
            original = min(originals, key=lambda row: row["time_ns"])
            drops = [row for row in flow["hole_drop_evidence"]
                     if (row["tx_id"], row["tx_time_ns"]) == (original["tx_id"], original["tx_time_ns"])]
            require(all(row["seq"] == original["seq"] and row["payload_bytes"] == original["payload_bytes"]
                        for row in drops), "Tagged original/drop sequence or payload mismatch")
            retx = [row for row in flow["hole_sender_evidence"] if row["event"] == "RETX"
                    and row["seq"] <= left and right <= row["seq"] + row["payload_bytes"]]
            require(drops and retx, "Terminal hole needs tagged original drop and retransmission evidence")
            require(all(row["time_ns"] >= original["time_ns"] for row in drops + retx), "Invalid drop/retx chronology")
            verified.append({"sequence_range": [left, right], "original": original,
                             "original_drop_rows": drops, "retransmissions": retx,
                             "any_receiver_payload_overlap_by_cutoff": False})
        flow["verified_terminal_holes"] = verified
        del flow["hole_sender_evidence"], flow["hole_drop_evidence"]
    analysis_path = run / "study_analysis.json"
    analysis = json.loads(analysis_path.read_text())
    require(set(analysis["flows"]) == set(ids), "Existing analyzer flow IDs differ")
    for fid, flow in result.items():
        existing = analysis["flows"][fid]
        require(existing["counts"]["application_delivered_bytes"] == flow["application_bytes"], "Analyzer app bytes differ")
        rate = flow["wire_unique_bytes"] * 8 / (cutoff / 1e9) / 1e6
        require(abs(existing["wire_unique_payload_rate_mbps"] - rate) < 1e-8, "Analyzer wire union differs")
    inputs += [run / "case.json", run / "config_ns3.properties", run / "schedule.csv", analysis_path]
    return {"case": run.name, "run_dir": str(run), "cutoff_ns": cutoff,
            "source_commit": manifest["source_commit"], "binary_sha256": manifest["binary_sha256"],
            "patch_sha256": manifest["patch_sha256"], "flows": result,
            "application_bytes": sum(flow["application_bytes"] for flow in result.values()),
            "wire_unique_bytes": sum(flow["wire_unique_bytes"] for flow in result.values()),
            "raw_input_hashes": [{"path": str(path.relative_to(run)), "sha256": digest(path),
                                  "bytes": path.stat().st_size} for path in inputs]}, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--guarded", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing to overwrite {args.out}")
    contracts = source_contracts()
    base, base_manifest = audit_case(args.baseline, "DD")
    guard, guard_manifest = audit_case(args.guarded, "GG")
    require(base["cutoff_ns"] == guard["cutoff_ns"], "Different measurement cutoffs")
    for key in ("binary_sha256", "patch_sha256", "official_image_digest", "config_ns3.properties_sha256"):
        require(base_manifest[key] == guard_manifest[key], f"Control mismatch: {key}")
    for base_flow, guard_flow in zip(base_manifest["flows"], guard_manifest["flows"]):
        for key in ("flow_id", "source_node", "destination_node", "size_bytes", "start_ns"):
            require(base_flow[key] == guard_flow[key], f"Control schedule mismatch: {key}")
    require(all(flow["wire_minus_application_bytes"] == 0 for flow in base["flows"].values()),
            "This DD/GG diagnostic requires no baseline terminal wire/app excess")
    excess = sum(flow["wire_minus_application_bytes"] for flow in guard["flows"].values())
    require(excess > 0 and any(flow["verified_terminal_holes"] for flow in guard["flows"].values()),
            "Expected a guarded terminal hole in at least one flow")
    app_delta = guard["application_bytes"] - base["application_bytes"]
    wire_delta = guard["wire_unique_bytes"] - base["wire_unique_bytes"]
    require(app_delta == wire_delta - excess, "DD/GG terminal accounting identity failed")
    result = {"schema_version": 2, "source_contracts": contracts, "baseline": base, "guarded": guard,
              "accounting": {"guarded_minus_baseline_application_bytes": app_delta,
                             "guarded_minus_baseline_wire_unique_bytes": wire_delta,
                             "guarded_wire_above_unresolved_frontiers_bytes": excess,
                             "identity_verified": "application_delta = wire_delta - guarded_wire_above_frontiers"},
              "limitations": [
                  "Wire Rx is emitted before TCP processing; wire-union excess is not an exact accepted-buffer measurement.",
                  "SACK confirms only the reported subset; late receiver arrivals may not have sender feedback by cutoff.",
                  "Application frontier assumes verified SYN seq0/data seq1, one connection per flow and no sequence wrap.",
                  "Pre-processing receiver expected_seq is checked against drained application history; it need not equal the final frontier when that payload produces same-time app delivery.",
                  "Terminal holes have tagged original drops and retransmission attempts, with no receiver payload overlap before cutoff.",
                  "No observed arrival by cutoff does not prove a retransmission was lost or would never arrive.",
                  "The accounting explains this deadline-specific application deficit, not all earlier trajectory differences or long-run superiority.",
                  "Guard had ended earlier; late loss recovery uses K3. Earlier guard causation of the eventual queue history is not isolated.",
                  "No simulator execution, duration extension, drain control or independent statistical replication is performed."],
              "audit_script_sha256": digest(__file__)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), **result["accounting"],
                      "per_flow_wire_excess": {fid: flow["wire_minus_application_bytes"] for fid, flow in guard["flows"].items()}}))


if __name__ == "__main__":
    main()
