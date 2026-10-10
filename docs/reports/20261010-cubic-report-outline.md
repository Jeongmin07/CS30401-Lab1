# Report outline: reordering tolerance, genuine loss, and coexisting flows

**Status: proposed report structure, 2026-10-10.** This is an English integration outline for Team 5, not the final report or a team-approved topic. The user authorized a bounded six-case K8 competition study and this outline. That authorization does not select the team's final policy, title, authors, parameters, or submission owner. All six K8 simulations and exporter validation have completed; one representative fresh-volume replay matches all 15 measurement/legacy CSVs and the full analysis. New K8 numbers below come from the validated export and matched loss audit, not from an inference about single-flow results. Actual case manifests, common-active rows, and the replay/trajectory/archive verification records were read for this outline. Evidence is linked from the [K8 experiment record](../experiments/20261010-cubic-k8-competing.md).

Proposed title: **Reordering-Tolerance Tradeoffs in the Course LEO CUBIC/SACK/PRR Stack**.

## 1. Research narrative and boundaries

The report can follow one question: **when does increased reordering tolerance avoid an unnecessary recovery, and what does that tolerance cost when a packet is genuinely lost or another connection shares the path?** The supplied LEO model makes this question testable through changing forwarding paths and propagation delays. It does not contain default radio errors, handover outages, or varying link capacities. Real Starlink measurements motivate careful evaluation; they do not validate those absent mechanisms in our simulator.

Begin with a positively identified episode: an original segment is accepted by the receiver before the sender retransmits it and enters recovery. Then show that changing the packet-count loss threshold prevents the episode, while local delivery improvement and whole-run delivery remain different outcomes. The q75 follow-up supplies a useful negative result: protecting an early event can change later congestion history and finish behind baseline. Its later-window control supports a conditional explanation without accounting for every subsequent queue interaction.

Next explain the price of waiting for more feedback. In finite transfers with an actual loss, a large threshold can delay repair or leave too little following feedback. The existing known-size exemption avoids selected small-flow penalties by retaining baseline detection, but its 21/22-MSS boundary and last-segment controls expose the limits. K8 is a tested compromise, not an optimal value: it reduces the demonstrated 22-MSS loss penalty while failing to retain K20's benefit in the synthetic 80-MSS reordering case.

Finally connect the single-flow tradeoff to coexistence. PR12 already shows that a guarded flow's gain or loss depends on start order and competing-flow history. Its simultaneous-start GD audit identifies delayed repair of a genuinely dropped packet as the first transport difference. The new K8 comparison shortens that local retransmission delay from 19.502288 to 5.735962 ms, yet produces a lower Jain index than K20 in all three simultaneous-start policies. The staggered-start exports match their corresponding K20 metrics, and separate normalized full-trace comparisons establish the stated observed-trajectory equality. This is a useful adverse result: reducing one real-loss cost does not make K8 a safer or generally better coexistence policy. An unchanged sum or a better Jain index alone does not establish that both connections benefit.

The contribution is a **bounded, reproducible mechanism and tradeoff study of an existing threshold intervention**. Raising reordering tolerance is established prior work. This is not a new congestion-control algorithm, an NCR or RACK implementation, an autonomous route detector, or a demonstrated improvement to deployed Linux/Starlink TCP.

## 2. Six-page allocation

