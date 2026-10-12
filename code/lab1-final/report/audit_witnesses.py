#!/usr/bin/env python3
"""Post-simulation packet witnesses from completed, fresh portable-package runs.

Example:
  python3 -B /work/code/report/audit_witnesses.py \
    --root /tmp/lab1-final-pace \
    --export /work/output/lab1-final-replay/pace --out /tmp/fresh-witnesses.json

Only the declared T26 window and case roles are fixed. Packet identities, times,
frontiers, counts and finite-transfer timelines are extracted from these runs.
This helper never launches simulations, regenerates analyses or reads old logs.
"""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

FIRST_WINDOW = (25_700_000_000, 28_200_000_000)
TAG = ("flow_id", "tx_id", "tx_time_ns", "seq", "payload_bytes")
ROLES = {
    "stock_t26": "leo10-base", "capacity": "capacity",
    "finite_stock": "micro-base", "finite_selective": "micro-selective",
    "finite_tail": "micro-tail", "finite_selected_pacing": "micro-selected",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def receipt(path):
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=digest)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    previous = -1
    with path.open(newline="", encoding="utf-8-sig") as source:
        for number, row in enumerate(csv.DictReader(source), 2):
            if "time_ns" in row:
                time = int(row["time_ns"])
                require(time >= previous, f"Nonchronological trace: {path}:{number}")
                previous = time
            yield dict(row, source_row=number)


def tag(row):
    return tuple(int(row[field]) for field in TAG)


def single(logs, pattern):
    paths = list(logs.glob(pattern))
    require(len(paths) == 1, f"Expected one {pattern}: {logs}")
    return paths[0]


