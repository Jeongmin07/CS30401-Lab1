"""Recalculate the first-loss evidence in retained same-start DD/GD traces.

This reads existing logs only. It does not run ns-3 or explain the eventual
whole-run delivery shares. The intended inputs are same-start-dd and
same-start-gd produced by run_competing.py with the canonical patch.
"""

import argparse
import collections
import csv
import hashlib
import itertools
import json
from pathlib import Path


SEMANTICS = {
    'sender': ('time_ns', 'flow_id', 'event', 'seq', 'ack', 'payload_bytes',
               'flags', 'sack_blocks', 'cong_state', 'local_port', 'peer_port'),
    'receiver': ('time_ns', 'node_id', 'connection_id', 'local_port',
                 'peer_ip', 'peer_port', 'flow_id', 'seq', 'ack',
                 'payload_bytes', 'flags', 'expected_seq'),
    'application': ('time_ns', 'node_id', 'connection_id', 'local_port',
                    'peer_ip', 'peer_port', 'flow_id', 'payload_bytes',
                    'connection_total_rx_bytes', 'sink_total_rx_bytes'),
    'congestion': ('time_ns', 'flow_id', 'event', 'old_value', 'new_value', 'cong_state'),
    'drop': ('time_ns', 'layer', 'node', 'device', 'reason', 'src', 'dst',
             'src_port', 'dst_port', 'seq', 'payload_bytes', 'flags', 'flow_id'),
}
RX_FILE = 'study_rx_node_1585_port_1024.csv'
APP_FILE = 'study_app_rx_node_1585_port_1024.csv'


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def rows(path, kind=None):
    with Path(path).open(newline='', encoding='utf-8') as source:
        for line, row in enumerate(csv.DictReader(source), 2):
            if kind == 'congestion' and row['event'] not in ('CONG', 'SSTHRESH'):
                continue
            yield {'line': line, 'row': row}


def first_difference(baseline, guarded, filename, kind):
    fields = SEMANTICS[kind]
    left = rows(baseline / 'logs_ns3' / filename, kind)
    right = rows(guarded / 'logs_ns3' / filename, kind)
    previous_left = collections.deque(maxlen=2)
    previous_right = collections.deque(maxlen=2)
    count = 0
    for a, b in itertools.zip_longest(left, right):
        key_a = None if a is None else tuple(a['row'].get(key) for key in fields)
        key_b = None if b is None else tuple(b['row'].get(key) for key in fields)
        if key_a != key_b:
            return {'file': filename, 'kind': kind, 'comparison_fields': fields,
                    'equal_semantic_rows': count, 'baseline': a, 'guarded': b,
                    'different_fields': list(fields) if a is None or b is None else
                    [key for key in fields if a['row'].get(key) != b['row'].get(key)],
                    'preceding_baseline': list(previous_left),
                    'preceding_guarded': list(previous_right),
                    'following_baseline': list(itertools.islice(left, 2)),
                    'following_guarded': list(itertools.islice(right, 2))}
        count += 1
        previous_left.append(a)
        previous_right.append(b)
    return {'file': filename, 'kind': kind, 'comparison_fields': fields,
            'equal_semantic_rows': count, 'identical_semantics': True}


def connections(run):
    found = {}
    totals = collections.Counter()
    for item in rows(run / 'logs_ns3' / APP_FILE):
        row = item['row']
        key = (row['node_id'], row['local_port'], row['connection_id'])
        identity = (row['flow_id'], row['peer_ip'], row['peer_port'])
        if key in found and found[key] != identity:
            raise ValueError('Receiver connection mapping changed within a trace.')
        found[key] = identity
        totals[key] += int(row['payload_bytes'])
        if totals[key] != int(row['connection_total_rx_bytes']):
            raise ValueError('Receiver per-connection cumulative bytes disagree with payload sums.')
    if len(found) != 2 or {value[0] for value in found.values()} != {'0', '1'}:
        raise ValueError('Expected exactly two independently mapped receiver connections.')
    return [{'node': key[0], 'local_port': key[1], 'connection_id': key[2],
             'flow_id': value[0], 'peer_ip': value[1], 'peer_port': value[2],
             'application_bytes': totals[key]} for key, value in sorted(found.items())]


