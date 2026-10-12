"""Bounded on-demand geometry screening; do not generate forwarding state or run TCP.

Reconstruct free-one/ISL-only path choices with destination-visible-satellite
single-source Dijkstra caches. First compare Seoul/London nodes and outgoing
interfaces with the independently walked existing forwarding files. Additional
city paths remain geometry hypotheses, not an exported/simulated topology.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import sys
import time
import types
from pathlib import Path

STARTED = time.monotonic()
DEFAULT_CITIES = Path("/home/ubuntu/hypatia/paper/satellite_networks_state/input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_1000.basic.txt")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class StopProbe(Exception):
    pass


class Probe:
    def __init__(self, args):
        self.args = args
        self.snapshots = []
        self.dijkstra_count = 0
        self.ephem_isl_position_computations = 0
        self.gsl_distance_calls = 0

    def check(self):
        if time.monotonic() - STARTED > self.args.max_elapsed_s:
            raise StopProbe("Elapsed geometry budget reached")

    def graph(self, nx, ephem, satellites, isls, epoch_str, date_str, max_isl):
        self.check()
        positions = {}
        # Same cached (a_ra, a_dec, range) calculation as course gen_state.py's
        # _fast_isl_distance. Store values before GS observers mutate ephem objects.
        for sid, satellite in enumerate(satellites):
            self.check()
            observer = ephem.Observer()
            observer.epoch, observer.date = epoch_str, date_str
            observer.lat, observer.lon, observer.elevation = 0, 0, 0
            satellite.compute(observer)
            positions[sid] = (satellite.a_ra, satellite.a_dec, satellite.range)
            self.ephem_isl_position_computations += 1
        graph, degree, interfaces = nx.Graph(), [0] * len(satellites), {}
        graph.add_nodes_from(range(len(satellites)))
        for a, b in isls:
            ra1, de1, r1 = positions[a]
            ra2, de2, r2 = positions[b]
            angle = float(repr(ephem.separation((ra1, de1), (ra2, de2))))
            distance = math.sqrt(r1 ** 2 + r2 ** 2 - 2 * r1 * r2 * math.cos(angle))
            require(math.isfinite(distance) and 0 < distance <= max_isl, "Invalid ISL geometry")
            # Insertion order is the official ISL-file order. Its strict-<
            # neighbor tie selection must not be replaced with a generic path.
            graph.add_edge(a, b, weight=distance)
            interfaces[(a, b)], interfaces[(b, a)] = degree[a], degree[b]
            degree[a] += 1
            degree[b] += 1
        return graph, degree, interfaces

    def visible(self, satgen, stations, satellites, epoch_str, date_str, max_gsl):
        result = {}
        for station in stations:
            candidates = []
            for sid, satellite in enumerate(satellites):
                self.check()
                distance = satgen.distance_m_ground_station_to_satellite(
                    station, satellite, epoch_str, date_str)
                self.gsl_distance_calls += 1
                if distance <= max_gsl:
                    candidates.append((distance, sid))
            result[station["name"]] = candidates
        return result

    def paths(self, nx, graph, visible, specs, satellites, degree, interfaces):
        distance_cache = {}
        targets = sorted({sid for _, destination in specs.values() for _, sid in visible[destination["name"]]})
        for sid in targets:
            self.check()
            if self.dijkstra_count >= self.args.max_dijkstra:
                raise StopProbe("Single-source Dijkstra budget reached")
            distance_cache[sid] = nx.single_source_dijkstra_path_length(graph, sid, weight="weight")
            self.dijkstra_count += 1

        def to_ground(cur, destination):
            choices = sorted((distance_cache[dst_sat].get(cur, math.inf) + gsl_distance, dst_sat)
                             for gsl_distance, dst_sat in visible[destination["name"]]
                             if math.isfinite(distance_cache[dst_sat].get(cur, math.inf)))
            return choices[0] if choices else (math.inf, None)

        result = {}
        for label, (source, destination) in specs.items():
            options = sorted((gsl_distance + to_ground(sid, destination)[0], sid)
                             for gsl_distance, sid in visible[source["name"]]
                             if math.isfinite(to_ground(sid, destination)[0]))
            if not options:
                result[label] = {"status": "no_visible_reachable_route", "nodes": [], "edges": [], "egresses": []}
                continue
            cur, nodes, edges, egresses = options[0][1], [source["node_id"], options[0][1]], [], []
            edges.append((source["node_id"], cur))
            egresses.append((source["node_id"], 0))
            total_distance = visible[source["name"]][[s for _, s in visible[source["name"]]].index(cur)][0]
            status = "hop_budget_reached"
            for _ in range(self.args.max_hops):
                _, dst_sat = to_ground(cur, destination)
                if dst_sat is None:
                    status = "unreachable_destination"
                    break
                if cur == dst_sat:
                    edges.append((cur, destination["node_id"]))
                    egresses.append((cur, degree[cur]))  # exactly one free GSL interface
                    total_distance += next(d for d, sid in visible[destination["name"]] if sid == cur)
                    nodes.append(destination["node_id"])
                    status = "reachable"
                    break
                best_distance, next_hop = 1_000_000_000_000_000, None
                for neighbor in graph.neighbors(cur):
                    distance = graph.edges[cur, neighbor]["weight"] + distance_cache[dst_sat].get(neighbor, math.inf)
                    if distance < best_distance:
                        best_distance, next_hop = distance, neighbor
                if next_hop is None or next_hop in nodes:
                    status = "missing_neighbor_or_loop"
                    break
                edges.append((cur, next_hop))
                egresses.append((cur, interfaces[(cur, next_hop)]))
                total_distance += graph.edges[cur, next_hop]["weight"]
                nodes.append(next_hop)
                cur = next_hop
            result[label] = {"status": status, "nodes": nodes, "edges": edges, "egresses": egresses,
                             "path_distance_m": total_distance,
                             "one_way_geometric_propagation_ms": total_distance / 299_792_458 * 1000}
        return result, len(targets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=Path(__file__).resolve().parents[2] /
                        "docs/experiments/assets/20261012-bbr-route/path-probe.json")
    parser.add_argument("--city-data", type=Path, default=DEFAULT_CITIES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-elapsed-s", type=float, default=100)
    parser.add_argument("--max-dijkstra", type=int, default=1000)
    parser.add_argument("--max-metadata-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-hops", type=int, default=64)
    args = parser.parse_args()
    require(not args.out.exists(), "Choose a new output directory")
    require(all(getattr(args, k) > 0 for k in ("max_elapsed_s", "max_dijkstra", "max_metadata_bytes", "max_hops")),
            "Budgets must be positive")
    probe = Probe(args)
    satgen_root = Path("/home/ubuntu/hypatia/satgenpy")
    for name in ("cartopy", "cartopy.crs"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.path.insert(0, str(satgen_root))
    import satgen
    import ephem
    import networkx as nx
    from astropy import units as u
    import astropy

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference["complete_requested_prefix"], "Reference path probe must be complete")
    reference_csv = args.reference.parent / "path-samples.csv"
    require({k: v for k, v in fingerprint(reference_csv).items() if k != "path"} == reference["outputs"]["path-samples.csv"],
            "Reference path CSV hash mismatch")
    with reference_csv.open(newline="", encoding="utf-8") as stream:
        actual = {(int(r["time_ns"]), int(r["source_node"]), int(r["destination_node"])):
                  {"status": r["status"], "nodes": json.loads(r["path_nodes"]),
                   "egresses": json.loads(r["directed_egresses"])} for r in csv.DictReader(stream)}
    samples = reference["requested_samples_ns"]
    require(1 <= len(samples) <= 8, "At most eight reference samples")
    paths_to_hash = [args.state / n for n in ("tles.txt", "ground_stations.txt", "isls.txt", "description.txt", "gsl_interfaces_info.txt")]
    source_paths = [Path("/home/ubuntu/lab/scripts/gen_state.py"), satgen_root / "satgen/dynamic_state/generate_dynamic_state.py",
        satgen_root / "satgen/dynamic_state/fstate_calculation.py", satgen_root / "satgen/dynamic_state/algorithm_free_one_only_over_isls.py",
        satgen_root / "satgen/distance_tools/distance_tools.py", satgen_root / "satgen/tles/read_tles.py"]
    fingerprint_paths = paths_to_hash + source_paths + [args.city_data, args.reference, reference_csv]
    require(sum(p.stat().st_size for p in fingerprint_paths) <= args.max_metadata_bytes,
            "Metadata/source-fingerprint read budget would be exceeded")
    inputs = [fingerprint(p) for p in fingerprint_paths]
    for previous in reference["metadata_inputs"]:
        if previous["name"] in ("tles.txt", "ground_stations.txt"):
            current = next(item for item in inputs if item["path"] == str(args.state / previous["name"]))
            require(current["sha256"] == previous["sha256"] and current["bytes"] == previous["bytes"],
                    "Geometry inputs differ from forwarding-path reference")
    tle = satgen.read_tles(str(args.state / "tles.txt"))
    satellites, epoch = tle["satellites"], tle["epoch"]
    isls = satgen.read_isls(str(args.state / "isls.txt"), len(satellites))
    original = satgen.read_ground_stations_extended(str(args.state / "ground_stations.txt"))
    require(len(original) == 2 and [s["name"] for s in original] == ["Seoul", "London"],
            "This bounded probe validates the supplied Seoul/London reference only")
    for station in original:
        station["node_id"] = len(satellites) + station["gid"]
    with args.city_data.open(newline="", encoding="utf-8") as stream:
        cities = {row[1]: row for row in csv.reader(stream)}
    stations = list(original)
    for name in ("Tokyo", "Paris"):
        require(name in cities, f"City absent from the installed Hypatia input dataset: {name}")
        row = cities[name]
        stations.append({"gid": len(stations), "node_id": len(satellites) + len(stations), "name": name,
                         "latitude_degrees_str": f"{float(row[2]):.6f}",
                         "longitude_degrees_str": f"{float(row[3]):.6f}", "elevation_m_float": float(row[4])})
    by_name = {s["name"]: s for s in stations}
    specs = {"reference-seoul-london": (by_name["Seoul"], by_name["London"]),
             "reference-london-seoul": (by_name["London"], by_name["Seoul"]),
             "candidate-tokyo-paris": (by_name["Tokyo"], by_name["Paris"])}
    description = dict(line.split("=", 1) for line in (args.state / "description.txt").read_text().splitlines())
    max_gsl, max_isl = float(description["max_gsl_length_m"]), float(description["max_isl_length_m"])
    with (args.state / "gsl_interfaces_info.txt").open() as stream:
        gsl_rows = list(csv.reader(stream))
    require(len(gsl_rows) == len(satellites) + len(original) and all(int(r[1]) == 1 for r in gsl_rows),
            "Reference is not the one-interface-per-node free-one policy")
    rows, overlaps, comparisons, stop_reason = [], [], [], None
    try:
        for at in samples:
            probe.check()
            before, previous_dijkstra = time.monotonic(), probe.dijkstra_count
            date_str, epoch_str = str(epoch + at * u.ns), str(epoch)
            graph, degree, interfaces = probe.graph(nx, ephem, satellites, isls, epoch_str, date_str, max_isl)
            visible = probe.visible(satgen, stations, satellites, epoch_str, date_str, max_gsl)
            found, unique_targets = probe.paths(nx, graph, visible, specs, len(satellites), degree, interfaces)
            for label in ("reference-seoul-london", "reference-london-seoul"):
                source, destination = specs[label]
                expected = actual.get((at, source["node_id"], destination["node_id"]))
                require(expected is not None, "Missing reference path at requested time")
                observed = found[label]
                passed = expected["status"] == observed["status"] and expected["nodes"] == observed["nodes"] and \
                         expected["egresses"] == [list(e) for e in observed["egresses"]]
                comparisons.append({"time_ns": at, "pair": label, "exact_nodes_and_directed_egresses": passed,
                                    **({} if passed else {"expected": expected, "observed": observed})})
                if not passed:
                    raise StopProbe("Reference mismatch; additional-city geometry must not be promoted to routing evidence")
            for label, found_path in found.items():
                source, destination = specs[label]
                rows.append({"time_ns": at, "pair": label, "source": source["name"], "destination": destination["name"],
                    "status": found_path["status"], "path_nodes": json.dumps(found_path["nodes"], separators=(",", ":")),
                    "directed_egresses": json.dumps(found_path["egresses"], separators=(",", ":")),
                    "one_way_geometric_propagation_ms": found_path.get("one_way_geometric_propagation_ms", "")})
            a, b = found["reference-seoul-london"], found["candidate-tokyo-paris"]
            known = a["status"] == b["status"] == "reachable"
            common_edges = sorted(set(a["edges"]) & set(b["edges"])) if known else []
            common_egresses = sorted(set(a["egresses"]) & set(b["egresses"])) if known else []
            common_isl = [e for e in common_edges if e[0] < len(satellites) and e[1] < len(satellites)]
            common_gsl_egresses = [e for e in common_egresses if e[0] < len(satellites) and
                                  e[1] == degree[e[0]]] if known else []
            overlaps.append({"time_ns": at, "group": "seoul-london_vs_tokyo-paris", "both_reachable": known,
                "shared_isl_edges": json.dumps(common_isl, separators=(",", ":")), "shared_isl_edge_count": len(common_isl),
                "shared_directed_egresses": json.dumps(common_egresses, separators=(",", ":")),
                "shared_gsl_egresses": json.dumps(common_gsl_egresses, separators=(",", ":"))})
            probe.snapshots.append({"time_ns": at, "satellites": len(satellites), "isl_edges": len(isls),
                "visible_satellites": {name: len(value) for name, value in visible.items()},
                "unique_destination_visible_satellites": unique_targets,
                "dijkstra_calls": probe.dijkstra_count - previous_dijkstra, "elapsed_s": time.monotonic() - before})
            probe.check()
    except StopProbe as exc:
        stop_reason = str(exc)
    completed = stop_reason is None and len(probe.snapshots) == len(samples)
    known_overlaps = [r for r in overlaps if r["both_reachable"]]
    shared, separate = [r["time_ns"] for r in known_overlaps if r["shared_isl_edge_count"]], \
                       [r["time_ns"] for r in known_overlaps if not r["shared_isl_edge_count"]]
    args.out.mkdir(parents=True)
    write_csv(args.out / "geometry-paths.csv", ("time_ns", "pair", "source", "destination", "status", "path_nodes",
        "directed_egresses", "one_way_geometric_propagation_ms"), rows)
    write_csv(args.out / "geometry-overlaps.csv", ("time_ns", "group", "both_reachable", "shared_isl_edges",
        "shared_isl_edge_count", "shared_directed_egresses", "shared_gsl_egresses"), overlaps)
    summary = {"kind": "bounded_on_demand_geometry_hypothesis", "no_state_generation_or_simulation": True,
        "complete": completed, "stop_reason": stop_reason,
        "script_sha256": fingerprint(Path(__file__))["sha256"], "input_fingerprints": inputs,
        "requested_samples_ns": samples, "snapshots": probe.snapshots,
        "stations": [{k: v for k, v in s.items() if k in ("name", "node_id", "latitude_degrees_str", "longitude_degrees_str", "elevation_m_float")} for s in stations],
        "hypothetical_added_stations": ["Tokyo", "Paris"], "candidate_groups": ["Seoul->London vs Tokyo->Paris"],
        "reference_comparisons": comparisons, "reference_matches": sum(c["exact_nodes_and_directed_egresses"] for c in comparisons),
        "reference_expected_comparisons": 2 * len(samples),
        "observed_shared_isl_sample_times_ns": shared, "observed_no_shared_isl_sample_times_ns": separate,
        "candidate_isl_merge_split_at_sampled_times": bool(shared and separate),
        "read_cost": {"fingerprinted_metadata_source_bytes": sum(item["bytes"] for item in inputs),
            "satgen_loader_additional_declared_bytes": sum((args.state / n).stat().st_size for n in ("tles.txt", "isls.txt", "ground_stations.txt")) +
                args.city_data.stat().st_size + (args.state / "description.txt").stat().st_size + (args.state / "gsl_interfaces_info.txt").stat().st_size + args.reference.stat().st_size + reference_csv.stat().st_size,
            "dijkstra_calls": probe.dijkstra_count, "ephem_isl_position_computations": probe.ephem_isl_position_computations,
            "gsl_distance_calls": probe.gsl_distance_calls, "elapsed_s_including_imports_and_tle_loading": time.monotonic() - STARTED,
            "meaning": "Metadata/source fingerprint reads and loader reads are reported separately; Python import IO and physical disk IO are not measured."},
        "budgets": {k: getattr(args, k) for k in ("max_elapsed_s", "max_dijkstra", "max_metadata_bytes", "max_hops")},
        "versions": {"networkx": nx.__version__, "ephem": ephem.__version__, "astropy": astropy.__version__},
        "method": ["Same TLEs, epoch, ISLs in file order, cached ephem ISL weights, GSL visibility distance threshold and one free GSL interface as the official generator.",
            "Every visible destination satellite gets one length-vector SSSP, cached per snapshot; no all-pairs shortest paths or full forwarding export.",
            "Source attachment minimizes full GSL+ISL+GSL distance, not nearest-satellite distance alone.",
            "At every satellite select (remaining distance + destination GSL length, destination satellite ID), then official strict-< neighbor iteration order.",
            "Dijkstra direction and floating-point/tie behavior may differ from the generator's scipy APSP; known sampled references are checked exactly, not assumed equivalent."],
        "limits": ["Additional-city node IDs exist only in this in-memory hypothesis, not in the supplied state.",
            "Eight samples can bracket sharing differences but cannot identify event timing, duration, in-flight paths or behavior between samples.",
            "ISL edge overlap and GSL egress overlap are separate; neither establishes a bottleneck or actual packet queue contention.",
            "One-way geometric propagation is a path-distance calculation, not socket SRTT or measured queue latency.",
            "Exact agreement on original sampled routes does not prove all future four-GS forwarding entries match an official export.",
            "A candidate requires a separately validated topology/state and matched TCP baseline before any performance claim."],
        "outputs": {name: {k: v for k, v in fingerprint(args.out / name).items() if k != "path"}
                    for name in ("geometry-paths.csv", "geometry-overlaps.csv")}}
    (args.out / "geometry-probe.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": completed, "reference_matches": summary["reference_matches"],
                      "candidate_isl_merge_split_at_sampled_times": summary["candidate_isl_merge_split_at_sampled_times"],
                      "read_cost": summary["read_cost"], "stop_reason": stop_reason}))
    return 0 if completed else 2


if __name__ == "__main__":
    raise SystemExit(main())
