#!/usr/bin/env python3
"""Store completed text logs and verify every decompressed archive member."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', nargs='+', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    inventory_path = a.out.with_name(a.out.name + '.inventory.json')
    if a.out.exists() or inventory_path.exists():
        raise ValueError('Archive and receipt must be new')
    members = {}
    with tarfile.open(a.out, 'w:gz') as archive:
        for run in a.runs:
            manifest = json.loads((run / 'manifest.json').read_text())
            if manifest['status'] != 'success' or manifest['returncode'] != 0:
                raise ValueError('Only completed cases: ' + str(run))
            for path in sorted(run.rglob('*')):
                if not path.is_file() or path.is_symlink() or path.suffix not in {'.json', '.csv', '.txt', '.properties'}:
                    continue
                name = run.name + '/' + path.relative_to(run).as_posix()
                if name in members:
                    raise ValueError('Duplicate archive member: ' + name)
                with path.open('rb') as source:
                    value = digest(source)
                members[name] = {'bytes': path.stat().st_size, 'sha256': value}
                archive.add(path, arcname=name, recursive=False)
    observed = set()
    with tarfile.open(a.out, 'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name not in members or member.name in observed:
                raise ValueError('Unexpected archive member')
            with archive.extractfile(member) as source:
                value = digest(source)
            if member.size != members[member.name]['bytes'] or value != members[member.name]['sha256']:
                raise ValueError('Decompressed member mismatch: ' + member.name)
            observed.add(member.name)
    if observed != set(members):
        raise ValueError('Missing archive members')
    with a.out.open('rb') as source:
        archive_hash = digest(source)
    record = {'archive': a.out.name, 'bytes': a.out.stat().st_size, 'sha256': archive_hash,
              'file_count': len(members), 'uncompressed_bytes': sum(m['bytes'] for m in members.values()),
              'every_decompressed_member_verified': True, 'members': members,
              'scope': 'Completed text logs/settings/manifests only; no ns-3 tree, binaries or generated state. Archive bytes identify this artifact; byte-identical reruns or deterministic gzip are not claimed.'}
    inventory_path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: record[k] for k in ('archive', 'bytes', 'sha256', 'file_count', 'every_decompressed_member_verified')}))


if __name__ == '__main__':
    main()
