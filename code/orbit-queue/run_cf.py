"""Run only the reviewed, fixed-policy T75 to T78 routing counterfactual."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('queue_run', HERE/'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt', required=True, type=Path)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--root', type=Path, default=Path('/tmp/orbit-queue-cf'))
    p.add_argument('--natural-root', type=Path, default=Path('/tmp/orbit-queue'))
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--ready', type=Path, default=HERE/'build-ready.json')
    a = p.parse_args(); receipt = json.loads(a.receipt.read_text())
    assert all(receipt['checks'].values()), 'Input construction checks failed'
    assert receipt['original_transition_ns'] == 75_000_000_000 and receipt['delayed_transition_ns'] == 78_000_000_000
    state = Path(receipt['modified_state'])
    current = {str(p.relative_to(state)):run.sha(p) for p in sorted(state.rglob('*')) if p.is_file()}
    assert run.hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest() == receipt['modified_files_mapping_sha256']
    original_run = a.natural_root/'selective-natural'
    original = json.loads((original_run/'manifest.json').read_text())
    assert original['status'] == 'success' and original['exit_code'] == 0
    assert original['runtime_unchanged'] and original['source_unchanged']
    current_patch = run.sha(HERE/'ns3.patch')
    assert original['patch_sha256'] == original['installed_diff_sha256'] == current_patch
    assert original['runtime_files'] == run.runtime(), 'Runtime differs from the completed selective case'
    assert original['build_ready_sha256'] == run.sha(a.ready)
    assert run.sha(original_run/'schedule.csv') == receipt['original_selective_schedule_sha256']
    assert run.sha(original_run/'manifest.json') == receipt['original_selective_manifest_sha256']
    name = 'selective-route75-delayed78'
    run.CASES[name] = dict(run.CASES['selective-natural'])
    provenance = dict(input_receipt_sha256=run.sha(a.receipt), input_receipt=str(a.receipt),
        original_selective_run=str(original_run), original_transition_ns=75_000_000_000,
        delayed_transition_ns=78_000_000_000, fixed_original_T75_forecast=True,
        implementation_patch_and_runtime_unchanged=True,
        intervention='Only the supplied T75 sparse routing delta moves to T78, both directions/link choices.',
        limit='Native ideal shared-GSL routing counterfactual; physical visibility and deployment feasibility unproved.')
    run.execute(name, a.root, a.timeout, a.ready, a.checkpoint,
                input_state=state, routing_counterfactual=provenance)


if __name__ == '__main__':
    main()
