# Route-shortening CUBIC diagnostic

This track first tests the premise for proactive cwnd drain or pacing: a natural supplied route shortening must be associated with a concrete, attributable queue/drop surge, rather than only reordered packets or a smaller propagation BDP.

Read the [predeclared diagnostic](../../docs/experiments/20261012-orbit-cubic-down.md). The parallel `orbit-cubic-up` track owns the fresh shared passive baseline; no duplicate baseline or controller has been launched here. Controller implementation is conditional on the measured gate. Source and result receipts will distinguish existing evidence from new measurements.
