#!/usr/bin/env python3
"""Add one opt-in timing policy to the exact passive BBR observer tree."""
import argparse
import json
from pathlib import Path
import subprocess


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + old[:90])
    return text.replace(old, new)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--patch', type=Path, required=True)
    a = p.parse_args()
    if a.patch.exists():
        raise ValueError('Refusing to overwrite exported patch')
    subprocess.run(['git', 'apply', '--reverse', '--check', '/work/code/bbr-route/ns3-observe.patch'], cwd=a.ns3, check=True)
    cc, h = [a.ns3 / ('src/internet/model/tcp-bbr.' + ext) for ext in ('cc', 'h')]
    text = cc.read_text()
    text = replace(text, '#include <memory>', '#include <memory>\n#include <sstream>\n#include "ns3/boolean.h"')
    text = replace(text, '.AddAttribute("Stream",', '''.AddAttribute("OrbitProbe",
                          "Expire an old-path RTT filter after an operator route-change hint",
                          BooleanValue(false),
                          MakeBooleanAccessor(&TcpBbr::m_orbitEnabled),
                          MakeBooleanChecker())
            .AddAttribute("Stream",''')
    text = replace(text, ': TcpCongestionOps(sock),', ': TcpCongestionOps(sock),\n      m_orbitEnabled(sock.m_orbitEnabled),')
    text = replace(text, '    UpdateRTprop(tcb);\n    CheckProbeRTT(tcb, rs);', '    ConsiderOrbitProbe(tcb);\n    UpdateRTprop(tcb);\n    CheckProbeRTT(tcb, rs);')
    text = replace(text, '        m_probeRttDoneStamp = Seconds(0);\n    }', '        m_probeRttDoneStamp = Seconds(0);\n        OrbitLog("PROBE_ENTER", tcb);\n    }')
    text = replace(text, '        m_nextRoundDelivered = m_delivered;\n    }\n    else if (!m_probeRttDoneStamp.IsZero())', '        m_nextRoundDelivered = m_delivered;\n        OrbitLog("PROBE_DRAINED", tcb);\n    }\n    else if (!m_probeRttDoneStamp.IsZero())')
    text = replace(text, '            m_minRttStamp = Simulator::Now();\n            RestoreCwnd(tcb);\n            ExitProbeRTT();', '            m_minRttStamp = Simulator::Now();\n            OrbitLog("PROBE_COMPLETE", tcb);\n            RestoreCwnd(tcb);\n            ExitProbeRTT();')
    # Above anchor occurs once in HandleProbeRTT; CwndEvent has deeper indentation.
    text = replace(text, '''        m_minRtt = tcb->m_lastRtt;
        m_minRttStamp = Simulator::Now();''', '''        const Time old = m_minRtt.Get();
        m_minRtt = tcb->m_lastRtt;
        m_minRttStamp = Simulator::Now();
        if (old != m_minRtt.Get() || m_state == BbrMode_t::BBR_PROBE_RTT)
            OrbitLog("RTPROP_SAMPLE", tcb);''')
    methods = r'''
void
TcpBbr::ConsiderOrbitProbe(Ptr<TcpSocketState> tcb)
{
    if (!m_orbitEnabled) return;
    if (!m_orbitLoaded)
    {
        const char* path = std::getenv("CS30401_ORBIT_FORECAST");
        NS_ABORT_MSG_IF(!path, "OrbitProbe requires CS30401_ORBIT_FORECAST");
        std::ifstream in(path);
        NS_ABORT_MSG_IF(!in.good(), "Cannot open orbit forecast");
        int64_t event, ready;
        while (in >> event >> ready)
        {
            NS_ABORT_MSG_IF(event < 0 || ready < event ||
                (!m_orbitHints.empty() && event <= m_orbitHints.back().first.GetNanoSeconds()),
                "Invalid ordered orbit forecast");
            m_orbitHints.emplace_back(NanoSeconds(event), NanoSeconds(ready));
        }
        NS_ABORT_MSG_IF(!in.eof(), "Malformed orbit forecast");
        m_orbitLoaded = true;
    }
    if (m_orbitNext >= m_orbitHints.size() || Simulator::Now() < m_orbitHints[m_orbitNext].second)
        return;
    const auto hint = m_orbitHints[m_orbitNext++];
    m_orbitEventNs = hint.first.GetNanoSeconds();
    m_orbitReadyNs = hint.second.GetNanoSeconds();
    m_orbitOldStampNs = m_minRttStamp.GetNanoSeconds();
    if (m_minRttStamp >= hint.first)
    {
        OrbitLog("HINT_FRESH_SKIP", tcb);
        return;
    }
    if (m_state != BbrMode_t::BBR_PROBE_BW || tcb->m_congState != TcpSocketState::CA_OPEN ||
        m_idleRestart || !tcb->m_lastRtt.Get().IsPositive() || tcb->m_lastRtt.Get() == Time::Max())
    {
        OrbitLog("HINT_STATE_SKIP", tcb);
        return;
    }
    // Path identity invalidates the old window; do not install geometry as RTT.
    // UpdateRTprop accepts an actual RTT sample, then the original CheckProbeRTT
    // and HandleProbeRTT retain their low-inflight duration and round safeguards.
    m_minRttStamp = Simulator::Now() - m_minRttFilterLen - NanoSeconds(1);
    OrbitLog("HINT_INVALIDATE", tcb);
}

void
TcpBbr::OrbitLog(const char* event, Ptr<const TcpSocketState> tcb)
{
    if (!m_observeEnabled) return;
    static std::unique_ptr<std::ofstream> out;
    if (!out)
    {
        const char* directory = std::getenv("CS30401_BBR_OBSERVE_DIR");
        NS_ABORT_MSG_IF(!directory, "Orbit trace requires observer directory");
        out = std::make_unique<std::ofstream>(std::string(directory) + "/orbit_probe.csv");
        NS_ABORT_MSG_IF(!out->good(), "Cannot open orbit trace");
        *out << "time_ns,flow_id,event,policy_enabled,hint_event_ns,hint_ready_ns,old_stamp_ns,"
                "rtprop_ns,last_rtt_ns,srtt_ns,bbr_state,cwnd_bytes,inflight_bytes,min_pipe_cwnd_bytes,"
                "min_rtt_stamp_ns,min_rtt_expired,probe_done_ns,round_start,probe_round_done,"
                "min_rtt_filter_ns,probe_duration_ns,round_count\n";
    }
    *out << Simulator::Now().GetNanoSeconds() << ',' << m_observeFlow << ',' << event
         << ',' << m_orbitEnabled << ',' << m_orbitEventNs << ',' << m_orbitReadyNs << ',' << m_orbitOldStampNs << ',';
    if (m_minRtt.Get() != Time::Max()) *out << m_minRtt.Get().GetNanoSeconds();
    *out << ',';
    if (tcb->m_lastRtt.Get() != Time::Max()) *out << tcb->m_lastRtt.Get().GetNanoSeconds();
    *out << ',';
    if (tcb->m_srtt.Get() != Time::Max()) *out << tcb->m_srtt.Get().GetNanoSeconds();
    *out << ',' << static_cast<int>(m_state) << ',' << tcb->m_cWnd.Get()
         << ',' << tcb->m_bytesInFlight.Get() << ',' << m_minPipeCwnd
         << ',' << m_minRttStamp.GetNanoSeconds() << ',' << m_minRttExpired
         << ',' << m_probeRttDoneStamp.GetNanoSeconds() << ',' << m_roundStart << ',' << m_probeRttRoundDone
         << ',' << m_minRttFilterLen.GetNanoSeconds() << ',' << m_probeRttDuration.GetNanoSeconds()
         << ',' << m_roundCount << '\n';
}
'''
    text = replace(text, '\n} // namespace ns3', '\n' + methods + '\n} // namespace ns3')
    header = h.read_text()
    header = replace(header, '#include "windowed-filter.h"', '#include "windowed-filter.h"\n#include <vector>\n#include <utility>')
    header = replace(header, '  private:\n    void ObserveAck', '''  private:
    void ConsiderOrbitProbe(Ptr<TcpSocketState> tcb);
    void OrbitLog(const char* event, Ptr<const TcpSocketState> tcb);
    bool m_orbitEnabled{false}, m_orbitLoaded{false};
    std::vector<std::pair<Time, Time>> m_orbitHints;
    size_t m_orbitNext{0};
    int64_t m_orbitEventNs{-1}, m_orbitReadyNs{-1}, m_orbitOldStampNs{-1};
    void ObserveAck''')
    cc.write_text(text)
    h.write_text(header)
    patch = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=a.ns3)
    a.patch.parent.mkdir(parents=True, exist_ok=True)
    a.patch.write_bytes(patch)
    print(json.dumps({'patch': str(a.patch), 'bytes': len(patch)}))


if __name__ == '__main__':
    main()
