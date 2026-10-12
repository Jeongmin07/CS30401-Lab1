# Final fixed-code course package and independent replay

Status: pre-build declaration,13 October2026. This phase packages and reproduces completed results; it implements no new algorithm and tunes no parameters. Frozen earlier source, libraries, inputs and original receipts remain unchanged.

## Scope fixed before execution

Use two exact frozen standalone runtime patches: pacing `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808` and backpressure `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f`. Do not merge their instrumentation into a third artifact. Each fresh official source volume is CPU2/4GiB/build-j1; each simulation has a600-second wall cap.

The fixed matrix is19 physical runs /22 mapped reported conditions. Pace has the original tail core10, native/capacity natural2, selected paced micro1, startup first-original-loss2 and exact delayed-T75→T78 counterfactual1. BP has control/FIFO/CoDel3. Three exact same-runtime aliases are pacingOFF→core `leo10-tail`, safety micro-original→`micro-base`, safety micro-current→`micro-tail`. Selective/tail natural runs and the separate BP control are not aliased. Four older numerical candidate studies are omitted from the final report/package; their repository records are preserved.

The primary profile explicitly enables selective+tail with native pacingOFF; the baseline disables both custom policies. Pacing/backpressure remain diagnostic options. No global TCP default, new topology, APSP, additional loss model, sweep or new timing choice is introduced.

## Portable dependency contract

[Self-contained package](../../code/lab1-final/README.md) owns frozen patches, copied stdlib policy/analysis/drop-audit helpers, exact forward-hints/path-truth inputs, a checksum-only historical parity contract and the original deterministic two-file route-delay generator. Figure tools are owned separately under its `report/`, with Matplotlib pinned through uv. No earlier study directory, copied state, raw logs, ns-3 tree, build output or GitHub download is required after extracting the course ZIP. Report and README are English and identify Seongchan Kim,Jeongmin Kim,Jaehwan Kang.

Fresh source is exported with the official `make_patch.sh` and compared byte-for-byte with its frozen artifact. Guards use staged+unstaged `git diff HEAD`, validate actual course baseline HEAD, reject stale runtime/readiness, and exclude a case if source/runtime/package helpers or inputs change. The ZIP can run without a Git checkout; absent repository identity is recorded honestly alongside file hashes.

Fresh figures/tables are generated only from actual receiver/packet/controller/queue traces. All345 declared historical measurement-CSV contracts must match; wall profiling is excluded. The counterfactual uses fresh selective native-device metadata and the unchanged construction recipe, verifies exactly two changed route files and loop/interface validity, and requires actual pre-T75 trajectory equality. Original hint epochs remain fixed despite delayed routing.

Planned dedicated containers/volumes: `lab1-final-pace-20261013` / `cs30401-final-pace-ns3-20261013`, and `lab1-final-bp-20261013` / `cs30401-final-bp-ns3-20261013`. No build/simulation occurs before the parent's reviewed source checkpoint. All build attempts, failed simulations/exclusions, official exports, input/config/command metadata, raw/analysis hashes and report-input parity will be preserved. Final results and verified artifact locations will be appended after actual replay.