The [course reference](../LAB_REFERENCE.md#submission-and-dates) requires the unchanged IEEE conference template, two columns, 10-point Times, Team ID and every member's name under the title. Sections 1–6 together have a **six-page limit**; references and optional appendices are outside that limit. The budget below includes abstract, figures, captions, and tables. Actual compliance must be checked after rendering the final PDF.

| Required section | Target pages | Argument and evidence to retain |
| --- | ---: | --- |
| 1. Introduction | 0.50 | Research question; course-model scope; short related-work positioning; bounded contributions. Include the abstract in this space. |
| 2. Problem Statement | 1.00 | One packet/ACK/application timeline establishing unnecessary recovery; distinguish loss detection from CUBIC growth; introduce genuine-loss and coexistence costs. |
| 3. Proposed Ideas | 0.75 | Externally scheduled K3→K20/K8→K3 intervention; known-size exemption; safe restoration and information/deployment assumptions. |
| 4. Experiment Setup | 1.00 | Parameter bases, separate LEO/synthetic/competition conditions, metric definitions, provenance and deterministic reproduction. |
| 5. Evaluation | 2.50 | Local versus whole-run benefit; q75 counterexample; finite-loss/reordering tradeoff; K20 competition and window audit; K8's local improvement and coexistence counterexample; limitations. |
| 6. Conclusion | 0.25 | Answer the supported question without a universal performance or deployment claim. |
| Total | **6.00** | A planning target, not a rendered page-count result. |

Keep the full case inventory, lengthy packet excerpts, notification-offset sweep, terminal-hole details, and exact reproduction commands in the appendix or submission README. Select cases by research question; do not treat the number of runs as the contribution. If space becomes tight, combine the q75 delivery timeline and local/whole-run table rather than dropping the negative result.

## 3. Section-level writing plan

### Introduction

Use Hypatia to motivate route-induced overtaking and evolving propagation delay. Cite TCP-NCR for the established robustness/loss-repair tradeoff. Cite the Starlink congestion-control study only for its evaluation approach: distinguish transient behavior, delivery metrics, and coexistence. Its Linux/access-network findings are not outcomes of our ns-3 ISL model.

A suitable contribution list is: (1) packet-level identification and controlled prevention of one unnecessary recovery; (2) measured genuine-loss and finite-flight counterexamples plus a restricted known-size exemption; (3) single-flow follow-up and same-path K8/K20 competition controls exposing history-dependent costs. The last point includes shorter local loss repair together with worse simultaneous-start delivery balance; retain both outcomes during team review.

### Problem Statement

Use the original q100, 10-Mbit/s, 26.2-second episode as the primary mechanism figure. Join original transmission identity, receiver acceptance, sender ACK/SACK, recovery, and retransmission. The existing source/trace analysis identifies SACK packet-count presumed-loss marking in that episode; do not rewrite it as simply “three duplicate ACKs.” State the coverage limit: connected drop hooks plus positive receiver acceptance do not audit every possible receiver rejection path.

Explain why the causal evidence needs more than a congestion-window dip or a geometric RTT change. The routing-timing control supports dependence on the forwarding transition and packets in flight but does not isolate propagation delay from all new-path queue effects. A later q75 event with increasing total propagation RTT also warns against equating all reordering with an RTT decrease.

### Proposed Ideas

Describe the already implemented sender intervention, leaving CUBIC's growth equation unchanged. Baseline uses K3; selected tests use K20 or K8 during absolute, externally supplied intervals. Activation does not clear previously marked SACK losses. Restoration occurs when the socket state permits and can be later than the requested end; a restore timer does not itself generate feedback or implement RACK-TLP.

Describe the optional exemption as an upfront check of the application's known total size: `ceil(MaxBytes / SegmentSize) <= 21` retains K3. This is not remaining-flight or tail detection. The exemption can relinquish reordering protection, does not solve arbitrary finite-flight starvation, and requires application information unavailable to some open-ended streams. The 100-GB competition flows are far above the cutoff, so their K8 comparison does not validate small-flow exemption behavior.

Address the handout's information requirements explicitly. The prototype uses an oracle schedule from known simulation events. An operator notification mechanism would need affected-flow mapping, expected event time, uncertainty and expiry, timely delivery, and sender integration. Such a mechanism, its message overhead, and imperfect-notice behavior have not been implemented. Existing shifted-window tests are timing sensitivity controls, not a notification protocol.

### Experiment Setup

Use one concise parameter table with separate families:

| Family | Conditions to identify | Basis and restriction |
| --- | --- | --- |
| Original mechanism/phase two | Course ns-3.48/Hypatia; supplied 200-s Seoul–London state; 100-ms updates; q100/10 Mbit/s primary single flow | Reproduce the established episode; exploratory operating point, not measured deployed capacity. |
| PR10 single-flow follow-up | q75, q50, q75 start=1; 10 Mbit/s; 200 s; windows **26.1–26.5 and 121.5–121.9 s** | Test later history and restricted threshold sensitivity on the same path. |
| Finite diagnostic controls | 100 Mbit/s; q2000; 4 s; declared size/drop position; fixed delay or 50→45-ms step at 0.201 s | Isolate genuine loss and reordering; synthetic cases are not additional LEO performance results. |
| PR12 and new K8 competition | q100; 10 Mbit/s; two 100-GB CUBIC flows; starts 0/0 or 0/10; 200 s; windows **26.1–26.5 and 74.9–75.3 s** | Compare unchanged DD with K8/K20 GD, DG, GG on matched inputs. Retain the old second window to make the bridge controlled. |

Retain seed `123456789`, MSS 1,380 B, initial cwnd 10 segments, 32-MiB buffers, SACK/timestamps/window scaling, and no pacing in the main CUBIC cases. Explain q/rate/window/cutoff choices as diagnostic choices; neither K8 nor cutoff 21 is a proved optimum. The older 100-Mbit/s BBR/NewReno/Vegas summaries are context rather than matched controls for the 10-Mbit/s study.

Define unique ordered receiver-application goodput as `8D / (10^6 T)` Mbit/s over a named half-open interval. Distinguish it from sender ACK progress and unique wire payload. Finite-flow completion is final complete application delivery minus application start and includes establishment; ongoing bulk flows have no completed-flow FCT. Competition uses the same denominator for both flows: 0–200 s for simultaneous starts and **10–200 s** for the common-active staggered comparison. Report per-flow delivery, the sum, Jain index, recovery/retransmission/LOSS entries, and actual guard activation/restoration. LOSS entries are not automatically timeout counts; retransmission rows are not independent lost-packet episodes.

### Evaluation

Order subsections by the question answered, not by who ran a batch:

1. **Preventing a verified episode:** original first-event goodput 9.485568→9.622464 Mbit/s (+1.4432%), compared with only 9.5443560→9.5465088 Mbit/s over 200 s (+0.02256%). Keep both scales visible.
2. **Why local success can finish worse:** q75 first-only ends 474,720 B behind; targeting both the 26.2- and 121.6-second events ends 6,900 B ahead (+0.0029%). The timeline, packet evidence, and later-window control support a conditional explanation, not a complete decomposition of every late byte difference.
3. **Loss versus reordering:** plot completion time for 20/22-MSS first loss and 80-MSS delay-step controls. K20's 22-MSS loss penalty is 100.119680 ms; K8 plus exemption's is 0.114720 ms. Conversely, K8's 80-MSS step completion remains 0.611527200 s, while K20 reaches 0.430944960 s. K8 therefore does not dominate K20.
4. **K20 coexistence and first divergence:** simultaneous-start GD changes the guarded flow by −7.20% and its competitor by +6.94%, with almost unchanged total delivery. The tagged real loss has 19.502288-ms later retransmission and 19.502455-ms later ordered repair. First-only reproduces GD-with-both and later-only reproduces DD in both start schedules. Do not attribute the entire long-run share change to that initial delay.
5. **K8 competition bridge:** compare all six validated exports with DD and matched K20. The first genuine-loss episode has a 5.735962-ms retransmission delay and 5.736017-ms ordered-repair delay under K8, versus 19.502288 and 19.502455 ms under K20. Despite this improvement, simultaneous-start Jain indices are lower for K8 in GD, DG, and GG; staggered-start exported metrics are unchanged from K20. All 15 measurement/legacy CSVs per staggered pair match after threshold/control normalization, with independent lifecycle/configuration checks. This is a counterexample to inferring better coexistence from a smaller local repair penalty. No complete causal explanation of the final shares is established.
6. **Interpretation limits:** one route, deterministic traffic, oracle timing, no RACK-TLP comparator, no modeled notice transport, and no independent seed distribution. Exact replay checks reproducibility, not statistical confidence. PR12's original K20 GG terminal accounting distinguishes cutoff-specific ordered-delivery deficit from wire arrival; it does not establish eventual delivery or accepted-buffer occupancy. Do not transfer that exact accounting to K8 GG without its separately reviewed sequence audit; no such additional causal claim is needed for this report narrative.

### Conclusion

The defensible ending is that route-informed reordering tolerance prevents a verified response under selected conditions while introducing genuine-loss and coexistence costs. The smaller threshold and known-size exemption address particular costs and retain documented failure cases. The K8 competition result makes the distinction concrete: faster local loss repair coexists with worse simultaneous-start delivery balance. Do not conclude that a universal controller, deployment-ready information source, or generally superior threshold has been established.

## 4. Claim–evidence map

| Candidate claim | Evidence to use | Boundary to preserve |
| --- | --- | --- |
| Original recovery followed receiver acceptance of the original | `code/kim-study/EXPERIMENT_NOTE.md`, `evidence/event26_evidence.csv`, source patch and causal figure | This tested ns-3 stack; acceptance evidence is stronger than wire arrival alone. |
| K20 prevents that episode with modest whole-run benefit | `PHASE2_NOTE.md`, `phase2_results.csv`, bulk/event summaries | Local benefit is not a large full-run throughput gain. |
| Known-size exemption removes selected small-flow penalties | Phase-two first/middle-loss and 21/22-MSS controls | Bypassing K20, not faster detection while retaining K20; no general tail solution. |
| K8 trades protection for faster genuine-loss repair | PR10 `results.csv` and finite case summaries | Post-hoc refinement; smallest successful tested value, not a proven minimum. |
| Earlier protection can worsen later delivery | PR10 q75 timeline, cwnd checkpoints, tagged 121.6-s packet evidence, later-window controls | Same path/history; not every queue state or subsequent difference is isolated. |
| K20 redistributes delivery in coexistence | PR12 original `results.csv` and one-second bins | Guarded/default shares and total delivery must be shown together; start order matters. |
| The first GD window is sufficient for its observed trajectory here | PR12 `ablation.csv`, `trajectory-equality.json` | 15 CSVs per pair; only threshold/control normalization and wall-time exclusion; internal predicates are not fully instrumented. |
| First simultaneous GD divergence delays genuine-loss repair | PR12 `first-loss.json`, linked tagged TcDrop and ACK/application rows | Not a spurious-loss example; 19.5 ms does not explain the complete long-run allocation by itself. |
| Original K20 GG's terminal app deficit has exact sequence accounting | PR12 `terminal-gap.json` | Finite cutoff; wire Rx is pre-processing; no drain or eventual-delivery control. This is not an accounting claim about K8 GG. |
| K8 shortens one genuine-loss delay but worsens simultaneous-start balance versus K20 | Six exporter-validated K8 cases: [results](../experiments/assets/cubic-competing-k8-20261010/results.csv), [comparison windows](../experiments/assets/cubic-competing-k8-20261010/comparison/windows.csv), [first-loss audit](../experiments/assets/cubic-competing-k8-20261010/first-loss.json) | Three simultaneous modes have lower Jain; join10 equality has a [separate trajectory check](../experiments/assets/cubic-competing-k8-20261010/join-trajectory.json). No universal fairness or invisible-state identity claim. |
| Reported deterministic outputs are reproducible | Existing v6/PR10 replay records; PR12 representative replay; [new K8 representative replay](../experiments/assets/cubic-competing-k8-20261010/reproduction.json) and archive verification | State exactly which cases were replayed; the other five new K8 cases were validated, not replayed in that fresh volume. Wall-clock timing differs. |

## 5. K8 result table and figure plan

The six new cases comprise GD, DG, GG at each of the two start schedules. Reuse original DD and the corresponding K20 policies; preserve their input/provenance records. Labels describe the guarded position(s), not a new TCP implementation.

| Start schedule | K8 policy | Flow 0, Mbit/s | Flow 1, Mbit/s | Sum, Mbit/s | K8 Jain | Matching K20 Jain |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 / 0, interval 0–200 s | GD | 3.9098160 | 5.6688744 | 9.5786904 | 0.967376 | 0.992069 |
| 0 / 0, interval 0–200 s | DG | 4.0846896 | 5.4945528 | 9.5792424 | 0.978798 | 0.989666 |
| 0 / 0, interval 0–200 s | GG | 5.4699888 | 4.1048376 | 9.5748264 | 0.980077 | 0.996213 |
| 0 / 10, interval 10–200 s | GD | 4.3972901 | 5.2180269 | 9.6153171 | 0.992767 | 0.992767 |
| 0 / 10, interval 10–200 s | DG | 3.6269305 | 5.9882703 | 9.6152008 | 0.943119 | 0.943119 |
| 0 / 10, interval 10–200 s | GG | 4.3972901 | 5.2180269 | 9.6153171 | 0.992767 | 0.992767 |

Goodput is rounded to seven decimal places and Jain to six here; sum rates are independently rounded from total bytes. Simultaneous DD's Jain is 0.999650; staggered DD's is 0.943119. Per-mode references are the original DD and matching K20 GD/DG/GG; the new rows do not replace those controls. Source rows are retained in [results.csv](../experiments/assets/cubic-competing-k8-20261010/results.csv) and the [combined comparison](../experiments/assets/cubic-competing-k8-20261010/comparison/windows.csv). The [join trajectory audit](../experiments/assets/cubic-competing-k8-20261010/join-trajectory.json) verifies all 15 measurement/legacy CSVs per K20/K8 pair after removing the threshold field and `THRESHOLD_*` control events. GD/DG/GG respectively have 13/13/11 already byte-identical files; only wall-clock `timing_results.csv` is excluded. Complete threshold lifecycle, intended K, actual schedule, and configuration identity are checked separately. This equality does not expose all internal TCP decisions.

| Matched simultaneous GD actual-loss audit | K8 delay from DD, ms | K20 delay from DD, ms |
| --- | ---: | ---: |
| First retransmission | 5.735962 | 19.502288 |
| Confirmed ordered application repair | 5.736017 | 19.502455 |

Also retain integer delivered bytes per flow for each interval, case/source identifiers, patch/binary/runner/config/schedule hashes, guard K validation, and raw/analysis fingerprints in the compact artifacts. Do not substitute rounded table equality for trajectory equality. Reusing prior references does not make them newly rerun results. Record a failed case or unmet validation explicitly rather than dropping its row.

Proposed body exhibits: **Fig. 1** original causal packet/ACK timeline; **Fig. 2** q75 cumulative application-delivery difference with the target events; **Fig. 3** finite-loss versus synthetic-reordering completion tradeoff; **Fig. 4** matched per-flow competition results for DD/K8/K20, optionally with a small first-loss inset. **Table I** holds parameter bases; **Table II** holds a compact comparison of local, whole-run, and coexistence outcomes. Move the full six-case table above to the appendix if the competition figure communicates the same results more legibly. Every final exhibit needs a source-case list and an exact generation command in the submission README.

## 6. Source snapshots and attribution

These are reading snapshots. A report-source commit is not automatically the commit that generated a case. Preserve execution-time case manifests and hashes when integrating results from multiple branches. The three PRs below were open with no submitted reviews when checked for this outline; PR12 was temporarily Draft during the K8 extension. Their contents are proposals/evidence for team review, not merged team decisions.

| Contribution | Reading snapshot | Experimental provenance and attribution |
| --- | --- | --- |
| Course requirements/model | [LAB_REFERENCE.md](../LAB_REFERENCE.md), [handout](../CS30401_26F_Lab1_Handout.pdf), [environment guide](../CS30401_26F_Lab1_Environment_Guide.pdf) | Official course materials govern submission requirements; the reference's historical planning paragraphs are not current experiment results. |
| Original mechanism, phase two, existing English draft | Merged study at `b60e8e019053c7d33b853510ec06c3d94ee78faf`; `code/kim-study/{EXPERIMENT_NOTE.md,PHASE2_NOTE.md,report/kim-study-draft.tex}` | kim-seongchan's independent study; canonical v6 patch. Original and replay histories remain separate. Existing draft predates PR10/12 and has unconfirmed team author names. |
| Single-flow follow-up | [PR10](https://github.com/Jeongmin07/CS30401-Lab1/pull/10), `036c9d84653a92944705c8af9d88313d3402443d`; `docs/experiments/20261010-cubic-followup.md` | Jeongmin07; 29 new configurations plus two originals replayed. Do not transplant its 121.5-s window into the competition comparison. |
| Literature/model translation | [PR11](https://github.com/Jeongmin07/CS30401-Lab1/pull/11), `503508d75371611144b348c74cd2a21bd9744e7b`; `docs/research/20261010-leo-tcp-literature.md` | kim-seongchan's source-reading note. Reviewed primary-source versions and locators are recorded there; no new experiment. |
| K20 competition and causal/terminal audits | [PR12](https://github.com/Jeongmin07/CS30401-Lab1/pull/12), `aa4d4778a95daf310db0a4fb90c6453dec226310`; `docs/experiments/20261010-cubic-competing{,-audit}.md` | kim-seongchan; original eight cases used `95c306dd9fc1d6c09f9d5ebccfc27215f8c41a24`, four window controls used `d5dcdce5cdfa9f3098a52ab7f449e3f6fe87f9f1`. Audit scripts were added after simulation and have separate hashes. |
| New K8 competition bridge | [Experiment record](../experiments/20261010-cubic-k8-competing.md), [compact assets](../experiments/assets/cubic-competing-k8-20261010/); execution source `7266051e6ed4cab15c13d59c555ca32f2803e479` | Six cases completed and exporter-validated; one representative fresh-volume replay matches measurement CSVs and full analysis. Source revision was read from every actual case manifest; existing DD/K20 references retain their original sources. |

Shared official image digest: `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`. Canonical v6 patch SHA-256: `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`. The recorded LEO binary SHA-256 in PR10/12 is `de9f678113c37a72df7e3215e876f18945c0ccecf9123f60fc8f655f9d9a6eab`. Full artifact hashes belong in the README/appendix rather than consuming main-body space.

The new six-case raw archive contains 120 files, is 63,853,717 B compressed, and has SHA-256 `4c0c4ffe7b978d31c3d345c4b63ebdc198b4e07f016070c4be44be52674d8e72`. It is an [additional asset in the existing competition release](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/cubic-competing-20261010/cubic-competing-k8-20261010.tar.gz); [archive manifest](../experiments/assets/cubic-competing-k8-20261010/archive-manifest.json) and [member verification](../experiments/assets/cubic-competing-k8-20261010/archive-verification.json) identify it separately from the old twelve-case archive. All 120 member sizes/hashes match the published and embedded manifest, and the [GitHub asset verification](../experiments/assets/cubic-competing-k8-20261010/github-asset-verification.json) confirms uploaded size/digest while preserving the original asset.

The new [representative replay](../experiments/assets/cubic-competing-k8-20261010/reproduction.json) runs `same-start-gd-k8` on a fresh official ns-3 volume. All 15 measurement/legacy CSV hashes and full-analysis SHA-256 `d37bf9fe8de2af3d9da6f926411c61132a1156aec05578ed5c0452474a1a05a0` match exactly; only `timing_results.csv` differs and its fingerprints are disclosed. This is one deterministic reproduction check, not an independent statistical sample or a replay of the other five K8 cases.

## 7. Primary references to cite selectively

Use the repository's verified source notes and the versions they reviewed. Do not add a paper's unverified numerical results to support our claims.

- Kassing et al., **Exploring the “Internet from space” with Hypatia**, IMC 2020: [author PDF](https://bdebopam.github.io/papers/imc2020-hypatia.pdf), [DOI](https://doi.org/10.1145/3419394.3423635). Motivation and simulator foundation, not validation of our CUBIC intervention.
- Xu et al., **CUBIC for Fast and Long-Distance Networks**, [RFC 9438](https://www.rfc-editor.org/rfc/rfc9438.html). Controller relevance; distinguish the standard from this particular ns-3 recovery stack.
- Bhandarkar et al., **Improving the Robustness of TCP to Non-Congestion Events**, [RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html). Established tolerance/feedback tradeoff; our fixed scheduled threshold is not NCR.
- Allman et al., **Early Retransmit for TCP and Stream Control Transmission Protocol**, [RFC 5827](https://www.rfc-editor.org/rfc/rfc5827.html). Finite-flight feedback motivation; not an implemented comparator.
- Cheng et al., **The RACK-TLP Loss Detection Algorithm for TCP**, [RFC 8985](https://www.rfc-editor.org/rfc/rfc8985.html). Explain time-based detection/probing and the scope limit; no RACK-TLP performance ranking is supported.
- Garcia, Sundberg, and Brunstrom, **TCP Congestion Control Performance over Starlink**, ANRW 2025: [author PDF](https://www.diva-portal.org/smash/get/diva2%3A1992495/FULLTEXT01.pdf), [DOI](https://doi.org/10.1145/3744200.3744760). Borrow evaluation distinctions and competition/start-order attention. Its prefix-based completion measures from long transfers are not our independently sized finite-flow controls, and its Linux access model differs from the supplied ISL model.

SaTCP and other route-aware proposals in PR11 can support one brief information-assumption paragraph if needed. None was ported or evaluated here. A full related-work catalogue would displace the assignment's mechanism/evaluation argument without adding evidence.

## 8. Decisions and completion work

**Proposals in this outline:** the title, narrative, page allocation, selected figures/cases, and the integrated tradeoff framing. **Completed evidence:** the original/phase-two study, pinned PR10/12 results/audits, six exporter-validated K8 cases, staggered K20/K8 trajectory checks, one new K8 representative fresh-volume replay, and 120-member archive verification. A separate [K8 terminal-hole audit](../experiments/assets/cubic-competing-k8-20261010/terminal-gap.json) also verifies its own cutoff-specific accounting; it can be an appendix check, and must not be substituted for the original K20 audit. **Still team decisions:** final topic/policy and parameter set, author names and contributions, report/patch integration owner, PR review/merge owner, and which findings enter the final submission. Do not turn this outline into `docs/PLAN.md` decisions.

Integrate the linked evidence into the final report while retaining favorable, adverse, and unchanged outcomes. Use the existing English draft as a source of verified mechanism prose, not as an already integrated final report. Keep distinct schedules, rates, queues, metrics, and execution-time source identities explicit; confirm shared raw-archive access before relying on its external release link in the final README.

For submission by **2026-10-13, 23:59 KST**, produce the final English `report.pdf`, `README.md`, and `code/` archive; retain the unchanged conference template; give every figure/table a reproduction command; submit the canonical patch and exact required code/dependency files. Exclude raw logs, generated state, the ns-3 tree, and builds from the course archive. Check the selected results from the final bundle in a fresh official volume and check the rendered six-page body, citations, units, author list, and contribution surveys. The outline itself does not certify those final checks as complete.
