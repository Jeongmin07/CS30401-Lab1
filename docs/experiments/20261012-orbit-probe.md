# Orbit-informed BBR ProbeRTT timing — predeclared bounded experiment

Owner: kim-seongchan with AI assistance, 12 October 2026. This is one independent candidate requested by the user. It does not select the team's final topic. Only `code/orbit-probe/`, this record and `assets/20261012-orbit-probe/` are owned here; no other controller patch is composed.

## Question and policy declared before runs

Can a route-change notification improve the timeliness of BBRv1-family RTprop remeasurement, without removing its low-inflight ProbeRTT or disguising the cost of extra measurements? The prior passive 40-second BBR run entered ProbeRTT at 10.098743036s and left at 10.497171637s. A later route shortening can naturally provide a lower RTT sample, so an extra probe may be redundant. No improvement is assumed.

The opt-in policy reads operator-oracle route-change times from the supplied `code/kim-study/path_truth_200s.csv`. It considers changes of at least 1ms in two-direction propagation RTT, matching the millisecond-scale RTT values visible in the course BBR trace. At event `t`, it waits `H = 2 * max(old, new propagation RTT)` before considering a measurement; this is an engineering hypothesis, **not** a bound on queue clearing or actual ACK arrival. The geometry value is never installed as TCP's measured RTprop.

At the first subsequent ACK, a notification is consumed. If a measured minimum has already been refreshed since `t`, no extra probe is requested. If BBR is not in ProbeBW, TCP is not CA_OPEN, or the connection is restarting from idle, the hint is skipped rather than interrupting an existing recovery/startup/probe. Otherwise the old path's filter timestamp is expired early and the **original** `UpdateRTprop` and `CheckProbeRTT` perform remeasurement. The 10-second filter length remains unchanged; all future natural expirations remain active. The original 4-MSS inflight cap, drain criterion, 200ms low-inflight duration and completed packet-round condition remain unchanged. A probe's full residence includes draining and may exceed 200ms.

This is an ideal timely operator notification. Endpoint acquisition, clock accuracy, route prediction errors, queued old-path data and competition are not solved by it. No wireless loss, outage, varying capacity, new topology or shortest-path search is added. Early invalidation may increase queue bias or sacrifice throughput; the comparison must retain those costs.

## Fixed four-case matrix and limits

Fresh official container `lab1-orbit-probe-20261012`, new volume `cs30401-orbit-probe-ns3-20261012`; pinned image `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`. CPU limit 2, memory limit 4GiB; build `-j1` to coordinate with the other independent tracks.

All cases use one Seoul1584→London1585 TcpBbr bulk flow, 100GB MaxBytes, 100 Mbit/s fixed ISL/GSL capacities, 100-packet device queues, default BBR pacing, seed 123456789, unmodified supplied 100ms routes. Policy OFF/ON use the same composed binary and passive observation ON. Each run has a 240-second wall-time cap; no more than four planned cases, with a global maximum of six including any disclosed repair reruns. Timed-out/failed cases are never performance results.

| Case | Policy | Start / end (s) | Declared receiver windows |
| --- | --- | --- | --- |
| solo40-off | OFF | 0 / 40 | whole [0,40), route-shortening [25.7,28.2) |
| solo40-on | ON | 0 / 40 | same |
| rise140-off | OFF | 105 / 140 | active [105,140), pre [116.6,121.6), post [121.6,126.6), late [131.6,136.6) |
| rise140-on | ON | 105 / 140 | same |

The second pair captures the real propagation increase at 121.6s after startup; it does not rewrite the provided topology or hold a path fixed. Whole [0,140) goodput and active [105,140) goodput have different denominators and must be labeled separately. Window selection is fixed before any new result is read. Low-inflight probe duration and evidence of RTT samples are audited independently of performance, with pending queues censored and drop hook layers kept separate. This small deterministic matrix has no statistical repetitions or generality guarantee.

## State before execution

The fresh volume received only the existing passive `code/bbr-route/ns3-observe.patch`. Controller code, build, exact source/runtime/input receipts, actual results and reproduction commands will be added below after they exist. No simulation for this policy had run when this declaration was written.

