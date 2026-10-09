"""Delay one routing transition; satellite movement/distance updates continue."""
import json
import os
from pathlib import Path
import shutil

source = Path('/home/ubuntu/lab/data/seoul_london/state')
target = Path('/tmp/cs30401-controls/delay26/state')
dynamic = 'dynamic_state_100ms_for_200s'
old = source/dynamic/'fstate_26100000000.txt'
assert old.is_file()
if target.exists(): raise SystemExit('Refusing to overwrite state control')
shutil.copytree(source, target, copy_function=lambda src,dst: os.symlink(os.path.abspath(src),dst))
changed = []
for step in range(262,269):
    file = target/dynamic/f'fstate_{step*100000000}.txt'
    assert file.is_symlink()
    file.unlink() # Removes our symlink only; never modifies the original state.
    file.symlink_to(old)
    changed.append(file.name)
manifest = {'original_state':str(source),'control_state':str(target),
            'operation':'Reuse the 26.1s forwarding snapshot at updates 26.2 through 26.8s; resume current snapshot at26.9s',
            'changed_forwarding_files':changed,'satellite_orbits_and_distances':'unchanged',
            'purpose':'Diagnostic route-transition timing control, not a deployable routing policy'}
(target.parent/'control.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
