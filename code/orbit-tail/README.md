# One extra final original segment during a selective loss wait

Experimental opt-in `ns3::TcpSocketBase::OrbitTailAdmission`, default false. It permits at most one extra original segment per active shared-wait episode after ordinary ACK-driven sending has used its normal allowance. It requires unique new SACK progress, application close-on-empty/send shutdown, one MSS or less unsent payload, sequence-based receiver-window compliance, and `pipe+payload <= cwnd+MSS`. It does not change cwnd, delivered/PRR accounting, the loss deadline or normal RTO. This is not RFC8985 TLP.

Read the [predeclared ten conditions](../../docs/experiments/20261013-orbit-tail.md). Existing orbit-loss files and runs remain unchanged. The standalone combined patch is based on the exact final V2 SHA recorded there. Development, runtime and input receipts must precede the first simulation; publication is owned by the parent task.
