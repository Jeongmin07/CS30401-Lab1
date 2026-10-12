#!/usr/bin/env python3
"""Repair the V1 semantic freshness gate; export a distinct full official patch."""
import argparse
from pathlib import Path
import subprocess


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + old[:80])
    return text.replace(old, new)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--patch', type=Path, required=True)
    a = p.parse_args()
    if a.patch.exists():
        raise ValueError('Refusing to overwrite V2 patch')
    existing = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=a.ns3)
    if existing != Path(__file__).with_name('ns3.patch').read_bytes():
        raise ValueError('Installed source does not match preserved V1 patch')
    cc, h = [a.ns3 / ('src/internet/model/tcp-bbr.' + ext) for ext in ('cc', 'h')]
    text = cc.read_text()
    text = replace(text, 'if (m_minRttStamp >= hint.first)', 'if (m_orbitLastProbeCompleteNs >= hint.first.GetNanoSeconds())')
    text = replace(text, 'OrbitLog("HINT_FRESH_SKIP", tcb);', 'OrbitLog("HINT_PROBE_COMPLETE_SKIP", tcb);')
    text = replace(text, 'm_state != BbrMode_t::BBR_PROBE_BW || tcb->m_congState != TcpSocketState::CA_OPEN ||', 'm_state != BbrMode_t::BBR_PROBE_BW ||')
    text = replace(text, '            OrbitLog("PROBE_COMPLETE", tcb);', '            m_orbitLastProbeCompleteNs = Simulator::Now().GetNanoSeconds();\n            OrbitLog("PROBE_COMPLETE", tcb);')
    text = replace(text, '"min_rtt_filter_ns,probe_duration_ns,round_count\\n";', '"min_rtt_filter_ns,probe_duration_ns,round_count,last_probe_complete_ns,cong_state\\n";')
    text = replace(text, "         << ',' << m_roundCount << '\\n';", "         << ',' << m_roundCount << ',' << m_orbitLastProbeCompleteNs\n         << ',' << static_cast<int>(tcb->m_congState) << '\\n';")
    header = replace(h.read_text(), '    size_t m_orbitNext{0};', '    size_t m_orbitNext{0};\n    int64_t m_orbitLastProbeCompleteNs{-1};')
    cc.write_text(text)
    h.write_text(header)
    a.patch.write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=a.ns3))
    print(a.patch)


if __name__ == '__main__':
    main()
