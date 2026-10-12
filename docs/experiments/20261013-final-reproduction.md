# Final fixed-code course package and independent replay

Status: all 19 simulations, both fresh builds and validated report-input regeneration completed successfully on 13 October 2026. The parent owns final PDF/ZIP and Release publication. This phase packages and reproduces completed results; it implements no new algorithm and tunes no parameters. Frozen earlier source, libraries, inputs and original receipts remain unchanged.

## Scope fixed before execution

Use two exact frozen standalone runtime patches: pacing `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808` and backpressure `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f`. Do not merge their instrumentation into a third artifact. Each fresh official source volume is CPU2/4GiB/build-j1; each simulation has a600-second wall cap.

The fixed matrix is19 physical runs /22 mapped reported conditions. Pace has the original tail core10, native/capacity natural2, selected paced micro1, startup first-original-loss2 and exact delayed-T75→T78 counterfactual1. BP has control/FIFO/CoDel3. Three exact same-runtime aliases are pacingOFF→core `leo10-tail`, safety micro-original→`micro-base`, safety micro-current→`micro-tail`. Selective/tail natural runs and the separate BP control are not aliased. Four older numerical candidate studies are omitted from the final report/package; their repository records are preserved.

The primary profile explicitly enables selective+tail with native pacingOFF; the baseline disables both custom policies. Pacing/backpressure remain diagnostic options. No global TCP default, new topology, APSP, additional loss model, sweep or new timing choice is introduced.

## Portable dependency contract

[Self-contained package](../../code/lab1-final/README.md) owns frozen patches, copied stdlib policy/analysis/drop-audit helpers, exact forward-hints/path-truth inputs, a checksum-only historical parity contract and the original deterministic two-file route-delay generator. Figure tools are owned separately under its `report/`, with Matplotlib pinned through uv. No earlier study directory, copied state, raw logs, ns-3 tree, build output or GitHub download is required after extracting the course ZIP. Report and README are English and identify Seongchan Kim,Jeongmin Kim,Jaehwan Kang.

Fresh source is exported with the official `make_patch.sh` and compared byte-for-byte with its frozen artifact. Guards use staged+unstaged `git diff HEAD`, validate actual course baseline HEAD, reject stale runtime/readiness, and exclude a case if source/runtime/package helpers or inputs change. The ZIP can run without a Git checkout; absent repository identity is recorded honestly alongside file hashes.

Fresh figures/tables are generated only from actual receiver/packet/controller/queue traces. The original 345-file historical contract is preserved. Final validation requires 342 byte-identical CSVs and three BP outcome files with exact ordered non-pending bytes and complete terminal pending-row bags, allowing only final pending-row serialization order; wall profiling is excluded. The counterfactual uses fresh selective native-device metadata and the unchanged construction recipe, verifies exactly two changed route files and loop/interface validity, and requires actual pre-T75 trajectory equality, including the new passive queue integrals. Original hint epochs remain fixed despite delayed routing.

Actual dedicated containers/volumes: `lab1-final-pace-20261013` / `cs30401-final-pace-ns3-20261013`, and `lab1-final-bp-20261013` / `cs30401-final-bp-ns3-20261013`. All builds and simulations started after the parent's reviewed execution checkpoint `9a5687bd4e46447e81f3dec13ab2f78442ede056`.

## Actual isolation and replay

The initial candidate ZIP had 39 members, 453,434 bytes and SHA256 `c7c9b0141d5200a2cdc80bf1f8aed1a74f4e64198781b8afcd254fd66de13c8a`. Each fresh container mounted only this extracted submission root at `/work`, without a research-repository checkout or access to earlier studies/logs. Package Git identity is explicitly null. The separate official ns-3 Git repository is retained because the course export script requires it.

Both official-source builds succeeded and their official exports were byte-identical to the two frozen patches. There were two build attempts and 19 simulation attempts, all successful; no simulation failed, timed out or was excluded. Every run retained unchanged source/runtime/package-input guards. All 17 runtime-file hashes per build, exact commands/configuration, input hashes and [build records](assets/20261013-final-reproduction/builds) are preserved. No simulation or controller parameter was changed after results.

## Postprocessing-only correction

