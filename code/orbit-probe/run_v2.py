#!/usr/bin/env python3
"""Execute the two predeclared V2 rise140 semantic-gate-repair cases."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NS3 = Path('/home/ubuntu/ns-3.48')
STATE = Path('/home/ubuntu/lab/data/seoul_london/state')
TRUTH = REPO / 'code/kim-study/path_truth_200s.csv'
CASES = {f'{family}-{mode}': dict(observe=True, starts=[start], policy=mode == 'on', duration=duration)
         for family, start, duration in [('v2-rise140', 105, 140)] for mode in ('off', 'on')}
WINDOWS = {'v2-rise140': {'whole': [0, 140], 'active': [105, 140], 'pre': [116.6, 121.6], 'post': [121.6, 126.6], 'late': [131.6, 136.6]}}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(*args, cwd=REPO):
    return subprocess.check_output(['git', '-c', f'safe.directory={cwd}', *args], cwd=cwd).strip()


def execute(name, root):
    definition = CASES[name]
    ready_path = HERE / 'build-ready-v2.json'
    ready = json.loads(ready_path.read_text())
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            words = [w.decode() for w in (process / 'cmdline').read_bytes().split(b'\0') if w]
            if words and Path(words[0]).name in ('cmake', 'ninja', 'g++', 'c++', 'cc1plus') and (process / 'cwd').resolve().is_relative_to(NS3):
                raise ValueError('Pending ns-3 build: refuse simulation launch')
        except (FileNotFoundError, ProcessLookupError):
            pass
    if ready['patch_sha256'] != sha(HERE / 'ns3-v2.patch'):
        raise ValueError('Compiled build receipt does not match patch')
    actual_runtime = {str(path.relative_to(NS3 / 'build')): sha(path) for path in [NS3 / 'build/scratch/main_satnet/ns3.48-main_satnet', *sorted((NS3 / 'build/lib').glob('*.so'))]}
    if actual_runtime != ready['runtime_files']:
        raise ValueError('Compiled build receipt differs from actual runtime')
    run = root / name
    run.mkdir(parents=True, exist_ok=False)
    subprocess.run(['bash', '/home/ubuntu/lab/scripts/make_run.sh', str(run), str(STATE),
                    'TcpBbr', '100', '100', str(definition['duration']), '1584', '1585'], check=True, capture_output=True)
    (run / 'schedule.csv').write_text(f"0,1584,1585,100000000000,{definition['starts'][0] * 10**9},,\n")
    hints = []
    with TRUTH.open(newline='') as source:
        rows = list(csv.DictReader(source))
    for old, new in zip(rows, rows[1:]):
        before, after, event = Decimal(old['rtt_prop_ms']), Decimal(new['rtt_prop_ms']), Decimal(new['t_s'])
        if new['path_changed'] != '1' or abs(after - before) < 1 or event < definition['starts'][0] or event >= definition['duration']:
            continue
        event_ns, wait_ns = int(event * 10**9), int(2 * max(before, after) * 10**6)
        hints.append(dict(event_ns=event_ns, ready_ns=event_ns + wait_ns, old_prop_rtt_ms=float(before), new_prop_rtt_ms=float(after)))
    forecast = run / 'forecast.txt'
    forecast.write_text(''.join(f"{h['event_ns']} {h['ready_ns']}\n" for h in hints))
    binary = NS3 / 'build/scratch/main_satnet/ns3.48-main_satnet'
    patch = HERE / 'ns3-v2.patch'
    source_diff = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=NS3)
    if source_diff != patch.read_bytes():
        raise ValueError('Installed source differs from exported combined patch')
    env = dict(os.environ, CS30401_BBR_OBSERVE='1', CS30401_BBR_OBSERVE_DIR=str(run / 'logs_ns3'),
               CS30401_ORBIT_FORECAST=str(forecast), LD_LIBRARY_PATH=str(NS3 / 'build/lib'))
    command = [str(binary), f'--run_dir={run}', f"--ns3::TcpBbr::OrbitProbe={'true' if definition['policy'] else 'false'}"]
    record = dict(case=name, definition=definition, status='running', command=command,
                  repo_commit=git('rev-parse', 'HEAD').decode(), repo_dirty=bool(git('status', '--porcelain')),
                  runner_sha256=sha(__file__), build_ready_sha256=sha(ready_path), patch_sha256=sha(patch), installed_diff_sha256=hashlib.sha256(source_diff).hexdigest(),
                  ns3_head=git('rev-parse', 'HEAD', cwd=NS3).decode(),
                  runtime_files={str(p.relative_to(NS3 / 'build')): sha(p) for p in [binary, *sorted((NS3 / 'build/lib').glob('*.so'))]},
                  state_static_sha256={p.name: sha(p) for p in sorted(STATE.iterdir()) if p.is_file()},
                  dynamic_state_sha256={p.name: sha(p) for p in sorted((STATE / 'dynamic_state_100ms_for_200s').iterdir()) if p.is_file()},
                  forecast_source_sha256=sha(TRUTH), forecast_sha256=sha(forecast), hints=hints,
                  config_sha256=sha(run / 'config_ns3.properties'), schedule_sha256=sha(run / 'schedule.csv'),
                  environment={k: env[k] for k in ('CS30401_BBR_OBSERVE', 'CS30401_BBR_OBSERVE_DIR', 'CS30401_ORBIT_FORECAST', 'LD_LIBRARY_PATH')},
                  sim_seconds=definition['duration'], rate_mbps=100, queue_packets=100, seed=123456789,
                  windows=WINDOWS[name.rsplit('-', 1)[0]], timeout_seconds=240,
                  declared_image_digest='ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4')
    manifest = run / 'manifest.json'
    manifest.write_text(json.dumps(record, indent=2) + '\n')
    started = time.monotonic()
    try:
        with (run / 'console.txt').open('w') as output:
            result = subprocess.run(command, env=env, cwd=NS3, stdout=output, stderr=subprocess.STDOUT, timeout=240)
        record.update(status='success' if result.returncode == 0 else 'failed', returncode=result.returncode)
    except subprocess.TimeoutExpired:
        record.update(status='timeout', returncode=None)
    record['wall_seconds'] = time.monotonic() - started
    record['runtime_sha_unchanged_after_run'] = all(sha(NS3 / 'build' / key) == value for key, value in record['runtime_files'].items())
    if not record['runtime_sha_unchanged_after_run']:
        record['status'] = 'runtime-mismatch'
    header = (run / 'logs_ns3/orbit_probe.csv').open().readline().strip().split(',') if (run / 'logs_ns3/orbit_probe.csv').exists() else []
    record['v2_trace_header_verified'] = 'last_probe_complete_ns' in header and 'cong_state' in header
    if record['status'] == 'success' and not record['v2_trace_header_verified']:
        record['status'] = 'unsupported-trace'
    record['outputs'] = {str(p.relative_to(run)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted((run / 'logs_ns3').glob('*')) if p.is_file()}
    manifest.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record[k] for k in ('case', 'status', 'wall_seconds')}), flush=True)
    if record['status'] != 'success':
        raise SystemExit(f'Incomplete run: {run}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cases', nargs='+', choices=CASES)
    p.add_argument('--root', type=Path, default=Path('/tmp/orbit-probe'))
    a = p.parse_args()
    for name in a.cases:
        execute(name, a.root)


if __name__ == '__main__':
    main()
