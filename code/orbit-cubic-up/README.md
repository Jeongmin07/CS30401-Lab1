# Passive source gate for proactive CUBIC window expansion

This candidate first asks whether the supplied path-lengthening transitions cause a window shortage and forward-link idle time. No scale-up policy is implemented yet. The declared diagnostic flow is one 100GB CUBIC flow, Seoul1584 to London1585, start0, 200seconds, 10 or100Mbit/s,100-packet queues, pacing off, stockMSS/SACK/PRR/K3. The maximum natural propagation increase is7.231ms(+7.98%), at187.4seconds.

`install.py` composes canonicalv6 plus passive socket window, the reused queue observer, and per-device physical transmitter busy-time observations into one complete`ns3.patch`. Apply that single patch to clean official source; do not stack it with other complete patches. Observer OFF changes no attributes, wire bytes, routing, timers, or loss decisions.

`orbit_window.csv` reads the existing AvailableWindow calculation and cached pipe; it does not call either getter again. It records each BEGIN/END callback in declared focus windows and one sample per100ms elsewhere. Queue statistics describe served device visits, not end-to-end RTT. Service bins split actual PhyTxBegin/End busy intervals at100ms boundaries; started bytes and completed receiver bytes have different attribution. Terminal active transmissions and queued packets are censored separately. Zero busy or an unknown device is not automatically the forward bottleneck.

Build with `./ns3 build -j 1`, save completed runtime hashes in`build-receipt.json`, then invoke `python3 /work/code/orbit-cubic-up/run.py cubic100-observed200`. The runner uses the finished binary directly, refuses existing run directories, checks the complete source diff and build runtime identities, and does not build during a run. All traces and attempts remain in the dedicated container; compact analysis is added after completion.

Source-window increases must be supported by actual cwnd limitation and utilization evidence. The BBR orbit-BDP result is not a CUBIC result. Geometry ratio scaling neither guarantees full utilization nor prevents queue overflow. Timing/rate errors, competition and independent statistical repetitions are outside this bounded pilot.
