"""Package reviewed submission sources, never old logs or simulator trees."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--candidate-receipt', type=Path, required=True)
    parser.add_argument('--postprocessing-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists() and not args.receipt.exists()
    data = json.loads(args.replay.read_text(encoding='utf-8'))
    assert data['physical_conditions'] == 19 and data['mapped_condition_count'] == 22
    assert data['aliases_are_not_simulations']
    assert len(data['cases']) == 19
    assert all(p.get('all_measurements_equal', p['all_exact']) for p in data['parity'].values())
    candidate = json.loads(args.candidate_receipt.read_text(encoding='utf-8'))
    correction = json.loads(args.postprocessing_receipt.read_text(encoding='utf-8'))
    corrections = correction['changes']
    assert set(corrections) == {'code/analyze.py', 'code/merge.py'}
    assert correction['qualification'] == 'Postprocessing only; no controller, simulation dispatcher, build or frozen runtime change.'
    # Executable code, pinned dependencies and input contracts remain the exact
    # isolated-mount source tested above. Documentation/report artifacts may mature.
    checked = []
    for member in candidate['inventory']:
        name = member['member']
        if not name.startswith('code/') or name.startswith('code/report/') or name == 'code/README.md':
            continue
        source = args.source / name.removeprefix('code/')
        assert source.is_file()
        if name in corrections:
            assert corrections[name]['old_sha256'] == member['sha256']
            assert corrections[name]['new_sha256'] == sha(source)
        else:
            assert sha(source) == member['sha256'], 'Tested source changed: ' + name
            checked.append(name)
    files = {'README.md': args.source / 'README.md', 'report.pdf': args.report}
    for path in sorted(args.source.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(args.source)
        if set(rel.parts) & {'__pycache__', '.venv', 'development'}:
            continue
        if rel.parts[0] == 'report':
            if rel.name.startswith('preflight') or rel.name == 'report.pdf':
                continue
            if path.suffix in {'.aux', '.out', '.log', '.toc'}:
                continue
        allowed = {'.py', '.csv', '.json', '.patch', '.sh', '.toml', '.lock', '.md', '.tex', '.pdf', '.png'}
        assert path.suffix in allowed or path.name == '.gitattributes', 'Unexpected package artifact: ' + str(rel)
        assert not (set(rel.parts) & {'logs_ns3', 'state', 'states', 'runs', 'build', 'ns-3.48'})
        files['code/' + rel.as_posix()] = path
    assert {name.split('/')[0] for name in files} == {'README.md', 'report.pdf', 'code'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    inventory = []
    with zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in sorted(files.items()):
            raw = source.read_bytes()
            info = zipfile.ZipInfo(name, (2026, 10, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if source.suffix == '.sh' else 0o100644) << 16
            archive.writestr(info, raw)
            inventory.append(dict(member=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    with zipfile.ZipFile(args.out) as archive:
        assert archive.testzip() is None
        for item in inventory:
            assert hashlib.sha256(archive.read(item['member'])).hexdigest() == item['sha256']
    receipt = dict(zip_path=str(args.out.resolve()), bytes=args.out.stat().st_size, sha256=sha(args.out),
                   source_checkpoint=candidate['source_checkpoint'], tested_source_members_equal=checked,
                   replay_sha256=sha(args.replay), report_sha256=sha(args.report), inventory=inventory,
                   postprocessing_correction=correction, postprocessing_receipt_sha256=sha(args.postprocessing_receipt),
                   member_integrity_checked=True, excluded_simulator_state_logs_tree_build=True,
                   generator_sha256=sha(Path(__file__)))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: receipt[key] for key in ['bytes', 'sha256', 'source_checkpoint', 'report_sha256']}))


if __name__ == '__main__':
    main()