## V1 results and semantic correction declared before V2

All four V1 cases completed. OFF/ON matched in **all 10 measured CSVs**, excluding controller-decision and wall-timing files. The shortening pair delivered 90.461484Mbit/s over [0,40) and 96.034752Mbit/s over [25.7,28.2). The increase pair delivered 89.264393Mbit/s over the active [105,140) window; no performance improvement was observed.

At 121.781230119s the ON policy skipped its hint because the minimum's update stamp was 121.642864104s, later than the route event. Yet the accepted RTprop remained 88ms while the cached TCP lastRtt was 100ms. The stamp identifies ACK processing, **not** the send/receive provenance of a newly measured path RTT. Old-flight ACKs/cached RTT can refresh this stamp after a route change. Therefore timestamp freshness alone does not demonstrate a valid new-path measurement. This is an observed semantic weakness of the V1 gate; these V1 null results remain preserved in the V1 patch, four manifests and raw archive.

The user-authorized final **two-case** budget will run `v2-rise140-off` and `v2-rise140-on`, with exactly the same flow105→140, network, seed and evaluation windows. The repair skips a hint only if a **normally completed ProbeRTT** is logged after the notified route change. It never replaces ProbeRTT with a timestamp refresh. Notifications before flow start are omitted; the only active-period notification in this pair is the actual increase at 121.6s. ProbeBW/nonidle/valid-sample checks remain. The extra V1 CA_OPEN restriction is removed because stock `CheckProbeRTT` itself permits an expired measurement during recovery; stock cwnd conservation, restore, low-inflight and round guards stay in effect. This is a semantic gate repair based on the observed old-flight ambiguity and the original implementation, **not tuning for a favorable score**.

V2 will export a distinct `code/orbit-probe/ns3-v2.patch` and use `run_v2.py`. Its explicit completion timestamp and TCP congestion state join the lifecycle trace. Source and runner will be frozen before either V2 simulation. Total simulation count remains capped at six. Early expiry must use TCP RTT samples, not injected geometry; extra probe residence, goodput sacrifice, queue changes and any remaining estimator limitations will be reported even if negative. No V2 result existed when this correction was written.

## Actual attempt accounting and runtime correction

The six-attempt declaration above was exceeded by **one authorized repair**, for seven attempts and six valid simulations. The first V2 OFF started before its asynchronous build completed and loaded the previous V1 libraries. It exited successfully as a program but has a 22-column V1 lifecycle trace and runtime hashes different from the finished V2 build. Its original `manifest.json` status/return code are preserved; [the separate exclusion](assets/20261012-orbit-probe/v2/build-race-exclusion.json) marks it ineligible for performance analysis. The sequential ON began after the build finished and is a valid V2 run; every recorded runtime SHA matches the completed V2 build and its 24-column trace.

Only the invalid OFF was repeated in a new directory with a pending-build/readiness-hash guard. OFF and ON therefore have different **runner** hashes, documented with the byte-preserved `run-v2-before-guard.py`. Their actual ns-3 binary, libraries, full source patch, settings, schedule, forecast, all static/dynamic input hashes and normalized simulation commands match. The guard also verifies unchanged runtime hashes after the repaired OFF and the actual V2 trace header. [Pair verification](assets/20261012-orbit-probe/v2/pair-comparison-final.json) passed. The earlier comparison-tool source is preserved as `compare-v2-before-replay.py`; the final helper also supports fresh replays with the same guarded runner on both sides. No eighth simulation was run.

| Attempt | Wall time (s) | Use |
| --- | ---: | --- |
| V1 solo40 OFF / ON | 74.4868 / 72.3536 | valid null pair |
| V1 rise140 OFF / ON | 59.7848 / 58.4312 | valid null pair |
| first V2 rise140 OFF | 47.1292 | excluded old-runtime build race; original successful exit retained |
| V2 rise140 ON | 50.9377 | valid finished V2 runtime |
| replacement V2 rise140 OFF | 50.5146 | valid, build/runtime guard passed |

