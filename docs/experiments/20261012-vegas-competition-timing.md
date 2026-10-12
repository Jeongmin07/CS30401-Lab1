# Competition-start robustness check

Owner: Jeongmin07, PR15 continuation. Predeclared before execution.
The user's latest instruction defers report/presentation work and prioritizes
research. No common PLAN change, teammate branch update or merge.

The forty-cycle recommendation rests partly on one CUBIC joining time (80 s).
Test whether its queue/sharing advantage survives a different traffic phase:
halve joining time to40 s, holding all other network and TCP conditions fixed.
This is a traffic-timing sensitivity diagnostic allowed by handout pp3–5;
it is not an independent LEO path or a realistic distribution of user arrivals.

Three new cases in `/tmp/vegas-competition-timing`:
`s3-join40-base`, `s3-join40-r20`, `s3-join40-r40`.
Use unchanged extracted ZIP source1deee988a37325c230a389ad4e6dafc518fc138f,
same official image/full patch as the s2 control. Fixed90ms propagation RTT,
100Mbps,q100,200s,Vegas0s,CUBIC40s,seed123456789,initialssthresh900MSS,
MSS1380,unchangedbuffers/loss/startup,noadaptive thresholds. Renewal disabled
for baseline or enabled with20/40 valid cycles and1ms rise threshold.

Primary evaluation uses the common [40,200) active interval: per-flow and
aggregate app goodput, Jain index, measured forward queue delay, drops and
retransmissions. Secondary [80,200) evaluates the later part of this same
run; never substitute it for the predeclared primary window. Record renewal
counts/times and audit rule operation independently. Compare 40 with20 and
each withbaseline. Preserve all three results without retuning; a reversed
queue/sharing ranking weakens the original balanced-candidate recommendation.
Use the same four-metric dominance rule as the original sensitivity study.

Runner options common to all: `--after-ms 45 --competitor
--competitor-start 40 --root /tmp/vegas-competition-timing
--source-manifest /work/SOURCE_MANIFEST.json --image-digest
sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`.
Add `--renewal --rounds 20` or `--renewal --rounds 40` as named.
Analyze each to its own directory with `--window common:40:200
--window late_common:80:200`. Run sequentially and retain manifests/logs.

Status: declared; results pending. In addition to these simulations, inspect
the immediate effect of renewal on the same cycle's inferred excess packets.
This algebraic local comparison is not a counterfactual whole-flow simulation.