def load_case(root, export, name, coverage_helper):
    run = root / name
    manifest_path, summary_path = run / "manifest.json", export / "cases" / name / "summary.json"
    m, s = read_json(manifest_path), read_json(summary_path)
    require(m.get("status") == "success" and m.get("exit_code") == 0 and not m.get("audit_exclude"),
            f"Incomplete/excluded run: {name}")
    require(m.get("case") == name and s["metrics"]["case"] == name, f"Case identity mismatch: {name}")
    for flag in ("runtime_unchanged", "source_unchanged", "launch_source_files_unchanged"):
        require(m.get(flag) is True, f"Failed {flag}: {name}")
    require(m.get("package_git", {}).get("commit") is None, f"Expected standalone replay: {name}")
    require(s["provenance"]["manifest"] == receipt(manifest_path), f"Stale summary manifest: {name}")
    analysis_path = run / "analysis.json"
    require(s["provenance"]["full_analysis"] == receipt(analysis_path), f"Stale full analysis: {name}")
    analysis = read_json(analysis_path)
    require(analysis["schema_version"] == 1 and set(analysis["flows"]) == {"0"}, f"Unsupported flow schema: {name}")
    verified = {}
    for rel, expected in m["output_files"].items():
        path = run / rel
        require(path.resolve().is_relative_to(run.resolve()) and path.is_file(), f"Invalid raw path: {rel}")
        actual = receipt(path)
        require(all(actual[k] == expected[k] for k in ("bytes", "sha256")), f"Raw hash mismatch: {name}/{rel}")
        verified[rel] = actual
    for item in analysis["inputs"]:
        path = Path(item["path"]).resolve()
        require(path.is_relative_to(run.resolve()) and str(path.relative_to(run.resolve())) in verified,
                f"External/unrecorded analysis input: {name}")
    logs = run / "logs_ns3"
    paths = dict(sender=single(logs, "tcp_flow_*_study_packets.csv"),
                 receiver=single(logs, "study_rx_node_*_port_*.csv"),
                 app=single(logs, "study_app_rx_node_*_port_*.csv"),
                 state=single(logs, "tcp_flow_*_study_events.csv"),
                 drops=logs / "study_drops.csv", coverage=logs / "study_drop_coverage.csv")
    coverage = coverage_helper.coverage_summary([paths["coverage"]])
    require(coverage == s["drop_coverage"], f"Coverage summary mismatch: {name}")
    packet_counts = Counter()
    retransmissions, syn = [], []
    for row in rows(paths["sender"]):
        require(row["flow_id"] == "0", f"Unexpected sender flow: {name}")
        packet_counts[row["event"]] += 1
        if row["event"] == "RETX" and int(row["payload_bytes"]):
            retransmissions.append(row)
        if row["event"] == "TX" and int(row["flags"]) & 2:
            syn.append(row)
    require(syn and all(int(r["seq"]) == 0 for r in syn), f"Initial sequence convention unsupported: {name}")
    retx_tags = {tag(r) for r in retransmissions}
    require(len(retx_tags) == len(retransmissions), f"Duplicate RETX identity: {name}")
    originals, next_seq, mirrors = [], 1, Counter()
    for row in rows(paths["sender"]):
        if row["event"] == "TX" and int(row["payload_bytes"]) and tag(row) in retx_tags:
            mirrors[tag(row)] += 1
        if row["event"] != "TX" or not int(row["payload_bytes"]) or tag(row) in retx_tags:
            continue  # Stock traces also emit TX for a tagged RETX; do not count it as new data.
        require(int(row["seq"]) == next_seq, f"Noncontiguous/new-sequence or wrap ambiguity: {name}")
        require(int(row["time_ns"]) == int(row["tx_time_ns"]), f"TX time/tag mismatch: {name}")
        next_seq += int(row["payload_bytes"])
        require(next_seq < 2**32, f"Sequence wrap unsupported: {name}")
        originals.append(row)
    require(all(mirrors[k] == 1 for k in retx_tags), f"Missing/duplicate TX mirror of RETX: {name}")
    require(all(int(r["time_ns"]) == int(r["tx_time_ns"]) for r in retransmissions), f"RETX time/tag mismatch: {name}")
    app_total, last_app, connection = 0, None, None
    for row in rows(paths["app"]):
        key = tuple(row[k] for k in ("node_id", "connection_id", "local_port", "peer_port", "flow_id"))
        connection = key if connection is None else connection
        require(key == connection and row["flow_id"] == "0", f"Multiple/unmapped app connections: {name}")
        app_total += int(row["payload_bytes"])
        require(app_total == int(row["connection_total_rx_bytes"]) == int(row["sink_total_rx_bytes"]),
                f"Application cumulative accounting mismatch: {name}")
        if int(row["payload_bytes"]):
            last_app = int(row["time_ns"])
    events = list(rows(paths["state"]))
    recovery = [r for r in events if r["event"] == "CONG" and r["new_value"] == "3" and r["old_value"] != "3"]
    losses = [r for r in events if r["event"] == "CONG" and r["new_value"] == "4" and r["old_value"] != "4"]
    drops = list(rows(paths["drops"]))
    known = [r for r in drops if r["flow_id"] == "0" and r["tx_id"] and int(r["tx_id"]) > 0]
    metrics = s["metrics"]
    for field, actual in (("receiver_bytes", app_total), ("retransmissions", len(retransmissions)),
                          ("recovery_entries", len(recovery)), ("ca_loss_entries", len(losses)),
                          ("drop_trace_rows", sum(r["flow_id"] == "0" for r in drops)),
                          ("distinct_tagged_drops", len({(r["flow_id"], r["tx_id"]) for r in known}))):
        require(metrics[field] == actual, f"Raw/summary {field} mismatch: {name}")
    require(math.isclose(app_total * 8 / metrics["duration_s"] / 1e6,
                         metrics["receiver_goodput_mbps"], rel_tol=0, abs_tol=1e-9), f"Goodput mismatch: {name}")
    if metrics["fct_s"] is not None:
        require(metrics["transfer_complete"] is True and app_total == m["expected_finite_bytes"], f"Incomplete FCT: {name}")
        require(math.isclose(last_app / 1e9 - metrics["flow_start_s"], metrics["fct_s"], rel_tol=0, abs_tol=1e-9),
                f"FCT mismatch: {name}")
    compact = dict(case=name, manifest=receipt(manifest_path), summary=receipt(summary_path),
                   full_analysis=receipt(analysis_path), consumed_raw_sources=[verified[str(p.relative_to(run))] for p in paths.values()],
                   all_manifest_outputs_hash_verified=len(verified), patch_sha256=m["patch_sha256"],
                   installed_diff_sha256=m["installed_diff_sha256"], runtime_files=m["runtime_files"],
                   build_ready_sha256=m["build_ready_sha256"], package_git=m["package_git"], metrics=metrics,
                   sender_event_counts=dict(packet_counts), drop_coverage=coverage,
                   drop_rows_without_usable_transmission_tag=analysis["drop_rows_without_usable_transmission_tag"],
                   sequence_mapping=dict(syn_sequence=0, first_new_data_sequence=1, exclusive_new_data_frontier=next_seq,
                                         ordered_app_bytes=app_total, no_wrap_validated=True))
    return dict(run=run, manifest=m, summary=s, analysis=analysis, paths=paths, compact=compact,
                originals=originals, retransmissions=retransmissions, recovery=recovery, drops=drops, last_app=last_app)


