#!/usr/bin/env python3
"""Independent post-run audit of the completed Vegas v1 matrix; stdlib only.

Reconstructs renewal history from the state CSV without importing the experiment
analyzer. Prefix checks compare unchanged measurement bytes, not policy traces.
No simulator is invoked. The audit was authored after the recorded source launch.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys

FAMILIES = ('fixed', 'step', 'fixed-comp', 'step-comp', 'leo')
CASES = tuple('v1-' + f + '-' + v for f in FAMILIES for v in ('base', 'renew'))
SOURCE_COMMIT = '82ad34a975d4b15f8a536527f8ea4f0cf6e41624'
PATCH_SHA = '25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59'
IMAGE = 'sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
MSS = 1380
STATE_FIELDS = ('time_ns,vegas_instance,event,base_rtt_ns,cycle_min_rtt_ns,rtt_samples,'
    'cwnd_before_bytes,cwnd_after_bytes,ssthresh_bytes,diff_pkts,cong_state,'
    'renewal_enabled,renewal_rounds,renewal_count,old_base_rtt_ns,recent_min_ns,'
    'history_rounds,history_elapsed_ns,valid_renewal_cycle,ssthresh_before_bytes,'
    'announced_state').split(',')
QUEUE_FIELDS = ('dequeue_time_ns,enqueue_time_ns,sojourn_ns,node_id,device_id,direction,'
    'packet_uid,tagged,flow_id,tx_id,tx_time_ns,packet_bytes').split(',')


def sha_file(path):
    h = hashlib.sha256()
    before = path.stat()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('input changed while hashing: ' + str(path))
    return {'bytes': before.st_size, 'sha256': h.hexdigest()}


def number(row, field):
    v = row[field]
    return int(v) if v != '' else None


class Audit:
    def __init__(self, root):
        self.root = root
        self.errors = []
        self.inputs = {}
        self.manifests = {}
        self.case_summaries = {}
        self.renewal_rows = {}

    def check(self, condition, message):
        if not condition:
            self.errors.append(message)

    def receipt(self, path):
        key = str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
        if key not in self.inputs:
            self.inputs[key] = sha_file(path)
        return self.inputs[key]

    def load_manifests(self):
        matrix_path = self.root / 'matrix-v1.json'
        matrix = json.loads(matrix_path.read_text())
        self.receipt(matrix_path)
        self.check(matrix['status'] == 'complete', 'matrix is not complete')
        declarations = {r['case']: r for r in matrix['declared_tasks_before_launch']}
        completions = {r['case']: r for r in matrix['results']}
        self.check(set(declarations) == set(CASES), 'declared matrix case set differs')
        self.check(set(completions) == set(CASES), 'completed matrix case set differs')
        self.check(all(r['runner_exit_code'] == 0 for r in completions.values()),
                   'matrix contains a failed runner')
        for name in CASES:
            path = self.root / name / 'case.json'
            m = json.loads(path.read_text())
            self.receipt(path)
            self.manifests[name] = m
            self.check(m['status'] == 'complete' and m['exit_code'] == 0,
                       name + ': case incomplete')
            self.check(m['source_commit'] == SOURCE_COMMIT and not m['source_worktree_dirty'],
                       name + ': launch commit/cleanliness differs')
            self.check(m['patch_sha256'] == PATCH_SHA and m['official_image_digest'] == IMAGE,
                       name + ': patch/image differs')
            policy = m['policy']
            self.check(policy['recent_min_renewal'] == name.endswith('-renew') and
                       policy['rounds'] == 20 and policy['min_rise_ns'] == 1000000 and
                       (policy['alpha'], policy['beta'], policy['gamma']) == (2, 4, 1),
                       name + ': declared policy differs')
            for filename in ('config_driver.json', 'config_ns3.properties'):
                q = self.root / name / filename
                if q.exists():
                    self.check(self.receipt(q)['sha256'] == m[filename + '_sha256'],
                               name + ': actual config hash differs: ' + filename)
            if m['parameters']['kind'] == 'micro':
                actual = m['actual_driver_settings_checked']
                config = json.loads((self.root / name / 'config_driver.json').read_text())
                self.check(all(config[k] == v for k, v in actual.items()),
                           name + ': recorded actual driver settings differ from saved config')
                self.check(actual['duration_ns'] == 200000000000 and
                           actual['event_ns'] == 100000000000 and
                           actual['before_one_way_delay_ns'] == 45000000 and
                           actual['after_one_way_delay_ns'] ==
                           (48000000 if '-step' in name else 45000000),
                           name + ': actual micro duration/propagation differs')
            # Verify the installed simulator and micro driver used by this audit.
            # Other analysis helpers may have been edited after the simulation;
            # their launch hashes remain in the original immutable case.json.
            for source in m['sources']:
                if source['path'].startswith('/home/ubuntu/ns-3.48/'):
                    q = Path(source['path'])
                    actual_source = self.receipt(q)
                    self.check(actual_source == {'bytes': source['bytes'],
                                                  'sha256': source['sha256']},
                               name + ': installed simulator source differs: ' + str(q))
        # This source check is for reading the mechanism, not a new launch claim.

    def audit_state(self, name):
        path = self.root / name / 'logs_ns3/vegas_state.csv'
        self.receipt(path)
        policy = self.manifests[name]['policy']
        states = {}
        renewals = []
        counts = collections.Counter()
        clears = collections.Counter()
        start_errors = len(self.errors)
        previous_time = -1
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            self.check(reader.fieldnames == STATE_FIELDS, name + ': state schema differs')
            for line, row in enumerate(reader, 2):
                label = f'{name}:state:{line}'
                self.check(None not in row and all(v is not None for v in row.values()),
                           label + ': malformed field count')
                n = lambda field: number(row, field)
                t, inst, ev = n('time_ns'), n('vegas_instance'), row['event']
                self.check(t >= previous_time, label + ': nonmonotonic timestamp')
                previous_time = t
                counts[ev] += 1
                st = states.setdefault(inst, {'active': False, 'history': [],
                                              'count': 0, 'pending': None})
                enabled, rounds = bool(n('renewal_enabled')), n('renewal_rounds')
                self.check(enabled == policy['recent_min_renewal'] and
                           rounds == policy['rounds'], label + ': trace policy differs')
                mi, base = n('cycle_min_rtt_ns'), n('base_rtt_ns')
                before, after = n('cwnd_before_bytes'), n('cwnd_after_bytes')
                samples, old, recent = n('rtt_samples'), n('old_base_rtt_ns'), n('recent_min_ns')
                valid = (st['active'] and n('cong_state') == 0 and
                         before >= n('ssthresh_before_bytes') and samples > 2 and
                         mi is not None and mi > 0 and base is not None)
                if ev in ('ENABLE', 'DISABLE'):
                    self.check(st['pending'] is None, label + ': transition between RENEW/decision')
                    st['active'] = ev == 'ENABLE'
                    clears[ev] += 1
                    st['history'].clear()
                    self.check(n('announced_state') is not None and
                               ((n('announced_state') == 0) == (ev == 'ENABLE')),
                               label + ': announced state mismatch')
                    self.check(n('valid_renewal_cycle') == 0 and old is None and recent is None,
                               label + ': transition has cycle/renewal fields')
                elif ev == 'RENEW' or ev.startswith('CYCLE_'):
                    self.check(bool(n('valid_renewal_cycle')) == valid,
                               label + ': validity does not reconstruct')
                    self.check(n('announced_state') is None,
                               label + ': decision has announced state')
                    if ev == 'RENEW':
                        self.check(st['pending'] is None and enabled and valid,
                                   label + ': ineligible renewal')
                        st['history'].append((t, mi))
                        st['history'] = st['history'][-rounds:]
                        minimum = min(v for _, v in st['history'])
                        self.check(len(st['history']) == rounds and recent == minimum and
                                   base == recent and old is not None and
                                   recent > old and recent - old >= policy['min_rise_ns'] and
                                   recent <= mi, label + ': renewal value/threshold/history mismatch')
                        self.check(n('history_rounds') == rounds and
                                   n('history_elapsed_ns') == t - st['history'][0][0],
                                   label + ': renewal history size/elapsed mismatch')
                        self.check(before == after and n('diff_pkts') is None,
                                   label + ': RENEW changes cwnd or reports a decision')
                        st['count'] += 1
                        renewals.append({
                            'time_ns': t, 'vegas_instance': inst,
                            'old_base_rtt_ns': old, 'new_base_rtt_ns': base,
                            'cycle_min_rtt_ns': mi, 'history_rounds': rounds,
                            'history_elapsed_ns': n('history_elapsed_ns'),
                            'history_first_time_ns': st['history'][0][0],
                            'cwnd_before_bytes': before,
                            'ssthresh_before_bytes': n('ssthresh_before_bytes'),
                            'rtt_samples': samples, 'renewal_count': st['count']})
                        st['pending'] = (t, recent, before, mi, samples)
                        st['history'].clear()
                    else:
                        if st['pending'] is not None:
                            self.check(st['pending'] == (t, recent, before, mi, samples),
                                       label + ': RENEW/current-cycle decision mismatch')
                            st['pending'] = None
                            # Current cycle was appended exactly once, before RENEW.
                        elif enabled and valid:
                            st['history'].append((t, mi))
                            st['history'] = st['history'][-rounds:]
                            expected_recent = (min(v for _, v in st['history'])
                                               if len(st['history']) == rounds else None)
                            self.check(recent == expected_recent,
                                       label + ': recent minimum field differs')
                            if expected_recent is not None:
                                self.check(not (expected_recent > base and
                                    expected_recent - base >= policy['min_rise_ns']),
                                    label + ': eligible renewal missing')
                        else:
                            clears['INVALID_CYCLE' if not valid else 'POLICY_DISABLED'] += 1
                            st['history'].clear()
                            self.check(recent is None, label + ': invalid/disabled recent minimum')
                        self.check(old is None and n('history_rounds') == len(st['history']) and
                                   n('history_elapsed_ns') ==
                                   (t - st['history'][0][0] if st['history'] else None),
                                   label + ': decision history/elapsed mismatch')
                        expected_event = ('CYCLE_INCREASE' if after > before else
                                          'CYCLE_DECREASE' if after < before else 'CYCLE_HOLD')
                        self.check(ev == expected_event, label + ': decision label mismatch')
                        if samples > 2:
                            self.check(base is not None and mi is not None and mi > 0 and
                                       base <= mi, label + ': baseline <= cycle minimum violated')
                            w = before // MSS
                            expected_diff = w - int(w * ((base / 1e9) / (mi / 1e9)))
                            self.check(n('diff_pkts') == expected_diff,
                                       label + ': Vegas diff does not reconstruct')
                        else:
                            self.check(n('diff_pkts') is None,
                                       label + ': insufficient-sample cycle has diff')
                else:
                    self.check(False, label + ': unknown event ' + ev)
                self.check(n('renewal_count') == st['count'],
                           label + ': renewal count mismatch')
                if ev in ('ENABLE', 'DISABLE'):
                    self.check(n('history_rounds') == 0 and n('history_elapsed_ns') is None,
                               label + ': transition did not clear history')
        self.check(all(st['pending'] is None for st in states.values()),
                   name + ': RENEW without following decision at EOF')
        self.renewal_rows[name] = renewals
        result = {'rows': sum(counts.values()), 'event_counts': dict(counts),
                  'history_clear_reasons': dict(clears),
                  'instances': sorted(states), 'renewals': renewals,
                  'errors': len(self.errors) - start_errors}
        self.case_summaries[name] = result
        return result

    def queue_windows(self, name):
        rows = self.renewal_rows[name]
        first = rows[0]
        maximum = max(rows, key=lambda r: r['new_base_rtt_ns'])
        selections = [('first_renewal_before_route_event', first),
                      ('maximum_renewed_base', maximum)]
        windows = []
        for title, row in selections:
            lo, hi = row['history_first_time_ns'], row['time_ns']
            prop = 90000000 if name == 'v1-fixed-comp-renew' or hi < 100000000000 else 96000000
            windows.append({'selection': title, 'renewal': row, 'dequeue_window_ns': [lo, hi],
                            'physical_propagation_rtt_ns': prop,
                            'new_base_minus_physical_propagation_ns': row['new_base_rtt_ns'] - prop,
                            'forward_sojourn_by_flow': {}})
        self.check(first['time_ns'] < 100000000000,
                   name + ': first selected renewal not before route event')
        q = self.root / name / 'logs_ns3/queue_sojourn.csv'
        before = q.stat()
        full_hash = hashlib.sha256()
        with q.open('rb') as stream:
            header = stream.readline()
            full_hash.update(header)
            self.check(header.decode().strip().split(',') == QUEUE_FIELDS,
                       name + ': queue schema differs')
            for raw in stream:
                full_hash.update(raw)
                fields = raw.rstrip(b'\r\n').split(b',')
                self.check(len(fields) == len(QUEUE_FIELDS), name + ': malformed queue row')
                t = int(fields[0])
                if fields[5] != b'forward':
                    continue
                matching = [w for w in windows if w['dequeue_window_ns'][0] <= t < w['dequeue_window_ns'][1]]
                if not matching:
                    continue
                sojourn, enqueue = int(fields[2]), int(fields[1])
                self.check(sojourn == t - enqueue and sojourn >= 0,
                           name + ': queue time identity mismatch')
                flow = fields[8].decode() if fields[7] == b'1' else 'untagged'
                for window in matching:
                    a = window['forward_sojourn_by_flow'].setdefault(flow,
                        {'count': 0, 'sum_ns': 0, 'min_ns': sojourn, 'max_ns': sojourn, 'zero_count': 0})
                    a['count'] += 1
                    a['sum_ns'] += sojourn
                    a['min_ns'] = min(a['min_ns'], sojourn)
                    a['max_ns'] = max(a['max_ns'], sojourn)
                    a['zero_count'] += int(sojourn == 0)
        after = q.stat()
        self.check((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                   name + ': queue input changed')
        self.inputs[str(q.relative_to(self.root))] = {'bytes': before.st_size, 'sha256': full_hash.hexdigest()}
        for window in windows:
            for a in window['forward_sojourn_by_flow'].values():
                a['mean_ns'] = a['sum_ns'] / a['count']
        return windows

    def prefix(self, path, cutoff):
        before = path.stat()
        full_hash, prefix_hash = hashlib.sha256(), hashlib.sha256()
        total_bytes = prefix_bytes = rows = prefix_rows = 0
        last_t = -1
        with path.open('rb') as stream:
            first = stream.readline()
            is_headerless = path.name.endswith(('_cwnd.csv', '_rtt.csv', '_progress.csv'))
            if is_headerless:
                time_index = 1
                data = first
            else:
                header = first.rstrip(b'\r\n').split(b',')
                self.check(b'time_ns' in header, str(path) + ': missing time_ns')
                time_index = header.index(b'time_ns')
                full_hash.update(first)
                prefix_hash.update(first)
                total_bytes += len(first)
                prefix_bytes += len(first)
                data = None
            for raw in ([data] if data is not None else []):
                full_hash.update(raw)
                total_bytes += len(raw)
                rows += 1
                t = int(raw.split(b',', time_index + 1)[time_index])
                self.check(t >= last_t, str(path) + ': nonmonotonic prefix source')
                last_t = t
                if cutoff is None or t < cutoff:
                    prefix_hash.update(raw); prefix_bytes += len(raw); prefix_rows += 1
            for raw in stream:
                full_hash.update(raw)
                total_bytes += len(raw)
                rows += 1
                t = int(raw.split(b',', time_index + 1)[time_index])
                self.check(t >= last_t, str(path) + ': nonmonotonic prefix source')
                last_t = t
                if cutoff is None or t < cutoff:
                    prefix_hash.update(raw); prefix_bytes += len(raw); prefix_rows += 1
        after = path.stat()
        self.check((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and
                   total_bytes == before.st_size, str(path) + ': prefix input changed')
        receipt = {'bytes': total_bytes, 'sha256': full_hash.hexdigest()}
        self.inputs[str(path.relative_to(self.root))] = receipt
        return {'all_rows': rows, 'prefix_rows': prefix_rows, 'prefix_bytes': prefix_bytes,
                'prefix_sha256': prefix_hash.hexdigest()}

    def prefix_pair(self, family):
        base_name, renew_name = 'v1-' + family + '-base', 'v1-' + family + '-renew'
        b, r = self.root / base_name / 'logs_ns3', self.root / renew_name / 'logs_ns3'
        renewal_rows = self.renewal_rows[renew_name]
        cutoff = min(x['time_ns'] for x in renewal_rows) if renewal_rows else None
        names = sorted(p.name for p in b.glob('*.csv') if p.name.startswith(('tcp_flow_', 'study_rx_', 'study_app_rx_'))
                       or p.name == 'study_drops.csv')
        self.check(names == sorted(p.name for p in r.glob('*.csv') if p.name.startswith(('tcp_flow_', 'study_rx_', 'study_app_rx_'))
                                  or p.name == 'study_drops.csv'), family + ': measurement trace set differs')
        files = []
        for filename in names:
            left, right = self.prefix(b / filename, cutoff), self.prefix(r / filename, cutoff)
            match = all(left[k] == right[k] for k in ('prefix_rows', 'prefix_bytes', 'prefix_sha256'))
            self.check(match, family + ': pre-renewal measurement prefix differs: ' + filename)
            files.append({'file': filename, 'base': left, 'renew': right, 'match': match})
        coverage = 'study_drop_coverage.csv'
        left, right = self.receipt(b / coverage), self.receipt(r / coverage)
        match = left == right
        self.check(match, family + ': timeless drop coverage differs')
        files.append({'file': coverage, 'comparison': 'whole_file_timeless_coverage', 'match': match})
        return {'family': family, 'baseline_case': base_name, 'renewal_case': renew_name,
                'cutoff_ns_exclusive': cutoff,
                'selection': 'all bytes for no-renewal pair' if cutoff is None else '[0, first RENEW time_ns)',
                'files_checked': len(files), 'all_match': all(x['match'] for x in files), 'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/tmp/cs30401-vegas'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    audit = Audit(args.root)
    audit.load_manifests()
    for name in CASES:
        audit.audit_state(name)
    queues = {name: audit.queue_windows(name) for name in ('v1-fixed-comp-renew', 'v1-step-comp-renew')}
    prefixes = [audit.prefix_pair(family) for family in FAMILIES]
    result = {
        'schema_version': 1, 'audit_scope': 'internal independent AI review of existing completed v1 traces; no simulation',
        'argv': sys.argv, 'script': {'path': str(Path(__file__).resolve()), **sha_file(Path(__file__))},
        'simulation_source_commit': SOURCE_COMMIT, 'simulation_patch_sha256': PATCH_SHA,
        'official_image_digest_declared_by_launch_manifests': IMAGE,
        'state_method': 'Per Vegas instance: reconstruct ENABLE/DISABLE and history; append current valid cycle once, cap last 20; on RENEW verify all history values, min/rise/count and elapsed, clear then consume same-time decision without reappend; recompute diff from 1380-byte MSS and original double-seconds ratio.',
        'queue_method': 'Forward dequeues in [first history timestamp, RENEW timestamp); aggregate exact sojourn = dequeue - enqueue by tagged flow, retain raw SHA. These descriptive windows do not join every SRTT callback to a packet or prove the queue never emptied.',
        'prefix_method': 'All rows of each selected raw measurement CSV are scanned and monotonic time verified. Original header/row bytes with time_ns < first RENEW time form each SHA+size/count receipt; no row normalization or policy-column removal. No-renewal fixed pair uses whole files. Timeless drop coverage uses full hash.',
        'summary': {'case_count': len(CASES),
                    'state_rows': sum(c['rows'] for c in audit.case_summaries.values()),
                    'renewals': sum(len(c['renewals']) for c in audit.case_summaries.values()),
                    'prefix_pairs': len(prefixes), 'prefix_files_checked': sum(c['files_checked'] for c in prefixes),
                    'all_prefix_checks_match': all(c['all_match'] for c in prefixes),
                    'error_count': len(audit.errors)},
        'cases': audit.case_summaries, 'competition_queue_windows': queues, 'prefix_checks': prefixes,
        'input_receipts': audit.inputs, 'errors': audit.errors,
        'limitations': [
            'This audit validates recorded rule application, not the correctness of propagation estimation or a universally better TCP.',
            'Twenty valid ACK-boundary cycles are not exactly twenty RTTs or independent samples; the input remains socket SRTT.',
            'A pre-renewal byte match bounds observer/startup equality only to its recorded cutoff. LEO renewal begins at 2.295799001 s in this matrix, so whole-run gains include early congestion-avoidance reference changes.',
            'Competitor window queue sojourn is descriptive. Positive samples do not establish continuous queue occupancy or causal attribution for every RTT sample.',
            'Fixed propagation plus raised reference demonstrates queue absorption; the policy cannot generally distinguish propagation increases from persistent congestion.',
            'Queue summary drop counters omit upstream TrafficControl drops; use study_drops.csv for loss evidence.',
            'case.json records launch sources. This post-run script has its own hash and was added after that launch; it is not part of commit 82ad34a.',
            'Fresh deterministic replay is a separate receipt; neither replay nor this audit creates independent statistical replications.'
        ]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'out': str(args.out), 'output': sha_file(args.out), 'script': result['script'], **result['summary']}, sort_keys=True))
    return 1 if audit.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
