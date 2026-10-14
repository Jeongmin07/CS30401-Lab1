# RFC-inspired bounded ELT experiment

Owner: Seongchan Kim. Branch: `experiment/elt-ack-clock`, based on `origin/main` (`b60e8e0`). This is a supplemental experiment, not a replacement submission.

## Dependencies and question

The unmerged [PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16) provides the frozen selective-wait/tail implementation and passive queue instrumentation. Execution dependencies are copied from commit `0a42d0e107307144842b1d3833b606645b0be934`; its pace patch has SHA-256 `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808`. The prior code, report, submission ZIP, and runtime remain unchanged.

The existing one-MSS tail admission repairs finite-transfer feedback starvation. It made no admissions in the natural bulk run and did not solve T75 queue overflow. Test whether the sending/exit discipline described by [RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html) improves the finite-size boundary and whether any resulting bulk trajectory improves queue behavior.

## Scope and limits

Implement Aggressive and Careful ELT send disciplines within the existing short orbit-gated wait. Save cumulative unacknowledged flight before the initiating SACK update, use one shared `pipe + skipped + MSS <= saved flight` allowance for new data, and apply the RFC-inspired cumulative-ACK exit window clamp once. Careful charges one additional skipped MSS per transmission; Aggressive does not. Tail admission is disabled in both ELT arms. Native receiver-window, pacing, transmission, and recovery bookkeeping remain in use.

This is **not full TCP-NCR/RFC 4653 compliance**: it retains the short orbit wait, threshold three, CUBIC/PRR recovery and RTO; starts on the existing eligible loss wait rather than every first SACK; does not implement repeated RFC T4 restart or the RFC recovery backoff. Full-MSS tests avoid assuming partial segments are full packets. No claim of fairness or fundamental queue elimination follows from this single-flow experiment.

## Predeclared physical runs (19)

- Finite genuine loss on an unchanged 50/50-ms path, with the deliberately wrong positive hint already used in PR #16: 20, 21, and 24 MSS, each under stock, selective wait, selective + one-MSS tail, ELT Aggressive, and ELT Careful. 15 runs.
- Natural Seoul–London LEO topology, 10 Mbps, 100-packet queues, 200 seconds, 100-GB single flow: stock, selective + tail, ELT Aggressive, ELT Careful. Four runs. Pacing off in all arms.

No search across all satellite paths or topology sweep. Use the existing forward-hint table and official cached state. Keep failed attempts and do not overwrite them. Freeze and publish source before building/running.

## Measures and gates

For finite runs, require complete delivered bytes; report FCT, first physical-drop-to-retransmission delay, original sends, ELT admissions, fixed saved-flight/skip accounting, and unchanged wait deadlines. OFF controls should reproduce known PR #16 results. Stop and repair if source/runtime invariants or bookkeeping fail.

For bulk, report whole-run application goodput, retransmissions/recovery, all tagged physical data losses, T26.2 [25.7,28.2), T75 [74.5,77.5), and exact source-queue time means before/after 75 seconds. Count actual active ELT waits at T75; a zero count excludes a direct local ELT intervention claim. Retain adverse results. An improvement in one flow is not sufficient evidence of fairness under competition.

Record image, source, patch, runtime, input/configuration, command and raw-output hashes in manifests. Raw traces stay outside Git; publish compact summaries and a verified compressed archive link after the runs.
