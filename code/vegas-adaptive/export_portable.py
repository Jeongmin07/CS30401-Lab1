"""Export a minimal Git-free research replay package, excluding raw data/state/build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[2]
assert not a.out.exists() and not a.out.with_suffix('.zip').exists()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
files=['code/vegas-adaptive/'+x for x in ('run_case.py','run_sensitivity.py','analyze_vegas.py','ns3.patch','vegas_micro.cc',
    'verify_sensitivity.py','pr14_audit_mechanism.py','pr14-renewal-references.json','plot_sensitivity.py')]
files+=['code/kim-study/'+x for x in ('analyze_study.py','path_truth_200s.csv','pyproject.toml','uv.lock')]
hashes={}
for rel in files:
    dst=a.out/rel
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(repo/rel,dst)
    hashes[rel]=hashlib.sha256(dst.read_bytes()).hexdigest()
(a.out/'SOURCE_MANIFEST.json').write_text(json.dumps(dict(source_commit=commit,files=hashes),indent=2)+'\n')
readme='''# Git-free Vegas renewal research replay

This is a research-code package, not the final Lab1_5.zip: it has no final report
or confirmed author list. The source manifest pins the exported commit and every
code file. No repository checkout, credentials, simulation logs, constellation
state, ns-3 tree or compiled binary is included. Use the supplied official state.

## Build and representative replay (PowerShell)

Extract this ZIP in a new folder and enter that folder. Use new container/volume
names for each replay; the runners refuse existing output paths.

```powershell
$studyRoot = (Resolve-Path .).Path
$studyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name vegas-portable-replay --mount "type=bind,source=$studyRoot,target=/work,readonly" --mount 'type=volume,source=vegas-portable-replay-ns3,target=/home/ubuntu/ns-3.48' $studyImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 vegas-portable-replay bash -lc 'git apply --check /work/code/vegas-adaptive/ns3.patch && git apply /work/code/vegas-adaptive/ns3.patch && git add -A && ./ns3 build -j 4'
docker exec vegas-portable-replay python3 /work/code/vegas-adaptive/run_case.py portable-fixed-comp-r40 --after-ms 45 --competitor --renewal --rounds 40 --source-manifest /work/SOURCE_MANIFEST.json --image-digest sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4
docker exec vegas-portable-replay python3 /work/code/vegas-adaptive/analyze_vegas.py /tmp/cs30401-vegas/portable-fixed-comp-r40 --out /tmp/portable-analysis --window common:80:200
```

Git inside the course ns-3 volume is used to apply/verify its baseline patch;
the submitted code itself needs no `.git` directory or host Git mount.
The complete patch was exported using the official make_patch.sh workflow.

## Full ten-case sensitivity table and figure

In the same built container (new output root), run:

```powershell
docker exec vegas-portable-replay python3 /work/code/vegas-adaptive/run_sensitivity.py --source-manifest /work/SOURCE_MANIFEST.json --image-digest sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4 --out /tmp/vegas-sensitivity/matrix.json
$studyCommit = (Get-Content SOURCE_MANIFEST.json | ConvertFrom-Json).source_commit
docker exec vegas-portable-replay python3 /work/code/vegas-adaptive/verify_sensitivity.py --out /tmp/sensitivity-evidence --expected-source-commit $studyCommit
docker exec vegas-portable-replay bash -lc 'cp -r /work/code/kim-study /tmp/sensitivity-plot-env && cd /tmp/sensitivity-plot-env && uv sync --frozen && uv run --frozen python /work/code/vegas-adaptive/plot_sensitivity.py --evidence /tmp/sensitivity-evidence --out /tmp/sensitivity-figures'
docker cp vegas-portable-replay:/tmp/sensitivity-evidence ./regenerated-evidence
docker cp vegas-portable-replay:/tmp/sensitivity-figures ./regenerated-figures
```

`results.csv` maps every case/window to measured app throughput, common-window
fairness, queue wait and drop counts. `verification.json` independently
reconstructs renewal histories and compares r20 raw measurements to pinned PR14
receipts. `sensitivity.png/pdf` comes from this table. Its 100 Mbps original-Vegas
reference line is a historical 41.5113384 Mbps value, explicitly marked in the
figure source receipt; reproduce that reference with the run_case command using
`--kind leo` and omitting `--renewal`, then analyze its full 200-second output.

Runtime depends on host CPU/storage: budget tens of minutes for build, ten
simulations, complete raw-log analysis and plotting; representative replay takes
minutes. The project experiment record gives the actual measured runtime.

## Model, parameters, reuse and limitations

Official course image 2026f-v1, ns-3.48 plus course Hypatia; Seoul-London 200 s,
100 ms routes, 100-packet queues, 100/50 Mbps links, seed 123456789, one long
Vegas flow. The fixed two-node diagnostic has 90 ms propagation RTT and CUBIC
joining at 80 s. Compare competition in [80,200), not unequal active lifetimes.
10/40 valid CA cycles halve/double PR14's 20-cycle history; minimum rise stays
1 ms, adaptive thresholds are off. 50 Mbps is a capacity sensitivity condition.

Reuses the course/ns-3 framework and Team 5 kim-seongchan's PR14 driver,
instrumentation, renewal implementation, analyzer and independent state audit.
Our PR15 adds adaptive comparison (disabled here), orchestration, checks and
portable packaging. Recent-min renewal follows an established idea, not a new
invention: La, Walrand and Anantharam, Issues in TCP Vegas, UCB/ERL M99/3, 1999.
Hypatia: Kassing et al., Exploring the Internet from space with Hypatia, ACM IMC,
2020. This deterministic study does not establish statistical significance,
general route/queue discrimination, Linux performance or universal optimality.
'''
(a.out/'README.md').write_text(readme,newline='\n')
archive=a.out.with_suffix('.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(a.out.rglob('*')):
        if path.is_file(): z.write(path,path.relative_to(a.out).as_posix())
print(json.dumps(dict(package=str(archive),bytes=archive.stat().st_size,
    sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),source_commit=commit)))
