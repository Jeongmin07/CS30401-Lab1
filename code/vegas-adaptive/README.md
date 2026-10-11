# Vegas-A-inspired follow-up (Jeongmin07)

This is a new endpoint-only candidate study, not a team direction or a merge decision.
Branch starts from main b60e8e019053c7d33b853510ec06c3d94ee78faf.
It reuses selected tools and the full v1 patch from PR #14 at
4a91c32cf90ea4aa6f81cc81accb2136e6e1f193, copied into this separate directory.
The upstream patch SHA256 is
25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59.
This is an explicit experimental dependency on an unmerged PR; it does not
modify the teammate's branch, canonical kim-study patch, or shared PLAN.

Candidate: adaptive Alpha/Beta and one previous valid CA-cycle throughput
estimate, based on Srijith/Jacob/Ananda (2005) section 3 and author Code3:
https://srijith.net/publications/journals/TCP_Vegas-A_COMCOM05.pdf
https://github.com/skn/vegas-a/blob/a379c93fe70d5d7b16e620d0e046a69e26a1ee0e/codes/tcp-vegas.cc.code3

Declared adaptation: course SRTT input, existing integer Vegas diff, initial
Alpha/Beta 2/4 with lower bounds 2/4, cycle-granularity cwnd +/-1 MSS. The NS-2
original uses initial/lower 1/3, different RTT/flight estimates and ACK-applied
increase. Therefore this is inspired by Vegas-A, not an exact reproduction.
Do not combine it with recent-min renewal. Startup, recovery and socket loss
handling remain the supplied implementations. Reset previous-rate validity on
Vegas disable/enable or an invalid CA cycle; the first valid CA cycle follows
ordinary Vegas and seeds history. Alpha/Beta retain learned values through
recovery. Record every adaptive decision for an independent rule audit.

Initial matched tests: supplied LEO solo and fixed 90ms propagation with CUBIC
joining at 80s; 200s, 100Mbps, queue100, seed123456789, no pacing, 100GB.
Both baseline and adaptive use the same new binary, renewal off. Check the
baseline against PR14's originals. Expand to solo 90->96ms step and fixed solo
only if the initial results justify explaining the mechanism. No parameter
sweep or selective tuning. Compare app delivery, common-window sharing,
direct micro queue delay/occupancy, drops, retransmissions and state traces.
Replay a representative case in a new volume, archive raw inputs with hashes,
and publish compact evidence plus the full final patch. No merge authorized.
