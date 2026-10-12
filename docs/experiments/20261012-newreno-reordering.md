# NewReno Reordering Cross-Check

## Status

Completed exploratory experiment on 2026-10-12. This is an independent cross-check of the CUBIC reordering result, not a team-approved final topic. The raw traces remain in the `lab1` container under `/tmp/cs30401-study/`; the compact results are in [results.csv](assets/20261012-newreno-reordering/results.csv).

## Question

Does the route-change-induced spurious recovery observed with CUBIC also occur with NewReno, and does temporarily increasing the packet-count reordering threshold have the same genuine-loss cost?

## Environment and method

- Official image: `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1`.
- Canonical version-6 patch SHA-256: `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`.
- NewReno used the same instrumented sender/receiver traces, transmission tags, drop hooks and analyzer as the CUBIC study.
- The microbenchmark used 100 Mbit/s, 2,000-packet queues and the existing stable, delay-step and intentional-loss controls.
- The LEO check used the supplied Seoul-London state, 100 Mbit/s, 1,000-packet queues, nodes 1584 to 1585, and 85 seconds. The threshold-64 windows were 26.1--26.5 and 74.9--75.3 seconds.

Representative commands inside the patched container were:

```bash
python3 /tmp/kim-study/run_study.py nr-step-base --kind micro --cc TcpNewReno --rate 100 --queue 2000 --duration 4 --before-ms 50 --after-ms 45 --event-s 0.201
python3 /tmp/kim-study/run_study.py nr-step-guard64 --kind micro --cc TcpNewReno --rate 100 --queue 2000 --duration 4 --before-ms 50 --after-ms 45 --event-s 0.201 --parameters 'study_threshold=64;study_windows=190000000:700000000'
python3 /tmp/kim-study/run_study.py nr-loss-base --kind micro --cc TcpNewReno --rate 100 --queue 2000 --duration 20 --event-s 10 --loss-s 10.06
python3 /tmp/kim-study/run_study.py nr-loss-guard64 --kind micro --cc TcpNewReno --rate 100 --queue 2000 --duration 20 --event-s 10 --loss-s 10.06 --parameters 'study_threshold=64;study_windows=9990000000:10300000000'
python3 /tmp/kim-study/run_study.py nr-leo100-base --kind leo --cc TcpNewReno --rate 100 --queue 1000 --duration 85 --trace 1
python3 /tmp/kim-study/run_study.py nr-leo100-guard64 --kind leo --cc TcpNewReno --rate 100 --queue 1000 --duration 85 --trace 1 --parameters 'study_threshold=64;study_windows=26100000000:26500000000|74900000000:75300000000'
```

Each completed run was analyzed with `analyze_study.py`; the failed parallel attempt of the guarded LEO case was discarded and the case was rerun alone successfully.

## Observations

In the delay-step microbenchmark, NewReno baseline produced one accepted-original retransmission and one recovery entry despite zero observed drops. The guard produced no recovery entry and retained the original delivery. In the actual-loss control, the intentional drop was observed in both variants. The guard delayed first retransmission from 50.34912 ms to 57.34704 ms and sequence-gap repair from 106.57488 ms to 113.57280 ms.

In the 85-second LEO run, baseline had two candidate unnecessary recoveries in the 26.2- and 75.0-second event windows. The guard had zero candidate unnecessary recoveries and zero retransmission rows in those windows. Whole-run receiver application goodput increased from 88.782121412 to 95.026475294 Mbit/s, a 7.0333% increase in this single deterministic configuration. Both variants observed 936 distinct tagged drops over the full run, so the difference is not explained by a reduction in all network drops.

## Interpretation and limits

These results support the claim that the tested route-change reordering mechanism is not specific to CUBIC's window-growth equation; it also appears in the course ns-3.48 NewReno/SACK/PRR path. The guard still delays genuine-loss recovery, so it is not a universally safe improvement. The LEO comparison has one path, one seed, one 85-second duration and one threshold/window choice. It does not establish general NewReno performance, current Linux behavior, statistical confidence, or deployable notification accuracy.