def packet_witnesses(case, selected, window=None):
    require(selected, "No selected retransmissions")
    paths = case["paths"]
    originals = {int(r["seq"]): r for r in case["originals"] if int(r["seq"]) in {int(x["seq"]) for x in selected}}
    wanted = {tag(r): r for r in originals.values()}
    received = {k: [] for k in wanted}
    rx_neighborhood = []
    lower = min(int(r["time_ns"]) for r in originals.values())
    upper = max(int(r["time_ns"]) for r in selected)
    lo_seq = min(int(r["seq"]) for r in originals.values())
    hi_seq = max(int(r["seq"]) + int(r["payload_bytes"]) for r in originals.values())
    for row in rows(paths["receiver"]):
        if row["tagged"] == "1" and tag(row) in wanted:
            received[tag(row)].append(row)
        if (lower <= int(row["time_ns"]) <= upper and int(row["payload_bytes"]) and
                lo_seq <= int(row["expected_seq"]) < hi_seq and int(row["seq"]) > int(row["expected_seq"])):
            rx_neighborhood.append(row)
    rx_times = {int(r["time_ns"]) for group in received.values() for r in group}
    app_rows, before_total = {}, 0
    for row in rows(paths["app"]):
        if int(row["time_ns"]) in rx_times:
            app_rows.setdefault(int(row["time_ns"]), []).append(dict(row, preceding_app_total_bytes=before_total))
        before_total = int(row["connection_total_rx_bytes"])
    acknowledgements = [r for r in rows(paths["sender"]) if r["event"] == "RX_ACK"]
    witnesses = []
    for retransmission in selected:
        seq, rt = int(retransmission["seq"]), int(retransmission["time_ns"])
        original = originals[seq]
        require(int(original["time_ns"]) < rt, "Original does not precede RETX")
        require(original["payload_bytes"] == retransmission["payload_bytes"], "Original/RETX byte-range mismatch")
        first_retx = min((r for r in case["retransmissions"] if int(r["seq"]) == seq), key=lambda r: int(r["time_ns"]))
        require(first_retx == retransmission, "Selected RETX is not the first for this sequence")
        matches = received[tag(original)]
        require(len(matches) == 1 and int(matches[0]["time_ns"]) < rt, "No unique original RX before RETX")
        rx = matches[0]
        require(rx["expected_seq"] == rx["seq"], "Wire arrival alone does not establish acceptance")
        same_time = app_rows.get(int(rx["time_ns"]), [])
        require(len(same_time) == 1, "Missing/ambiguous same-time receiver application evidence")
        app = same_time[0]
        require(app["node_id"] == rx["node_id"] and app["connection_id"] == rx["connection_id"], "RX/application connection mismatch")
        require(app["preceding_app_total_bytes"] == seq - 1 and int(app["connection_total_rx_bytes"]) >= seq + int(rx["payload_bytes"]) - 1,
                "Ordered application frontier does not cover the segment")
        original_drops = [d for d in case["drops"] if d["flow_id"] == "0" and d["tx_id"] and tag(d) == tag(original)]
        cohort_drops = [d for d in case["drops"] if d["flow_id"] == "0" and d["seq"] and int(d["payload_bytes"] or 0) and
                        int(d["seq"]) < seq + int(rx["payload_bytes"]) and seq < int(d["seq"]) + int(d["payload_bytes"]) and
                        int(original["time_ns"]) <= int(d["time_ns"]) < rt]
        require(not original_drops and not cohort_drops, "Observed drop conflicts with the claimed unnecessary original RETX")
        before_ack = [r for r in acknowledgements if r["source_row"] < retransmission["source_row"]]
        covering = [r for r in acknowledgements if int(r["time_ns"]) >= int(app["time_ns"]) and
                    int(r["ack"]) >= seq + int(rx["payload_bytes"])]
        witnesses.append(dict(original_tx=original, original_rx=rx, same_time_receiver_app=app,
                              later_first_retx=retransmission, original_sequence_delivered_before_retransmission=True,
                              app_to_retx_ns=rt-int(app["time_ns"]), original_tag_drop_rows=original_drops,
                              overlapping_sequence_drop_rows_before_retx=cohort_drops,
                              sender_ack_immediately_preceding_retx=before_ack[-1] if before_ack else None,
                              first_subsequent_cumulative_ack_covering_segment=covering[0] if covering else None))
    start, end = window or (min(int(r["time_ns"]) for r in selected), max(int(r["time_ns"]) for r in selected)+1)
    rec = [r for r in case["recovery"] if start <= int(r["time_ns"]) < end]
    event_drops = [r for r in case["drops"] if start <= int(r["time_ns"]) < end]
    count = dict(start_ns=start, end_ns=end, retx_packets=sum(start <= int(r["time_ns"]) < end for r in case["retransmissions"]),
                 recovery_entries=len(rec), rx_ack_rows=sum(start <= int(r["time_ns"]) < end for r in acknowledgements),
                 rx_ack_rows_with_sack=sum(start <= int(r["time_ns"]) < end and bool(r["sack_blocks"]) for r in acknowledgements),
                 all_direction_drop_rows=len(event_drops))
    if window:
        matches = [w["flows"]["0"] for w in case["summary"]["path_event_windows"]
                   if round(w["window_start_s"]*1e9) == start and round(w["window_end_s"]*1e9) == end]
        require(len(matches) == 1, "Missing predeclared T26 summary window")
        for field, name in (("retx_packets", "official_retransmission_rows"), ("recovery_entries", "recovery_state_entries")):
            require(count[field] == matches[0].get(name, 0), f"Event count mismatch: {field}")
    return dict(witnesses=witnesses, window_counts=count, recovery_entry_rows=rec,
                reordered_original_receiver_rows=rx_neighborhood,
                qualification="Each claim uses the exact original transmission tag, pre-processing expected_seq, and same-time ordered receiver application delivery. Wire receipt or absence of observed drops alone is insufficient. ACK arrival at the sender may lag application delivery. These witnesses do not establish a universal loss-path audit or the physical cause of the route-neighborhood reordering.")


