# Forecast-informed loss detection with bounded restoration

This is an opt-in variant of the team's existing CUBIC/SACK/PRR window protection. **Existing K8/K20 already used notified windows.** This variant derives windows from supplied geometry and restores K3 with a loss-evidence reevaluation at expiry. It does not pause sending, change CUBIC growth, clear loss/SACK evidence or implement RACK. Read [the experiment record](../../docs/experiments/20261012-forecast-loss.md) for completed results, costs and boundaries.

`study_bounded_restore=1` permits a guard only in OPEN, with zero duplicate ACK count, no known loss, SACK enabled and FACK disabled. The fixed threshold applies to both socket duplicate-ACK handling and TxBuffer SACK presumed-loss marking. At expiry the threshold is restored; in DISORDER existing evidence is reevaluated and can invoke stock recovery without a new ACK. A timer contributes zero newly delivered bytes; stock PRR still grants its normal initial recovery-send credit. The RTO handler is unchanged, and the application releases an active high threshold after a CA_LOSS trace. Neither the current geometry horizon nor a high packet-count threshold guarantees no genuine-loss delay.

The combined patch includes canonical v6 instrumentation and benchmark plus this small variant. Apply **one** patch to clean official source. Do not layer this patch with `code/bbr-route/ns3-observe.patch` or with another study patch. `install_bounded.py` is for developing the variant on an exact v6 tree; the combined patch is the replay artifact.

## Replay

Run from the repository root in PowerShell; use new names and an empty volume. The runner refuses existing case directories and verifies the installed source diff, runtime files and input/output hashes. It explicitly uses the current build libraries. Raw traces stay in the container; export compact evidence before sharing.

```powershell
$forecastRoot = (Resolve-Path .).Path
$forecastImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name forecast-replay --cpus 4 --memory 6g --mount "type=bind,source=$forecastRoot,target=/work" --mount 'type=volume,source=forecast-replay-ns3,target=/home/ubuntu/ns-3.48' $forecastImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 forecast-replay bash -lc 'git apply --check /work/code/predict-loss/ns3.patch && git apply /work/code/predict-loss/ns3.patch && git add -N scratch/main_satnet/study_drop_trace.h scratch/study_micro/study_micro.cc && ./ns3 build -j 4'
docker exec forecast-replay python3 -B /work/code/predict-loss/run.py loss-first-base loss-first-legacy loss-first-bounded loss-middle-base loss-middle-bounded
docker exec forecast-replay python3 -B /work/code/predict-loss/run.py leo10-base leo10-forecast leo10-late
docker exec forecast-replay python3 -B /work/code/predict-loss/run.py leo100-base40 leo100-forecast20-40 leo100-forecast64-40
docker exec forecast-replay python3 -B /work/code/predict-loss/run.py loss-rto3-base loss-rto3-bounded
```

Analyze each completed case using `code/kim-study/analyze_study.py`. For LEO pass `--path-truth /work/code/kim-study/path_truth_200s.csv --include-bins --output RUN/analysis.json`; for the stable micro controls pass `--events 2 --include-bins --output RUN/analysis.json`. Then `summarize.py --root /tmp/predict-loss --out NEW_EXPORT` checks actual delivery, raw receipts, controller transitions and expiry before exporting. The exact run commands/parameters are in every copied manifest. The original fresh volume was built and executed; this complete replay command block has not itself been rerun in another volume yet.

`run.py` uses **operator-oracle information** from existing geometry, not an implemented public-orbit or operator-message predictor. It selects negative propagation-RTT steps on path changes and sets H=2*max(old,new propagation RTT), starting at the change. The horizon does not include a measured future queue. Payload/ACK ordering evidence is evaluated afterward and is never fed into the controller. The supplied path-truth RTT combines both directions, which limits forward-only prediction claims.
