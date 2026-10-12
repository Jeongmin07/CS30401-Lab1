# Exact time-area measurements

`queue_area.h` observes a queue that is empty at simulation time zero. Supply packet and byte trace changes separately using their actual old/new values and timestamps, then close the held state with `Advance(actual_cutoff_ns)`. No new simulator event is scheduled. Bins are100ms by default; missing idle intervals contribute exactly zero. A peak at an instantaneous change is separate from a nonzero area. Full time is defined only when a nonzero maximum is provided and the held packet count equals it. Use maximum0 for a combined inventory that includes requeues/in-service items without a strict packet maximum.

The caller owns coverage, native callback wiring, complete cutoff, capacities, conservation and output metadata. Do not infer old queue state from late flush snapshots, add differently weighted visit means, or omit pending/dropped residence.

`check_area.cc` validates independently calculated nonuniform integrals, both same-time callback orders, a partial last bin with held pending data, zero idle intervals, and a combined inventory above100 with no fabricated strict full time. It is a standalone metrics check and runs no ns-3 simulation. In the course image:

```sh
g++ -std=c++17 -I/home/ubuntu/ns-3.48/build/include /work/code/queue-metrics/check_area.cc -L/home/ubuntu/ns-3.48/build/lib -lns3.48-core -o /tmp/queue-area-check
LD_LIBRARY_PATH=/home/ubuntu/ns-3.48/build/lib /tmp/queue-area-check
```