def finite_chronology(case):
    originals, retransmissions, s = case["originals"], case["retransmissions"], case["summary"]
    require(retransmissions and s["metrics"]["transfer_complete"] is True, "Incomplete finite chronology")
    first = retransmissions[0]
    after = [r for r in originals if int(r["time_ns"]) >= int(first["time_ns"])]
    tail = s["tail_policy"]
    pacing_path = case["run"] / "logs_ns3/tcp_flow_0_pacing.csv"
    pacing = list(rows(pacing_path)) if pacing_path.exists() else []
    episodes = s["selective_policy"]["episodes"]
    inside = [{"episode": ep, "original_tx_rows": [r for r in originals if ep["start_ns"] <= int(r["time_ns"]) < ep["end_ns"]]}
              for ep in episodes]
    physical = [r for r in case["drops"] if r["layer"] == "PhyRxDrop" and int(r["payload_bytes"] or 0) > 0]
    require(len(physical) == 1, "Finite physical-loss rule does not select exactly one transmission")
    drop = physical[0]
    matching = [r for r in originals if tag(r) == tag(drop)]
    require(len(matching) == 1 and int(matching[0]["time_ns"]) <= int(drop["time_ns"]), "Physical drop has no exact original-TX join")
    subsequent = [r for r in retransmissions if r["seq"] == drop["seq"] and int(r["time_ns"]) >= int(drop["time_ns"])]
    require(subsequent, "No after-drop retransmission of the selected finite loss")
    return dict(metrics=s["metrics"], first_data_retransmission=first, last_new_original_tx=originals[-1],
                first_retx_to_last_new_tx_ns=int(originals[-1]["time_ns"])-int(first["time_ns"]),
                first_retx_to_last_app_delivery_ns=case["last_app"]-int(first["time_ns"]),
                new_original_tx_rows_after_first_retx=after, all_new_original_tx_rows=originals,
                all_data_retransmission_rows=retransmissions, recovery_entry_rows=case["recovery"],
                physical_drop_rows=case["drops"], physical_loss_witness=dict(drop=drop, original_tx=matching[0],
                    first_retransmission_after_drop=subsequent[0], drop_to_first_retx_ns=int(subsequent[0]["time_ns"])-int(drop["time_ns"])),
                selective_wait_episodes=episodes,
                new_originals_during_actual_waits=inside, tail_policy=tail, native_pacing_rate_changes=pacing,
                pacing_source=receipt(pacing_path) if pacing_path.exists() else None,
                qualification="TX rows sharing a RETX tag are excluded from original-data counts. FCT is the completed receiver application endpoint, not the last TX. This observed finite scenario does not exercise every receiver-window, FIN, ECN, RTO or extra-tail-loss safety branch.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing to overwrite: {args.out}")
    package = Path(__file__).resolve().parents[1]
    helper_path = package / "code/kim-study/analyze_study.py"
    spec = importlib.util.spec_from_file_location("witness_coverage", helper_path)
    coverage_helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage_helper)
    out = dict(schema=1, status="running", phase="Post-simulation explanatory audit of fresh isolated-package runs; no simulations or original-log imports.",
               tool=receipt(Path(__file__)), coverage_helper=receipt(helper_path), roles=ROLES, cases={})
    try:
        for role, name in ROLES.items():
            case = load_case(args.root, args.export, name, coverage_helper)
            record = case["compact"]
            if role == "stock_t26":
                selected = [r for r in case["retransmissions"] if FIRST_WINDOW[0] <= int(r["time_ns"]) < FIRST_WINDOW[1]]
                require(len(selected) == 3, "The declared three-packet T26 stock claim is unsupported")
                record["packet_witnesses"] = packet_witnesses(case, selected, FIRST_WINDOW)
                require(record["packet_witnesses"]["window_counts"]["recovery_entries"] == 1, "The declared one-recovery T26 claim is unsupported")
            elif role == "capacity":
                require(len(case["retransmissions"]) == 2, "The declared two remaining capacity RETXs are unsupported")
                record["packet_witnesses"] = packet_witnesses(case, case["retransmissions"])
                record["route_cause_limit"] = "Observed packet reordering does not independently establish geometric shortening. Use a separate supplied-geometry receipt to identify the actual route transition and its propagation-delay direction."
            else:
                record["finite_chronology"] = finite_chronology(case)
            out["cases"][role] = record
        out["status"] = "success"
        out["verified_unnecessary_retransmissions"] = sum(len(out["cases"][role]["packet_witnesses"]["witnesses"]) for role in ("stock_t26", "capacity"))
        out["qualification"] = "Direct application-delivery witnesses prove these five retransmissions unnecessary for delivering their byte ranges. They do not prove every recovery was spurious, queue-free operation, deployment feasibility, or general algorithm superiority. The original analyzer's candidate classifications are broader than this APP-before-RETX criterion."
    except Exception as error:
        out.update(status="failed", error=f"{type(error).__name__}: {error}", qualification="Incomplete audit: do not use missing witnesses as established claims.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(out, destination, indent=2)
        destination.write("\n")
    print(json.dumps(dict(out=str(args.out), status=out["status"], verified_unnecessary_retransmissions=out.get("verified_unnecessary_retransmissions"), error=out.get("error"))))
    return 0 if out["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
