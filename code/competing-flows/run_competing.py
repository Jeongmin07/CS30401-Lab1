"""Run two same-direction CUBIC flows inside the official course container.

This runner does not apply patches or build ns-3. Prepare the canonical patch
and binary first; every case stays under /tmp/cs30401-competing/<name>.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


RUN_ROOT = Path('/tmp/cs30401-competing')
OFFICIAL_IMAGE = 'ghcr.io/yeonjong21/cs30401-lab1:2026f-v1'
OFFICIAL_DIGEST = 'sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
MAKE_RUN = Path('/home/ubuntu/lab/scripts/make_run.sh')
BINARY = Path('/home/ubuntu/ns-3.48/build/scratch/main_satnet/ns3.48-main_satnet')
DEFAULT_GUARD = ('study_threshold=20;'
                 'study_windows=26100000000:26500000000|74900000000:75300000000')
FLOW_BYTES = 100000000000


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(run, manifest):
    temporary = run / '.case.json.tmp'
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                         encoding='utf-8')
    temporary.replace(run / 'case.json')


def read_commit(repository):
    result = subprocess.run(
        ['git', '-c', f'safe.directory={repository}', '-C', str(repository),
         'rev-parse', 'HEAD'], check=True, capture_output=True, text=True,
        env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))
    return result.stdout.strip()


def parse_arguments(argv=None):
    script = Path(__file__).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', help='New case name; existing cases are never overwritten.')
    parser.add_argument('--mode', choices=['DD', 'GD', 'DG', 'GG'], default='DD',
                        help='D=default K3, G=scheduled guard; letters label flow 0/1.')
    parser.add_argument('--guard-parameters', default=DEFAULT_GUARD)
    parser.add_argument('--parameters0', default=None,
                        help='Override guard parameters for flow 0 when its mode is G.')
    parser.add_argument('--parameters1', default=None,
                        help='Override guard parameters for flow 1 when its mode is G.')
    parser.add_argument('--start0-s', type=float, default=0)
    parser.add_argument('--start1-s', type=float, default=0)
    parser.add_argument('--rate', type=float, default=10)
    parser.add_argument('--queue', type=int, default=100)
    parser.add_argument('--duration', type=int, default=200)
    parser.add_argument('--state', default='/home/ubuntu/lab/data/seoul_london/state')
    parser.add_argument('--patch', default=str(script.parents[1] / 'kim-study' / 'ns3.patch'))
    parser.add_argument('--source-commit', default=None,
                        help='Repository revision for archive replay without Git; otherwise read HEAD.')
    parser.add_argument('--image-digest', default=os.environ.get('CS30401_IMAGE_DIGEST', OFFICIAL_DIGEST),
                        help='Image digest verified on the host; the container cannot inspect Docker.')
    parser.add_argument('--trace', type=int, choices=[0, 1], default=1)
    args = parser.parse_args(argv)

    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', args.name):
        parser.error('Use an ASCII alphanumeric case name with hyphens/underscores, at most 128 characters.')
    if not math.isfinite(args.rate) or args.rate <= 0:
        parser.error('--rate must be finite and positive.')
    if args.queue <= 0 or not 0 < args.duration <= 200:
        parser.error('--queue must be positive and --duration must be between 1 and 200 seconds.')
    starts = [args.start0_s, args.start1_s]
    if any(not math.isfinite(value) or not 0 <= value < args.duration for value in starts):
        parser.error('Both flow starts must be finite, nonnegative, and before simulation end.')
    start_ns = [round(value * 1e9) for value in starts]
    if any(value >= args.duration * 1000000000 for value in start_ns):
        parser.error('A rounded flow start reaches simulation end.')
    if start_ns[0] > start_ns[1]:
        parser.error('The course scheduler requires start0 <= start1; swap GD/DG to exchange roles.')
    if args.source_commit is not None and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', args.source_commit):
        parser.error('--source-commit must be a full hexadecimal Git commit ID.')
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', args.image_digest):
        parser.error('--image-digest must have the form sha256:<64 hexadecimal digits>.')

    flows = []
    for flow_id, role in enumerate(args.mode):
        override = getattr(args, f'parameters{flow_id}')
        if role == 'D':
            if override not in (None, ''):
                parser.error(f'Flow {flow_id} is D; nonempty parameters would contradict --mode.')
            parameters = ''
        else:
            parameters = args.guard_parameters if override is None else override
            if any(character in parameters for character in ',\r\n'):
                parser.error('Flow parameters must fit one unquoted scheduler CSV column.')
            controls = dict(token.split('=', 1) for token in parameters.split(';') if '=' in token)
            try:
                threshold = int(controls.get('study_threshold', '3'))
            except ValueError:
                parser.error('A G flow requires an integer study_threshold > 3.')
            if threshold <= 3 or not controls.get('study_windows'):
                parser.error('A G flow requires study_threshold > 3 and nonempty study_windows.')
        flows.append({'flow_id': flow_id, 'role': role, 'source_node': 1584,
                      'destination_node': 1585, 'size_bytes': FLOW_BYTES,
                      'start_ns': start_ns[flow_id], 'additional_parameters': parameters})
    return args, flows


def main(argv=None):
    args, flows = parse_arguments(argv)
    script = Path(__file__).resolve()
    run = RUN_ROOT / args.name
    if RUN_ROOT.is_symlink() or run.resolve() != run:
        raise SystemExit('Refusing a symlink in the fixed output path.')
    try:
        run.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f'Refusing to overwrite existing case {run}')

    environment = dict(os.environ, FLOWS='1584>1585,1584>1585', PACING='false',
                       CS30401_STUDY_TRACE=str(args.trace),
                       CS30401_STUDY_TRACE_DIR=str(run / 'logs_ns3'))
    setup_command = ['bash', str(MAKE_RUN), str(run), args.state, 'TcpCubic',
                     str(args.rate), str(args.queue), str(args.duration), '1584', '1585']
    command = [str(BINARY), '--run_dir=' + str(run)]
    manifest = {'schema_version': 1, 'case': args.name, 'run_dir': str(run),
                'parameters': vars(args), 'flows': flows, 'state': args.state,
                'official_image': OFFICIAL_IMAGE, 'official_image_digest': args.image_digest,
                'image_digest_qualification': 'Host-verified declaration; no in-container Docker inspection.',
                'setup_command': setup_command, 'command': command,
                'trace_environment': {key: environment[key] for key in
                                      ('FLOWS', 'PACING', 'CS30401_STUDY_TRACE', 'CS30401_STUDY_TRACE_DIR')},
                'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'start_time_unix': time.time(), 'status': 'preparing', 'stage': 'provenance',
                'exit_code': None, 'simulation_exit_code': None, 'wall_time_s': None}
    started = time.monotonic()
    simulation_started = None
    return_code = 1
    write_manifest(run, manifest)
    try:
        (run / 'logs_ns3').mkdir()
        manifest['source_commit'] = args.source_commit or read_commit(script.parents[2])
        manifest['source_commit_origin'] = 'explicit argument' if args.source_commit else 'repository HEAD'
        manifest['runner_sha256'] = sha256(script)
        manifest['patch_sha256'] = sha256(args.patch)
        manifest['binary_sha256'] = sha256(BINARY)
        manifest['make_run_sha256'] = sha256(MAKE_RUN)
        manifest['stage'] = 'make_run'
        write_manifest(run, manifest)
        with (run / 'setup.log').open('w', encoding='utf-8') as log:
            subprocess.run(setup_command, env=environment, check=True,
                           stdout=log, stderr=subprocess.STDOUT)

        manifest['stage'] = 'configuration'
        config_path = run / 'config_ns3.properties'
        config = config_path.read_text(encoding='utf-8')
        pattern = r'^tcp_flow_enable_logging_for_tcp_flow_ids=.*$'
        config, count = re.subn(pattern, 'tcp_flow_enable_logging_for_tcp_flow_ids=set(0,1)',
                                config, flags=re.MULTILINE)
        if count != 1:
            raise ValueError('Expected exactly one detailed-logging setting from make_run.sh.')
        config_path.write_text(config, encoding='utf-8')
        schedule_path = run / 'schedule.csv'
        schedule_path.write_text(''.join(
            f"{flow['flow_id']},1584,1585,{FLOW_BYTES},{flow['start_ns']},"
            f"{flow['additional_parameters']},\n" for flow in flows), encoding='utf-8')
        manifest['config_ns3.properties_sha256'] = sha256(config_path)
        manifest['schedule.csv_sha256'] = sha256(schedule_path)
        manifest.update(status='running', stage='simulation')
        write_manifest(run, manifest)
        simulation_started = time.monotonic()
        with (run / 'console.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        return_code = result.returncode
        manifest['simulation_exit_code'] = return_code
        manifest['status'] = 'complete' if return_code == 0 else 'failed'
    except (Exception, KeyboardInterrupt) as error:
        manifest['status'] = 'failed'
        manifest['error_type'] = type(error).__name__
        manifest['error'] = str(error)
        return_code = 130 if isinstance(error, KeyboardInterrupt) else getattr(error, 'returncode', 1)
    finally:
        manifest['exit_code'] = return_code
        manifest['wall_time_s'] = round(time.monotonic() - started, 6)
        if simulation_started is not None:
            manifest['simulation_wall_time_s'] = round(time.monotonic() - simulation_started, 6)
        manifest['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        write_manifest(run, manifest)
    print(json.dumps({key: manifest.get(key) for key in
                      ('case', 'status', 'stage', 'exit_code', 'wall_time_s', 'patch_sha256', 'error')},
                     indent=2), flush=True)
    if return_code:
        print(f'Failure evidence retained in {run}', file=sys.stderr)
    return return_code if return_code >= 0 else 128 - return_code


if __name__ == '__main__':
    raise SystemExit(main())