def selected_loss(run, sequence, divergence_ns):
    packet_path = run / 'logs_ns3' / 'tcp_flow_0_study_packets.csv'
    transmissions = [item for item in rows(packet_path)
                     if item['row']['seq'] == sequence and int(item['row']['payload_bytes']) > 0
                     and item['row']['event'] in ('TX', 'RETX')]
    original = next(item for item in transmissions if item['row']['event'] == 'TX')
    repair = next(item for item in transmissions
                  if item['row']['event'] == 'RETX'
                  and int(item['row']['time_ns']) >= divergence_ns)
    if int(original['row']['time_ns']) >= divergence_ns:
        raise ValueError('Selected original transmission does not precede the divergence.')
    tag = (original['row']['tx_id'], original['row']['tx_time_ns'])
    repair_tag = (repair['row']['tx_id'], repair['row']['tx_time_ns'])
    drops = [item for item in rows(run / 'logs_ns3' / 'study_drops.csv')
             if item['row']['flow_id'] == '0'
             and (item['row']['tx_id'], item['row']['tx_time_ns']) == tag]
    if not drops:
        raise ValueError('The selected original has no directly matched network drop trace.')
    if any(item['row']['seq'] != sequence for item in drops):
        raise ValueError('Drop tag matches but sequence differs.')
    original_wire, repair_wire, next_wire = [], None, None
    for item in rows(run / 'logs_ns3' / RX_FILE):
        row = item['row']
        if row['flow_id'] != '0':
            continue
        wire_tag = (row['tx_id'], row['tx_time_ns'])
        if wire_tag == tag:
            original_wire.append(item)
        if repair_wire is not None and next_wire is None:
            next_wire = item
        if wire_tag == repair_tag:
            if row['seq'] != sequence:
                raise ValueError('Repair receiver tag matches but sequence differs.')
            repair_wire = item
    if repair_wire is None:
        raise ValueError('No receiver row matches the selected retransmission tag.')
    receive_time = repair_wire['row']['time_ns']
    app = [item for item in rows(run / 'logs_ns3' / APP_FILE)
           if item['row']['flow_id'] == '0' and item['row']['time_ns'] == receive_time]
    if not app or sum(int(item['row']['payload_bytes']) for item in app) <= 0:
        raise ValueError('No positive same-time ordered application delivery confirms this repair.')
    if int(repair_wire['row']['expected_seq']) != int(sequence):
        raise ValueError('Repair is not at the receiver pre-processing missing sequence.')
    if next_wire is None or int(next_wire['row']['expected_seq']) <= int(sequence):
        raise ValueError('Following receiver row does not confirm expected-sequence advancement.')
    events = [item for item in rows(run / 'logs_ns3' / 'tcp_flow_0_study_events.csv')
              if 26100000000 <= int(item['row']['time_ns']) < 27000000000]
    recovery = next(item for item in events
                    if item['row']['event'] == 'CONG' and item['row']['new_value'] == '3'
                    and int(item['row']['time_ns']) == int(repair['row']['time_ns']))
    ack = next(item for item in rows(packet_path)
               if item['row']['event'] == 'RX_ACK'
               and item['row']['time_ns'] == repair['row']['time_ns'])
    return {'original_transmission': original, 'original_tagged_drop_rows': drops,
            'original_wire_rows_found': original_wire, 'first_matching_retransmission': repair,
            'triggering_ack_observation': ack, 'recovery_state_entry': recovery,
            'matched_repair_receiver_row': repair_wire, 'next_flow0_receiver_row': next_wire,
            'same_time_application_delivery': app,
            'same_time_application_bytes': sum(int(item['row']['payload_bytes']) for item in app),
            'local_threshold_and_congestion_events': events}


def source_evidence():
    root = Path('/home/ubuntu/ns-3.48')
    specs = {
        'src/internet/model/tcp-socket-base.cc': {
            'locators': {'SetRetxThresh': [4708, 4711], 'DupAck_recovery_tests': [1857, 1870],
                         'SACK_duplicate_ACK_definition': [2066, 2083], 'EnterRecovery': [1714, 1764]}},
        'src/internet/model/tcp-tx-buffer.cc': {'locators': {'UpdateLostCount': [866, 909]}},
        'src/traffic-control/model/traffic-control-layer.cc': {'locators': {'stopped_queue_TcDrop': [373, 390]}},
        'contrib/basic-sim/model/apps/tcp-flow-sink.cc': {
            'locators': {'pre_processing_expected_seq': [203, 233], 'ordered_application_delivery': [236, 261]}},
    }
    for name, entry in specs.items():
        path = root / name
        entry['path'] = str(path)
        entry['available'] = path.is_file()
        if path.is_file():
            entry['sha256'] = digest(path)
    return {'root': str(root), 'qualification': 'Locators refer to the retained canonical course source; hashes identify the inspected files.',
            'files': specs}


