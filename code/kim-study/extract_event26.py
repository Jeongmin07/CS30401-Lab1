"""Extract reviewable evidence for the 26.2 s LEO routing event.

Uses only the standard library. The extraction is intentionally tied to the
recorded leo10-base transmission (flow 0, tx 21859, sequence 29734861).
It validates its key claims against the source CSVs instead of manufacturing
event rows. Same-time rows from separate files do not establish callback order.
"""

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path


BASE_CASE = "leo10-base"
CONTROL_CASE = "leo-delay26-base-v5"
TARGET_TX = 21859
TARGET_SEQ = 29734861
WINDOW_START = 26100000000
WINDOW_END = 26600000000
FIELDS = [
    "evidence_type", "source_case", "source_file", "source_row", "time_ns",
    "event", "flow_id", "packet_uid", "tx_id", "seq", "ack", "payload_bytes",
    "expected_seq", "sack_blocks", "old_value", "new_value", "threshold",
    "cong_state", "detail",
]


def rows(path):
    """Yield physical source line number and the original row."""
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            yield reader.line_num, row


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract(runs_root, path_truth, output):
    base_case_dir = runs_root / BASE_CASE
    base = base_case_dir / "logs_ns3"
    control_case_dir = runs_root / CONTROL_CASE
    control = control_case_dir / "logs_ns3"
    evidence = []

    def add(name, line, row, event=None, label="observed", case=BASE_CASE,
            detail=""):
        item = {key: row.get(key, "") for key in FIELDS}
        item.update(evidence_type=label, source_case=case, source_file=name,
                    source_row=line, event=event or row.get("event", ""),
                    detail=detail)
        evidence.append(item)

    snapshots = {}
    for line, row in rows(path_truth):
        time = Decimal(row["t_s"])
        if time in (Decimal("26.1"), Decimal("26.2")):
            snapshots[str(time)] = row
            add(path_truth.name, line, {"time_ns": int(time * 10**9)},
                "ROUTE_SNAPSHOT", "derived_from_state",
                detail=json.dumps(row, sort_keys=True, separators=(",", ":")))
    require(len(snapshots) == 2, "Missing 26.1/26.2 s path-truth snapshots")

    target = None
    target_retx = []
    first_covering_ack = None
    initial_sequence = None
    # These adjacent original transmissions show overtaking across the update.
    selected_tx_ids = set(range(21853, 21870)) | {21979, 21980, 21981}
    name = "tcp_flow_0_study_packets.csv"
    for line, row in rows(base / name):
        time = int(row["time_ns"])
        tx_id = int(row["tx_id"])
        if row["event"] == "TX" and int(row["flags"]) & 2:
            if initial_sequence is None:
                initial_sequence = int(row["seq"])
        if row["event"] == "TX" and tx_id == TARGET_TX:
            require(int(row["seq"]) == TARGET_SEQ, "Target tx has wrong sequence")
            target = row
        if row["event"] == "RETX" and int(row["seq"]) == TARGET_SEQ:
            target_retx.append(row)
        if row["event"] == "RX_ACK" and int(row["ack"]) >= TARGET_SEQ + 1380:
            if first_covering_ack is None:
                first_covering_ack = row
        keep = row["event"] == "TX" and tx_id in selected_tx_ids
        keep |= row["event"] == "RETX" and tx_id in {21979, 21980, 21981}
        keep |= row["event"] == "RX_ACK" and 26318000000 <= time <= 26335000000
        if keep:
            detail = "tx_time_ns=" + row["tx_time_ns"]
            if row["event"] == "RX_ACK" and row["packet_uid"] == "42007":
                detail += ";triggering SACK covers three 1380-byte segments above cumulative ACK"
            if row["event"] == "RX_ACK" and row["packet_uid"] == "42009":
                detail += ";first covering ACK for sequence29734861"
            add(name, line, row, detail=detail)
    require(target is not None, "Target original transmission missing")
    require(initial_sequence == 0, "Unexpected TCP initial sequence; acceptance mapping needs review")
    require(int(target["payload_bytes"]) == 1380, "Unexpected target payload size")
    require(len(target_retx) == 1, "Expected exactly one retransmission of target sequence")
    require(first_covering_ack is not None, "Missing covering ACK")
    retransmission_time = int(target_retx[0]["time_ns"])
    ack_time = int(first_covering_ack["time_ns"])
    require(ack_time > retransmission_time, "Covering ACK did not arrive after retransmission")

    original_receive = None
    name = "study_rx_node_1585_port_1024.csv"
    for line, row in rows(base / name):
        if row["tagged"] == "1" and int(row["tx_id"]) in range(21853, 21870):
            detail = "tx_time_ns=" + row["tx_time_ns"]
            if int(row["seq"]) > int(row["expected_seq"]):
                detail += ";payload ahead of next expected sequence"
            if int(row["tx_id"]) == TARGET_TX:
                original_receive = row
                detail += ";original target transmission reaches receiver socket"
            add(name, line, row, "RECEIVER_RX", detail=detail)
    require(original_receive is not None, "Missing receiver tag for original transmission")
    receive_time = int(original_receive["time_ns"])
    require(receive_time < retransmission_time, "Original did not arrive before retransmission")

    accepted = False
    name = "study_app_rx_node_1585_port_1024.csv"
    for line, row in rows(base / name):
        time = int(row["time_ns"])
        if 26277000000 <= time <= 26291000000:
            detail = "connection_total_rx_bytes=" + row["connection_total_rx_bytes"]
            total = int(row["connection_total_rx_bytes"])
            start = total - int(row["payload_bytes"]) + 1
            end = total + 1  # SYN uses seq0; first data byte uses seq1.
            if time == receive_time and start <= TARGET_SEQ and end >= TARGET_SEQ + 1380:
                accepted = True
                detail += (";application delivery covers original target sequence;"
                           f"delivered_sequence_interval={start}:{end};first_data_sequence=1")
            add(name, line, row, "APPLICATION_DELIVERY", detail=detail)
    require(accepted, "No same-time application acceptance covering original sequence")

    recovery_times = []
    name = "tcp_flow_0_study_events.csv"
    for line, row in rows(base / name):
        time = int(row["time_ns"])
        if 26318000000 <= time <= 26335000000:
            add(name, line, row)
        if row["event"] == "CONG" and row["new_value"] == "3":
            recovery_times.append(time)
    require(retransmission_time in recovery_times, "No same-time recovery entry")

    drop_counts = Counter()
    event_drops = []
    target_drops = []
    for _, row in rows(base / "study_drops.csv"):
        drop_counts[row["layer"]] += 1
        if WINDOW_START <= int(row["time_ns"]) <= WINDOW_END:
            event_drops.append(row)
        if row.get("flow_id") == "0" and row.get("tx_id") == str(TARGET_TX):
            target_drops.append(row)
    require(not event_drops, "Actual drop recorded in event window; loss-free claim invalid")
    require(not target_drops, "Target original transmission has drop evidence")
    coverage = [row for _, row in rows(base / "study_drop_coverage.csv")]
    require(coverage and all(row["connected"] == "1" for row in coverage),
            "Drop coverage has missing or disconnected hooks/checks")
    require(any(row["layer"] == "TcDrop" for row in coverage), "TcDrop hook missing")
    add("study_drops.csv", "", {"time_ns": WINDOW_START}, "DROP_WINDOW_AUDIT", "derived",
        detail=(f"window_ns={WINDOW_START}:{WINDOW_END};all_direction_drop_rows=0;"
                "original_tx21859_drop_rows=0;whole_run_rows_by_layer=" +
                json.dumps(dict(drop_counts), sort_keys=True, separators=(",", ":"))))
    add("study_drop_coverage.csv", "", {"time_ns": WINDOW_START},
        "DROP_HOOK_COVERAGE", "derived",
        detail=(f"all {len(coverage)} declared hooks/checks connected=1;TcDrop included;"
                "manifest alone does not independently audit every discard path"))

    control_counts = {"recovery": 0, "retx": 0, "out_of_order_payload": 0, "drop": 0}
    sources = [
        ("tcp_flow_0_study_events.csv", "recovery"),
        ("tcp_flow_0_study_packets.csv", "retx"),
        ("study_rx_node_1585_port_1024.csv", "out_of_order_payload"),
        ("study_drops.csv", "drop"),
    ]
    for name, key in sources:
        for _, row in rows(control / name):
            if not WINDOW_START <= int(row["time_ns"]) <= WINDOW_END:
                continue
            keep = key == "recovery" and row["event"] == "CONG" and row["new_value"] == "3"
            keep |= key == "retx" and row["event"] == "RETX"
            keep |= (key == "out_of_order_payload" and int(row["payload_bytes"]) > 0
                     and int(row["seq"]) > int(row["expected_seq"]))
            keep |= key == "drop"
            control_counts[key] += int(keep)
    base_meta = json.loads((base_case_dir / "case.json").read_text(encoding="utf-8"))
    control_meta = json.loads((control_case_dir / "case.json").read_text(encoding="utf-8"))
    require(base_meta["binary_sha256"] == control_meta["binary_sha256"],
            "Control and baseline use different recorded binaries")
    schedules = [hashlib.sha256((folder / "schedule.csv").read_bytes()).hexdigest()
                 for folder in (base_case_dir, control_case_dir)]
    require(schedules[0] == schedules[1], "Control and baseline schedules differ")
    add("logs_ns3 aggregate;case.json;schedule.csv", "", {"time_ns": WINDOW_START},
        "DELAYED_ROUTE_CONTROL", "derived", CONTROL_CASE,
        detail=(f"window_ns={WINDOW_START}:{WINDOW_END};" +
                json.dumps(control_counts, sort_keys=True, separators=(",", ":")) +
                ";same recorded binary hash and independently hashed schedule;"
                "control design:26.1s forwarding snapshot retained26.2-26.8s;"
                "orbits/distance continue;design independently specified in make_state_control.py"))
    add(name="tcp_flow_0_study_packets.csv", line="",
        row={"time_ns": ack_time}, event="COVERING_ACK_DELAY", label="derived",
        detail=(f"covering_ack_minus_retransmission_ns={ack_time - retransmission_time};"
                f"retransmission_minus_original_acceptance_ns={retransmission_time - receive_time}"))

    evidence.sort(key=lambda row: (int(row.get("time_ns") or 0), row["source_file"],
                                   int(row.get("source_row") or 0)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(evidence)
    return {
        "output": str(output), "rows": len(evidence),
        "original_acceptance_ns": receive_time, "recovery_retransmission_ns": retransmission_time,
        "first_covering_ack_ns": ack_time,
        "covering_ack_delay_after_retransmission_ns": ack_time - retransmission_time,
        "event_window_drop_rows": len(event_drops),
        "whole_run_drop_rows_by_layer": dict(drop_counts), "control_window": control_counts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
    parser.add_argument("--path-truth", type=Path, default=Path("/work/path_truth_200s.csv"))
    parser.add_argument("--output", type=Path, default=Path("/work/event26_evidence.csv"))
    args = parser.parse_args()
    try:
        result = extract(args.runs_root, args.path_truth, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
