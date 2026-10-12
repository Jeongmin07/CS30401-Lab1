#!/usr/bin/env python3
"""Build the exact V2 source, then record readiness for a fresh guarded replay."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--replace', action='store_true', help='Explicitly replace a prior build readiness receipt, not experiment manifests')
    a = p.parse_args()
    if a.out.exists() and not a.replace:
        raise ValueError('Readiness receipt exists; use a new path or explicit --replace')
    patch = Path(__file__).with_name('ns3-v2.patch')
    diff = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=a.ns3)
    if diff != patch.read_bytes():
        raise ValueError('Source diff differs from V2 combined patch')
    # This synchronous command must complete successfully BEFORE readiness exists.
    subprocess.run([str(a.ns3 / 'ns3'), 'build', '-j', '1'], cwd=a.ns3, check=True)
    build = a.ns3 / 'build'
    record = {'patch_sha256': sha(patch), 'source_diff_sha256': hashlib.sha256(diff).hexdigest(),
              'build_completed_exit_code': 0, 'recorder_sha256': sha(Path(__file__)),
              'runtime_files': {str(path.relative_to(build)): sha(path) for path in [build / 'scratch/main_satnet/ns3.48-main_satnet', *sorted((build / 'lib').glob('*.so'))]}}
    a.out.write_text(json.dumps(record, indent=2) + '\n')
    print(a.out)


if __name__ == '__main__':
    main()
