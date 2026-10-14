"""Construct only the predeclared T75 to T78 sparse routing counterfactual.

This retains the original selective policy/hints. It is a fixed-policy routing
intervention under the supplied ideal GSL channel, not a visibility forecast.
No ns-3 simulation, topology generation or shortest-path computation occurs.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import time

ORIGINAL_T = 75_000_000_000
DELAYED_T = 78_000_000_000
STEP = 100_000_000


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def read_rows(path):
    data = [tuple(map(int, s.split(','))) for s in path.read_text().splitlines() if s]
    assert all(len(r) == 5 for r in data), path
    assert len({r[:2] for r in data}) == len(data), 'Duplicate sparse key'
    return data


def apply(table, records):
    for current, target, nxt, my_if, next_if in records:
        table[(current, target)] = (nxt, my_if+1, next_if+1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=Path('/home/ubuntu/lab/data/seoul_london/state'))
    p.add_argument('--observed-logs', type=Path, default=Path('/tmp/orbit-queue/selective-natural/logs_ns3'))
    p.add_argument('--out-state', type=Path, default=Path('/tmp/orbit-queue-inputs/delay75-to78/state'))
    p.add_argument('--receipt', required=True, type=Path)
    a = p.parse_args(); start = time.monotonic()
    assert not a.out_state.exists() and not a.receipt.exists(), 'Refuse overwrite'
    dynamic_name = 'dynamic_state_100ms_for_200s'
    original_dynamic = a.state/dynamic_name
    t75 = original_dynamic/f'fstate_{ORIGINAL_T}.txt'
    t78 = original_dynamic/f'fstate_{DELAYED_T}.txt'
    change = read_rows(t75)
    assert len(change) == 30 and all(r[1] in (1584, 1585) for r in change), 'Unexpected supplied T75 transition'
    assert len(read_rows(t78)) == 0, 'T78 already contains another update'
    for t in range(ORIGINAL_T+STEP, DELAYED_T+STEP, STEP):
        assert not read_rows(original_dynamic/f'fstate_{t}.txt'), 'Intervening routing update'

    # Exact live device identities were recorded by the completed natural run.
    metadata_path = a.observed_logs/'queue_devices.csv'
    with metadata_path.open(newline='') as f:
        metadata = {(int(r['node_id']), int(r['device_id'])): r for r in csv.DictReader(f)}
    ids = sorted({node for node, _ in metadata})
    assert ids == list(range(1586)), 'Unexpected course node set'
    degree = {node: 0 for node in ids}
    counterpart = {}
    # Native TopologySatelliteNetwork::CreateISLs creates devices in file order,
    # after loopback. Check that reconstructed indices agree with live types.
    for line in (a.state/'isls.txt').read_text().splitlines():
        x, y = map(int, line.split())
        degree[x] += 1; degree[y] += 1
        counterpart[(x, degree[x])] = (y, degree[y])
        counterpart[(y, degree[y])] = (x, degree[x])
    for index in counterpart:
        assert metadata[index]['device_type'] == 'ns3::PointToPointLaserNetDevice', index
    gsl_interfaces = {}
    for line in (a.state/'gsl_interfaces_info.txt').read_text().splitlines():
        node, count, _ = line.split(','); node, count = int(node), int(count)
        gsl_interfaces[node] = list(range(degree[node]+1, degree[node]+count+1))
        for interface in gsl_interfaces[node]:
            assert metadata[(node, interface)]['device_type'] == 'ns3::GSLNetDevice'
    expected_indices = set(counterpart) | {(node, i) for node, iset in gsl_interfaces.items() for i in iset}
    assert expected_indices == set(metadata), 'Native interface ordering differs'

    def edge(node, destination, table):
        nxt, my_if, next_if = table[(node, destination)]
        assert nxt >= 0 and (node, my_if) in metadata and (nxt, next_if) in metadata
        source_type = metadata[(node, my_if)]['device_type']
        next_type = metadata[(nxt, next_if)]['device_type']
        if source_type == 'ns3::PointToPointLaserNetDevice':
            assert next_type == source_type and counterpart[(node, my_if)] == (nxt, next_if)
        else:
            assert source_type == next_type == 'ns3::GSLNetDevice'
            assert (node >= 1584) != (nxt >= 1584), 'Non satellite-ground GSL hop'
        return (node, my_if, nxt, next_if, source_type)

    def walk(source, destination, table):
        path, edges, seen = [source], [], {source}
        while path[-1] != destination:
            assert (path[-1], destination) in table, 'Missing forwarding key'
            e = edge(path[-1], destination, table)
            nxt = e[2]
            assert nxt not in seen and len(path) < 1586, 'Forwarding loop'
            path.append(nxt); seen.add(nxt); edges.append(e)
        return dict(nodes=path, interfaces=edges)

    a.out_state.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(a.state, a.out_state)
    modified_dynamic = a.out_state/dynamic_name
    (modified_dynamic/t75.name).write_bytes(b'')
    (modified_dynamic/t78.name).write_bytes(t75.read_bytes())
    originals = {str(x.relative_to(a.state)): sha(x) for x in sorted(a.state.rglob('*')) if x.is_file()}
    modified = {str(x.relative_to(a.out_state)): sha(x) for x in sorted(a.out_state.rglob('*')) if x.is_file()}
    changed = [n for n in originals if originals[n] != modified[n]]
    assert set(changed) == {str(t75.relative_to(a.state)), str(t78.relative_to(a.state))}
    assert set(originals) == set(modified)

    frames = sorted(original_dynamic.glob('fstate_*.txt'), key=lambda f:int(f.stem.split('_')[1]))
    assert [int(f.stem.split('_')[1]) for f in frames] == list(range(0, 200_000_000_000, STEP))
    ot, mt = {}, {}
    affected_frames, future_overrides = [], []
    targets = {(x, destination) for x in ids for destination in (1584, 1585) if x != destination}
    keys = {r[:2] for r in change}
    for f in frames:
        t = int(f.stem.split('_')[1]); original_rows = read_rows(f)
        modified_rows = read_rows(modified_dynamic/f.name)
        apply(ot, original_rows); apply(mt, modified_rows)
        if t < ORIGINAL_T or t >= DELAYED_T:
            assert ot == mt, 'Accumulated state differs outside the declared delayed interval'
        if ORIGINAL_T <= t <= DELAYED_T+STEP:
            # All sources to both supplied destinations, not merely the two
            # endpoint paths, must be loop-free and use native-valid interfaces.
            for current, destination in targets:
                walk(current, destination, ot); walk(current, destination, mt)
            affected_frames.append(dict(time_ns=t,
                original_forward=walk(1584, 1585, ot), original_reverse=walk(1585, 1584, ot),
                modified_forward=walk(1584, 1585, mt), modified_reverse=walk(1585, 1584, mt),
                original_state_digest=digest(sorted((k,v) for k,v in ot.items())),
                modified_state_digest=digest(sorted((k,v) for k,v in mt.items())),
                state_equal=ot == mt, all_source_paths_checked_each_state=len(targets)))
        if t > ORIGINAL_T:
            overlapping = [r for r in original_rows if r[:2] in keys]
            if overlapping:
                future_overrides.append(dict(time_ns=t, changed_key_overrides=len(overlapping)))
    record = dict(schema=1, original_state=str(a.state), modified_state=str(a.out_state),
        original_transition_ns=ORIGINAL_T, delayed_transition_ns=DELAYED_T,
        changed_key_count=len(keys), exact_changed_files=[dict(name=n, original_sha256=originals[n],
            modified_sha256=modified[n], original_bytes=(a.state/n).stat().st_size,
            modified_bytes=(a.out_state/n).stat().st_size) for n in changed],
        original_file_count=len(originals), original_files_mapping_sha256=digest(originals),
        modified_files_mapping_sha256=digest(modified),
        modified_dynamic_input_sha256={p.name:sha(p) for p in sorted(modified_dynamic.iterdir()) if p.is_file()},
        static_sha256={p.name:sha(p) for p in sorted(a.state.iterdir()) if p.is_file()},
        affected_frames=affected_frames, subsequent_changed_key_overrides=future_overrides,
        native_device_identity_sha256=sha(metadata_path), native_interface_count=len(metadata),
        original_selective_schedule_sha256=sha(a.observed_logs.parent/'schedule.csv'),
        original_selective_manifest_sha256=sha(a.observed_logs.parent/'manifest.json'),
        unchanged_forecast_source_sha256=sha(Path(__file__).parent.parent/'orbit-geometry/forward-hints.csv'),
        helper_sha256=sha(Path(__file__)), wall_seconds=time.monotonic()-start,
        checks=dict(only_two_routing_files_changed=True, unchanged_static_and_capacity_inputs=True,
            all_pre75_accumulated_state_equal=True, all_post78_accumulated_state_equal=True,
            no_intervening_key_override=True, every_affected_forward_reverse_path_valid=True,
            all_source_paths_valid_in_both_states=True, actual_interface_types_match_native_file_order=True),
        assumptions=['Original selective forecast/policy schedule stays at T75; it is not reforecast to T78.',
            'Both directional routes/link choices are retained until T78; the intervention is not pure RTT geometry.',
            'Native GSLHelper uses one shared channel with no visibility/range gate; physical feasibility is not proved.',
            'Input validation does not authorize the third simulation; independent and parent review are still required.'])
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(record, indent=2)+'\n', newline='\n')
    print(json.dumps({'receipt':str(a.receipt),'sha256':sha(a.receipt),'wall_seconds':record['wall_seconds'],
                      'changed_files':len(changed),'frames_validated':len(affected_frames),'checks':record['checks']}))


if __name__ == '__main__':
    main()