def audit(baseline, guarded):
    manifests = [json.loads((run / 'case.json').read_text(encoding='utf-8'))
                 for run in (baseline, guarded)]
    for manifest in manifests:
        if manifest['status'] != 'complete' or manifest['exit_code'] != 0:
            raise ValueError('Both input simulations must have completed successfully.')
    for key in ('patch_sha256', 'binary_sha256', 'config_ns3.properties_sha256'):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError('The compared run manifests disagree on ' + key)
    if digest(baseline / 'config_ns3.properties') != digest(guarded / 'config_ns3.properties'):
        raise ValueError('The input configuration files differ.')
    schedules = []
    for run in (baseline, guarded):
        with (run / 'schedule.csv').open(newline='') as source:
            schedules.append(list(csv.reader(source)))
    for schedule in schedules:
        if len(schedule) != 2 or any(row[:5] != [str(fid), '1584', '1585', '100000000000', '0']
                                     for fid, row in enumerate(schedule)):
            raise ValueError('This audit requires the declared same-start, same-direction bulk pair.')
    if schedules[0][0][5] or schedules[0][1][5] or schedules[1][1][5] or not schedules[1][0][5]:
        raise ValueError('Expected baseline DD and guarded GD AdditionalParameters.')

    specs = [('tcp_flow_0_study_packets.csv', 'sender'),
             ('tcp_flow_1_study_packets.csv', 'sender'),
             (RX_FILE, 'receiver'), (APP_FILE, 'application'),
             ('tcp_flow_0_study_events.csv', 'congestion'),
             ('tcp_flow_1_study_events.csv', 'congestion'), ('study_drops.csv', 'drop')]
    differences = [first_difference(baseline, guarded, name, kind) for name, kind in specs]
    first_sender = differences[0]
    if first_sender.get('identical_semantics'):
        raise ValueError('No flow-0 packet divergence found.')
    first = first_sender['baseline']['row']
    divergence_ns = int(first['time_ns'])
    if divergence_ns < 26100000000:
        raise ValueError('Protocol behavior diverges before the first guard activation.')
    if first['event'] != 'TX':
        raise ValueError('Expected the first baseline packet divergence to be a retransmission TX.')
    selected = [selected_loss(run, first['seq'], divergence_ns) for run in (baseline, guarded)]
    original_fields = ('flow_id', 'time_ns', 'seq', 'payload_bytes', 'tx_id', 'tx_time_ns')
    if any(selected[0]['original_transmission']['row'][key] != selected[1]['original_transmission']['row'][key]
           for key in original_fields):
        raise ValueError('The selected original differs between runs.')
    baseline_loss, guarded_loss = selected
    input_hashes = {}
    for label, run in (('baseline', baseline), ('guarded', guarded)):
        files = [run / name for name in ('case.json', 'config_ns3.properties', 'schedule.csv')]
        files.extend(run / 'logs_ns3' / name for name, _ in specs)
        input_hashes[label] = [{'path': str(path.relative_to(run)), 'bytes': path.stat().st_size,
                                'sha256': digest(path)} for path in files]
    return {'schema_version': 1, 'baseline': str(baseline), 'guarded': str(guarded),
            'audit_script_sha256': digest(__file__),
            'input_source_commits': {label: manifest['source_commit'] for label, manifest in
                                    zip(('baseline', 'guarded'), manifests)},
            'comparison_policy': {
                'excluded_metadata': ['threshold', 'packet_uid', 'uid', 'tx_id', 'tx_time_ns'],
                'threshold_reason': 'Scheduled K changes are the intervention, not a transport-behavior divergence.',
                'identity_reason': 'Packet UID and generated transmission tags are not transport behavior; full rows retain them for evidence joins.',
                'congestion_events': 'Compare only CONG/SSTHRESH; record threshold lifecycle separately.',
                'tag_join': 'Match original/drop/repair by flow_id plus tx_id and tx_time_ns; never use packet UID.'},
            'connection_mapping': {'baseline': connections(baseline), 'guarded': connections(guarded)},
            'first_semantic_differences': differences,
            'selected_sequence': first['seq'], 'selected_loss': {'baseline': baseline_loss, 'guarded': guarded_loss},
            'measured_differences': {
                'recovery_and_retransmission_delay_ns': int(guarded_loss['first_matching_retransmission']['row']['time_ns']) - int(baseline_loss['first_matching_retransmission']['row']['time_ns']),
                'confirmed_ordered_delivery_delay_ns': int(guarded_loss['matched_repair_receiver_row']['row']['time_ns']) - int(baseline_loss['matched_repair_receiver_row']['row']['time_ns']),
                'baseline_same_time_application_bytes': baseline_loss['same_time_application_bytes'],
                'guarded_same_time_application_bytes': guarded_loss['same_time_application_bytes']},
            'input_hashes': input_hashes, 'source_evidence': source_evidence(),
            'limitations': [
                'This validates a local actual-loss repair delay after the first guard activation; it does not explain the eventual whole-run delivery-share difference.',
                'No new simulation, parameter sweep, or independent statistical sample is generated.',
                'A TcDrop row identifies traffic-control rejection at the recorded node; this trace uses a sentinel device index and does not identify the outgoing device.',
                'Receiver expected_seq is recorded before TCP processing; acceptance is supported separately by same-time ordered application delivery and subsequent expected_seq advancement.',
                'App packet UID may refer to coalesced bytes and is not joined to a wire packet.',
                'Both duplicate-ACK and SACK presumed-loss thresholds change; existing traces do not separately expose which recovery predicate fired.',
                'Following cross-flow timing and congestion differences are observations, not a proof that this single delay accounts for all later interactions.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--guarded', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Refusing to overwrite existing audit output: ' + str(args.out))
    result = audit(args.baseline, args.guarded)
    with args.out.open('x', encoding='utf-8') as target:
        target.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'output': str(args.out), 'selected_sequence': result['selected_sequence'],
                      'measured_differences': result['measured_differences']}, indent=2))


if __name__ == '__main__':
    main()
