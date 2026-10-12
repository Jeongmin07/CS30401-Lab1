"""Sparse directional path-change geometry using the supplied state only.

Evaluate the old and new routes at the SAME change time; do not interpret
half of a two-direction RTT drop as a verified forward delay change.
Runs inside the course image. No new topology or simulation is generated.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=Path('/home/ubuntu/lab/data/seoul_london/state'))
    p.add_argument('--dynamic', default='dynamic_state_100ms_for_200s')
    p.add_argument('--src', type=int, default=1584)
    p.add_argument('--dst', type=int, default=1585)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists() or a.receipt.exists():
        raise ValueError('Refusing to overwrite geometry artifacts')
    clock = time.monotonic()
    os.environ.setdefault('SATGENPY', '/home/ubuntu/lab/hypatia/satgenpy')
    official = Path('/home/ubuntu/lab/scripts/path_truth.py')
    spec = importlib.util.spec_from_file_location('course_path_truth', official)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tles = module.satgen.read_tles(str(a.state/'tles.txt'))
    sats, epoch = tles['satellites'], tles['epoch']
    gss = module.satgen.read_ground_stations_extended(str(a.state/'ground_stations.txt'))
    n = len(sats)
    table, prev, events, inputs = {}, None, [], []
    files = sorted((a.state/a.dynamic).glob('fstate_*.txt'),
                   key=lambda q: int(q.stem.split('_')[1]))
    rows_read = bytes_read = 0

    def walk(start, destination):
        path, seen = [start], {start}
        while path[-1] != destination:
            nxt = table.get((path[-1], destination), -1)
            if nxt < 0 or nxt in seen or len(path) > 200:
                raise ValueError('Missing or cyclic supplied route')
            path.append(nxt)
            seen.add(nxt)
        return path

    def propagation(path, event_ns):
        date = str(epoch + event_ns * module.u.ns)
        distance = 0.0
        for x, y in zip(path, path[1:]):
            if x >= n:
                distance += module.satgen.distance_m_ground_station_to_satellite(
                    gss[x-n], sats[y], str(epoch), date)
            elif y >= n:
                distance += module.satgen.distance_m_ground_station_to_satellite(
                    gss[y-n], sats[x], str(epoch), date)
            else:
                distance += module.satgen.distance_m_between_satellites(
                    sats[x], sats[y], str(epoch), date)
        return round(distance/module.C*1e9)

    for source in files:
        t = int(source.stem.split('_')[1])
        raw = source.read_bytes()
        inputs.append(dict(name=source.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        bytes_read += len(raw)
        for line in raw.decode().splitlines():
            current, dest, nxt, _, _ = map(int, line.split(','))
            table[(current, dest)] = nxt
            rows_read += 1
        current = (walk(a.src, a.dst), walk(a.dst, a.src))
        if prev is not None and current != prev:
            events.append(dict(event_ns=t,
                fwd_changed=int(current[0] != prev[0]), rev_changed=int(current[1] != prev[1]),
                old_fwd_ns=propagation(prev[0], t), new_fwd_ns=propagation(current[0], t),
                old_rev_ns=propagation(prev[1], t), new_rev_ns=propagation(current[1], t),
                old_fwd_path='-'.join(map(str, prev[0])), new_fwd_path='-'.join(map(str, current[0])),
                old_rev_path='-'.join(map(str, prev[1])), new_rev_path='-'.join(map(str, current[1]))))
        prev = current
    if not events:
        raise ValueError('No supplied path changes')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(events[0]))
        w.writeheader()
        w.writerows(events)
    receipt = dict(kind='same-event-time forward/reverse propagation only', src=a.src, dst=a.dst,
        script_sha256=digest(__file__), course_script_sha256=digest(official),
        static_inputs={q.name:digest(q) for q in sorted(a.state.iterdir()) if q.is_file()},
        input_files=inputs, input_rows=rows_read, input_bytes=bytes_read,
        path_changes=len(events), output_sha256=digest(a.out), wall_seconds=time.monotonic()-clock,
        limitations='No queue/serialization/packet arrival bound; operator routing oracle, not a public-orbit predictor.',
        new_topology_generated=False, simulations_run=False)
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('input_rows','input_bytes','path_changes','wall_seconds','output_sha256')}))


if __name__ == '__main__':
    main()