These wall times are execution costs, not statistical performance repetitions. Build used `-j1`; initial compilation ran before the first pair, V2 compilation completed before its valid ON, and replacement OFF used the finished unchanged build. [Container metadata](assets/20261012-orbit-probe/container-runtime.json) records the actual image configuration ID, declared pinned image argument and resource caps. Original launch readiness is preserved in [build-ready-at-run.json](assets/20261012-orbit-probe/v2/build-ready-at-run.json).

## Valid V2 outcomes: timeliness with a shifted performance dip

Both bulk flows remain incomplete against 100GB MaxBytes; no finite-flow completion-time claim is made. Exact delivered totals are 390,531,720B OFF and 390,854,640B ON. Metrics use **receiver application delivery**, not sender ACK progress.

| Predeclared window | OFF goodput (Mbit/s) | ON goodput (Mbit/s) | Change |
| --- | ---: | ---: | ---: |
| whole [0,140), including 105s idle | 22.31609829 | 22.33455086 | +0.08269% |
| active [105,140) | 89.26439314 | 89.33820343 | +0.08269% |
| pre [116.6,121.6) | 96.173856 | 96.173856 | 0% |
| post [121.6,126.6) | 93.806880 | 87.242496 | **−6.99776%** |
| late [131.6,136.6) | 85.875744 | 94.409664 | +9.93752% |

The first ordinary ProbeRTT at 115.087600125→115.442359185s is identical. The second probe moves from **131.642990084→132.009175413s** OFF to **121.781230119→122.147976259s** ON: entry is 9.861759965s earlier. Both observed active windows contain two probes. This is not removal of ProbeRTT or evidence of fewer probes over an unobserved longer run.

Exact lifecycle audit verifies the original four-MSS cap (5,520B), drain at inflight≤cap, 200ms minimum low-inflight interval and completed packet round. Low-inflight residence for the second probe is 0.274975609s OFF versus 0.275421618s ON. Total probe residence, including drain, is 0.720944389s OFF versus 0.721505200s ON (+0.560811ms). The ON notification actually invalidates the filter at 121.781230119s. Its first accepted TCP cached lastRtt is **100ms**, showing temporary queue/sample bias; after draining, the accepted minimum is **91ms**. Ten accepted cached-lastRtt update records occur after that drain, rather than ten independently identified wire RTT observations. The RTprop filter length remains 10s and ordinary expirations remain enabled. Geometry is not installed as a measured RTT.

The stock drain criterion concerns TCP's tracked pipe/inflight budget. It does **not** certify that every network queue has emptied, or identify a new-path transmission for each cached RTT value. These measurement and oracle limitations remain even though the original ProbeRTT lifecycle safeguards passed.

Over the active window, mean served-device-queue-visit wait is 0.104613990ms OFF versus 0.102464996ms ON. This includes zero waits, multiple devices and both data/ACK directions; it is not end-to-end queue latency. TcDrop **hook-event counts** increase from 6,696 to 6,832; no sum is treated as unique physical losses or retransmissions. The post window has 942→870 TcDrop events, while the late window has 690→697. Queue enqueue/dequeue/pending conservation and coverage checks passed; terminal queued packets are separately censored (64 OFF, 0 ON). Sparse BBR congestion-state snapshots do not provide an exact recovery-entry or RTO count. Receiver goodput dips and layered drops are the directly measured costs.

The result supports **earlier valid low-inflight remeasurement in this one provided path-increase condition**, with a clear near-event cost and a small net difference over the active interval. It does not establish a useful general throughput gain, robust prediction, universal scheduling rule or an improvement to current Linux BBRv3. V1's shortening/null result belongs to V1 and is not a V2 test. Competing traffic, false/mistimed hints, longer horizons and deployment accuracy remain untested. No more experiments or parameter tuning were performed.

