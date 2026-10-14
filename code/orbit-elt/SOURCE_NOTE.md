# Bounded ELT-inspired source overlay

This is an opt-in sending adaptation for CUBIC/SACK/PRR inside the existing short selective loss wait. It is **not complete TCP-NCR**, TLP, RACK, or a new loss detector. The exact frozen `ace08` source is the input; `implement.py` rejects different socket source hashes and modifies only `tcp-socket-base.cc` and `.h` in the supplied new tree. It performs no build or simulation. All earlier submission code, runtime volumes and results remain unchanged.

## Modes and placement

`ns3::TcpSocketBase::OrbitEltMode` is 0 OFF, 1 Aggressive, or 2 Careful. OFF leaves native sending and the configured old one-MSS tail rule unchanged. Modes 1/2 disable that tail rule, so two sending allowances cannot stack.

`ReceivedAck` saves `HighTx - Head` **before** `ReadOptions` changes the SACK scoreboard. If that ACK starts the existing actual selective wait, the saved value becomes fixed `FlightSizePrev` (`F0`). Activation follows stale-ACK validation and happens once per existing wait episode. It therefore starts at the first presumed-loss deferral, rather than at RFC 4653's first SACK. A later cumulative ACK cannot refresh/restart the sending allowance within that same episode.

Native SACK already frees pipe. Consequently, this overlay governs the **new-data branch within `SendPendingData`**, rather than adding transmissions after its ordinary loop. Outside the active phase it uses unchanged native `AvailableWindow`. While active in `CA_DISORDER`, only processing unique new SACK information drives transmission. Application/pacing callbacks without such processing cannot generate an allowance. Duplicate SACK information produces no new `bytesSacked` in the existing tx-buffer implementation.

## Fixed permission and unchanged packet accounting

The new-data eligibility test is `pipe + Skipped + MSS <= F0`, with a separate receiver sequence-window bound. It temporarily uses `F0 - pipe - Skipped` rather than min-with-native-cwnd permission; the cwnd field is not inflated to create credit. `F0` is cumulatively unacknowledged data, including already SACKed items, and is **different from pipe and cwnd**. Pipe is the native `sent - SACKed - presumedLost + retransmitted` estimate, not a direct network occupancy measurement.

Aggressive keeps `Skipped=0`. Careful adds the actual full-MSS bytes to `Skipped` after each original send, withholding the next equivalent room. This follows the ordering of RFC 4653 E2/E3/E4: the pre-send test is exact; actual post-send pipe must remain at most `F0`, but Careful's post-send **virtual** `pipe + Skipped` may reach `F0 + MSS`. Skipped is not transmitted traffic.

Each accepted segment must be a full MSS at the actual high-TX frontier. The existing receiver-window, NextSeg, pacing, Nagle, packet tags, retransmission distinction, RTT history, `NotifyDataSent`, FIN handling and next-TX updates are retained through native `SendDataPacket` and the ordinary loop. Stored loss selection returns to native sending permission. The initial 20/21/24-MSS pilot contains full segments; partial-tail, receiver-edge FIN and pacing-enabled behavior remain limited source reasoning unless separately observed. No fake delivery bytes or old SACK credits are passed to PRR.

## Termination and burst control

On cumulative ACK advancement, T1/T2 run once **after** native `DiscardUpTo`, `ProcessAck`, NewAck/CC processing and before ordinary sending:

`cwnd = min(postACK data FlightSize + MSS, F0)` and `ssthresh = F0`.

The cwnd-inflation trace value is synchronized to that cwnd. FIN sequence space beyond the data high-TX frontier is treated as zero outstanding data, not unsigned wrap. When the ACK first cancels the orbit wait inside `ProcessAck`, a pending CACK-exit flag preserves this later clamp. A native recovery/ECN/RTO cancellation clears the flag and wins; T1/T2 cannot overwrite that subsequent native loss response. This termination can alter cwnd/ssthresh and future CUBIC behavior; it is not the old tail rule's admission-only unchanged-cwnd guarantee.

The shared loss deadline, epoch end, stock recovery, ECN, RTO and socket timer cancellation terminate ELT without T1/T2. There is no new timer, deadline refresh, K change, synthetic ACK or PRR bypass. The existing selective cohort, loss budget and hard-expiry reevaluation remain unchanged.

## Trace contract

New file: `tcp_flow_0_orbit_loss_elt.csv`, beside existing loss/tail traces. Header:

```text
flow_id,time_ns,event,mode,epoch_ns,deadline_ns,saved_flight_bytes,pipe_bytes,skipped_bytes,cwnd_bytes,ssthresh_bytes,unsent_bytes,new_sack_bytes,sent_bytes,seq,head_seq,high_tx,receiver_right_edge,active,phase_used
```

`ELT_BEGIN` contains the pre-SACK `F0` and post-SACK pipe. Each `ELT_SEND_BEFORE` records pre-send pipe/Skipped and **planned** MSS bytes; its same-time `ELT_NEW_TX` records the native actual return, post-send pipe and post-send Skipped. `phase_used` means activation has been consumed for the episode, not one packet. `ELT_CACK_BEFORE` is after native ACK/CC processing and before the formula; `ELT_EXIT_CACK` contains its result and `active=0`. `ELT_CACK_PENDING` identifies an earlier orbit cancellation awaiting that formula. Other exit/skip event names describe why sending or the phase stopped. Deadline/timer events carry no fabricated new-SACK delivery.

## Research boundary

[RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html), sections 3.1–3.4, supplies the fixed-flight/Skipped sending and anti-burst ideas. This adaptation retains K3 and the short orbit deadline, uses one activation per selective-wait episode, and keeps native CUBIC/PRR recovery. It does not implement NCR's adaptive DupThresh, full phase restart, or roughly RTT-long disambiguation. A improvement must be demonstrated by actual APP completion/throughput, original TX/ACK chronology, pipe/window guards and genuine-drop controls.

An ELT phase gated on selective waiting has no direct action at a transition where that wait never starts. The finite final-packet stall and whole-run/T75 queue overflow are separate outcomes; neither an improvement nor a universal solution is assumed here.