The original PACE analysis succeeded and is preserved. The original BP analysis stopped at its first `bp_outcomes.csv` byte-hash check, while all three BP simulations remained successful. Independent comparison found identical headers and ordered non-pending bytes, plus identical complete 15-field pending rows and multiplicities. Only their final serialization order differed. The unchanged observer emits a `std::map<const Packet*, Entry>` in pointer-key order at final flush; old/fresh installed observer SHA256 is `5298eb4585f8082ba346ca5eec946959adc19327c4e6ad8ce52dec2649584819`.

Reviewed postprocessing checkpoint `b5d01511d4b729346e6840e6ab11891e860132da` corrects only `analyze.py` / `merge.py` validation and adds a hash-only [pending-order contract](../../code/lab1-final/inputs/expected-pending-order.json). The original 345-file contract is unchanged, SHA256 `e9fcfdb92ea8737b7f5e2f027ee3e2bc83f35d84728b443bebdf430335ff8afb`. The exception is restricted to the three named BP files/patch: exact header, ordered non-pending raw bytes, sorted complete pending raw-line bags, counts, cutoff, censored reason, suffix placement and unique visit IDs are required. There is no numeric tolerance or omitted field.

Both analyses were regenerated from the completed raw runs into new `pace-validated` / `bp-validated` directories, preserving original outputs and the failed-analysis receipt. No simulation was rerun for this repair. The final merge reports **342 byte-identical CSV contracts plus three exact full-field pending-order contracts**, `all_measurements_equal=true` and `all_exact=false`. [Correction receipt](assets/20261013-final-reproduction/postprocessing-correction.json) records both source checkpoints, exact old/new helper hashes, 26 unchanged execution files and completed postprocessing outcomes.

## Fresh evidence and limits

[Fresh merged report input](assets/20261013-final-reproduction/report-data.json) and [QA summary](assets/20261013-final-reproduction/reproduction.json) retain 19 physical conditions, 22 mappings, scalar/measurement equality and actual trace series. Reference checksums never generate plot values. This validates deterministic regeneration and portability; it is not statistical replication, a new algorithm evaluation or evidence for a wider operating domain.

The reporting-only witness helper verified all six relevant fresh manifests/raw sets/summary and full-analysis receipts. It found three stock T26 and two remaining capacity-run original transmissions delivered to the application before their first retransmission. [Final witness receipt](assets/20261013-final-reproduction/witnesses-final.json), 165,623 bytes, has SHA256 `66ed61ba7f885fafe4fde97c2f12a75bb39e244557b15176ab3773f3a06c5ac4`; the initial receipt is preserved separately. These support unnecessary retransmission directly rather than inferring it from absent drops. Finite pacing chronology and exact physical-drop joins were regenerated too. No unproven direction-specific cause is assigned to the residual capacity episode.

## Verified raw archives

All members were streamed and checked for size/SHA256; local publication copies were rechecked after copying into ignored `output/lab1-final-raw/`.

| Archive | Bytes | Members | SHA256 |
|---|---:|---:|---|
| `lab1-final-pace-20261013.tar.gz` | 129,625,046 | 447 | `881ea9904c31a68467aa5c873fff222e0cd9a973cf5a78f087ed6b6e628109cd` |
| `lab1-final-bp-20261013.tar.gz` | 53,775,408 | 118 | `d3076df71f124e4cc21644d675708fe5570f085f98fb880d571ee176a0eae029` |

Total: 183,400,454 compressed bytes. [PACE inventory](assets/20261013-final-reproduction/lab1-final-pace-inventory.json) and [BP inventory](assets/20261013-final-reproduction/lab1-final-bp-inventory.json) list every member. Archives include the 19 actual run directories/manifests and build/export records; PACE also retains the CF receipt/two changed sparse files and initial fresh validation receipts. Full provided state, ns-3 trees and historical logs are excluded. Corrected validation records and both witness versions are retained separately in compact evidence.

The parent published the [submission candidate and both raw archives](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/lab1-final-20261013), then checked all five remote asset sizes and SHA256 digests against local files. [Publication receipt](assets/20261013-finalization/release.json) and [final PDF/ZIP checks](20261013-finalization.md) record that separate step. The course ZIP contains report/README/code only, with no raw archive, logs, generated state, environment directory or compiler output.