See [valid V2 summary](assets/20261012-orbit-probe/v2/summary.json), [window table](assets/20261012-orbit-probe/v2/windows.csv), [V1 evidence](assets/20261012-orbit-probe/summary.json) and [unchanged V1/V2 OFF measurements](assets/20261012-orbit-probe/v2/off-versus-v1.json). The scientific [PNG](assets/20261012-orbit-probe/v2/figures/v2-timing-tradeoff.png) / [PDF](assets/20261012-orbit-probe/v2/figures/v2-timing-tradeoff.pdf) separates sparse RTprop estimator samples, nominal geometry and actual receiver-byte bins; exact probe residence is shaded. [Figure receipt](assets/20261012-orbit-probe/v2/figures/plot-receipt.json) identifies every plotted source.

## Reproduce on a new official source volume

Apply **one full patch** to clean official ns-3; V1 and V2 are distinct full patches, not layers to apply together. The following is a fresh-replay recipe, not a claim that an eighth run occurred. Keep the current raw archives/readiness snapshot intact. A fresh compile may have new runtime hashes, so explicitly record that completed build before launching either policy condition.

```bash
# Inside a new pinned official container, with repository at /work:
cd /home/ubuntu/ns-3.48
git apply --check /work/code/orbit-probe/ns3-v2.patch
git apply /work/code/orbit-probe/ns3-v2.patch
git add -N scratch/main_satnet/bbr_route_observer.h
python3 -B /work/code/orbit-probe/record_build.py --out /work/code/orbit-probe/build-ready-v2.json --replace
python3 -B /work/code/orbit-probe/run_v2.py v2-rise140-off v2-rise140-on --root /tmp/orbit-probe-replay
python3 -B /work/code/orbit-probe/analyze_v2.py /tmp/orbit-probe-replay/v2-rise140-off /tmp/orbit-probe-replay/v2-rise140-on --out /tmp/orbit-probe-replay-analysis
python3 -B /work/code/orbit-probe/compare_v2.py --off /tmp/orbit-probe-replay/v2-rise140-off --on /tmp/orbit-probe-replay/v2-rise140-on --out /tmp/orbit-probe-replay-comparison.json
```

`record_build.py` was added as a synchronous replay safeguard after the manual completed build used here; it did not generate the original launch readiness file. For V1, apply `code/orbit-probe/ns3.patch`, build `./ns3 build -j 1`, then run `run.py solo40-off solo40-on rise140-off rise140-on` and `analyze.py` on those four fresh directories. All run and analysis directories must be new. The V2 plot consumes committed compact evidence: `python3 -B /work/code/orbit-probe/plot.py --evidence /work/docs/experiments/assets/20261012-orbit-probe/v2 --out /tmp/orbit-probe-replot`; matplotlib 3.10.8 was used for the saved figure. Initial V1/V2 analysis hashes, runtime/input hashes and actual source commits remain in each manifest/receipt rather than being rewritten to a later publishing commit.

## Verified local raw archives, publication handled by the parent task

Three immutable archives were copied into repository `output/`, with destination bytes/SHA rechecked. Every decompressed member's size/hash was verified; no ns-3 tree, binaries or generated state is included. The third archive deliberately preserves the excluded attempt and its audit record.

| Archive | Bytes | SHA256 | Members |
| --- | ---: | --- | ---: |
| `orbit-probe-v1-20261012.tar.gz` | 11,991,776 | `8fdac40bf18052157c470a20673578f8f4ae400cdd22778b84b0a33435b6c460` | 80 |
| `orbit-probe-v2-20261012.tar.gz` | 5,617,613 | `22a3a6cc4a56f39f5674676eae761c22d59268c9629488931c1c0ba4aa028afd` | 40 |
| `orbit-probe-excluded-build-race-20261012.tar.gz` | 2,807,948 | `bc547863b0984c3c4f8bf6c0a0884edfef61b064810322e59948c80fa4c00352` | 21 |

Inventories: [V1](assets/20261012-orbit-probe/raw-inventory-v1.json), [valid V2](assets/20261012-orbit-probe/v2/raw-inventory.json), [excluded attempt](assets/20261012-orbit-probe/v2/excluded-raw-inventory.json). These are local verified artifacts; this task did not upload or publish them. The parent task will record verified Release assets in [the common parallel-candidate record](20261012-parallel-candidates.md).
