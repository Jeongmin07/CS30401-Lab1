# Native CUBIC pacing and an operator-capacity ceiling

Read the [fixed declaration](../../docs/experiments/20261013-queue-pacing.md). Initial controls are pacing OFF, native defaults ON, and native ON with a predetermined payload ceiling of 9623430 bps for the physical 10 Mbps/1380-byte payload/1434-byte serialized data packet. Current selective+tail policy remains identical; additional observers integrate exact queue state without changing native decisions. No simulations launch before the parent's source checkpoint.

The optional five-case safety stage is declared before outcomes, conditional on an initial winner. Build/source/runtime/actual inputs and failed attempts must be preserved separately. Publication and Git writes are owned by the parent chat.
