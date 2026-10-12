"""Compose canonical v6 and passive CUBIC HyStart logging on clean official ns-3."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + repr(old[:90]))
    return s.replace(old, new)


METHODS = r'''
void TcpCubic::SetOrbitObservationFlow(uint64_t flowId) {
    const char* enabled = std::getenv("CS30401_HYSTART_TRACE");
    m_orbitObserve = enabled && std::string(enabled) == "1";
    m_orbitFlow = flowId;
}
void TcpCubic::ObserveOrbitHyStart(const char* event, Ptr<const TcpSocketState> tcb,
                                 const Time& input, uint32_t reasons,
                                 uint32_t beforeSs, int64_t ackGap) const {
    if (!m_orbitObserve) return;
    static std::unique_ptr<std::ofstream> out;
    if (!out) {
        const char* directory = std::getenv("CS30401_STUDY_TRACE_DIR");
        NS_ABORT_MSG_IF(!directory, "Missing HyStart trace directory");
        out = std::make_unique<std::ofstream>(std::string(directory) + "/hystart_state.csv");
        NS_ABORT_MSG_IF(!out->good(), "Cannot create HyStart state trace");
        *out << "time_ns,flow_id,event,hystart_enabled,detect_mode,reason_mask,input_rtt_ns,"
                "delay_min_ns,current_rtt_ns,threshold_ns,sample_count,cwnd_bytes,"
                "ssthresh_before_bytes,ssthresh_after_bytes,last_acked_seq,round_end_seq,"
                "round_start_ns,last_ack_ns,ack_gap_before_ns,round_elapsed_ns,"
                "cong_state,cwnd_limited,found,cached_last_rtt_ns,srtt_ns\n";
    }
    auto time = [&](const Time& value) {
        if (value != Time::Min() && value != Time::Max()) *out << value.GetNanoSeconds();
        *out << ',';
    };
    *out << Simulator::Now().GetNanoSeconds() << ',' << m_orbitFlow << ',' << event
         << ',' << m_hystart << ',' << static_cast<int>(m_hystartDetect) << ',' << reasons << ',';
    time(input); time(m_delayMin); time(m_currRtt);
    if (m_delayMin != Time::Min()) *out << HystartDelayThresh(m_delayMin).GetNanoSeconds();
    *out << ',' << static_cast<unsigned>(m_sampleCnt) << ',' << tcb->m_cWnd.Get()
         << ',' << beforeSs << ',' << tcb->m_ssThresh.Get()
         << ',' << tcb->m_lastAckedSeq.GetValue() << ',' << m_endSeq.GetValue() << ',';
    time(m_roundStart); time(m_lastAck);
    *out << ackGap << ',';
    if (m_roundStart != Time::Min()) *out << (Simulator::Now()-m_roundStart).GetNanoSeconds();
    *out << ',' << static_cast<int>(tcb->m_congState) << ',' << tcb->m_isCwndLimited
         << ',' << m_found << ',';
    time(tcb->m_lastRtt.Get());
    if (tcb->m_srtt.Get() != Time::Max()) *out << tcb->m_srtt.Get().GetNanoSeconds();
    *out << '\n';
}
'''


def transform(root):
    out = {}
    rel = 'src/internet/model/tcp-cubic.h'
    s = (root/rel).read_text()
    s = once(s, '    static TypeId GetTypeId();',
        '    static TypeId GetTypeId();\n    void SetOrbitObservationFlow(uint64_t flowId);')
    s = once(s, '  private:\n    bool m_fastConvergence;',
        '  private:\n'
        '    bool m_orbitObserve{false};\n    uint64_t m_orbitFlow{0};\n'
        '    void ObserveOrbitHyStart(const char* event, Ptr<const TcpSocketState> tcb,\n'
        '                             const Time& input, uint32_t reasons,\n'
        '                             uint32_t beforeSs, int64_t ackGap) const;\n'
        '    bool m_fastConvergence;')
    out[rel] = s
    rel = 'src/internet/model/tcp-cubic.cc'
    s = (root/rel).read_text()
    s = once(s, '#include "tcp-cubic.h"',
        '#include "tcp-cubic.h"\n#include <cstdlib>\n#include <fstream>\n#include <memory>')
    s = once(s, '    m_sampleCnt = 0;\n}',
        '    m_sampleCnt = 0;\n'
        '    ObserveOrbitHyStart("ROUND_RESET", tcb, Time::Min(), 0, tcb->m_ssThresh, 0);\n}')
    s = once(s, '    /* Discard delay samples right after fast recovery */',
        '    if (tcb->m_cWnd <= tcb->m_ssThresh)\n'
        '        ObserveOrbitHyStart("ACK", tcb, rtt, 0, tcb->m_ssThresh,\n'
        '            m_lastAck == Time::Min() ? -1 : (Simulator::Now()-m_lastAck).GetNanoSeconds());\n\n'
        '    /* Discard delay samples right after fast recovery */')
    s = once(s, '        Time now = Simulator::Now();\n\n        /* first detection',
        '        Time now = Simulator::Now();\n'
        '        const int64_t ackGap = (now-m_lastAck).GetNanoSeconds();\n'
        '        const uint32_t beforeSs = tcb->m_ssThresh;\n'
        '        uint32_t reasons = 0;\n\n        /* first detection')
    anchor = '                    m_found = true;'
    if s.count(anchor) != 1:
        raise ValueError('ACK-train decision anchor differs')
    s = s.replace(anchor, anchor + '\n                    reasons |= 1;')
    s = once(s, '                m_found = true;\n            }\n        }\n\n        /*',
        '                m_found = true;\n                reasons |= 2;\n            }\n        }\n\n        /*')
    s = once(s, '            tcb->m_ssThresh = tcb->m_cWnd;\n        }\n    }\n}',
        '            tcb->m_ssThresh = tcb->m_cWnd;\n        }\n'
        '        ObserveOrbitHyStart(m_found ? "EXIT" : "HYSTART_SAMPLE", tcb, delay,\n'
        '                            reasons, beforeSs, ackGap);\n    }\n}')
    s = once(s, '} // namespace ns3', METHODS + '\n} // namespace ns3')
    out[rel] = s
    rel = 'scratch/main_satnet/main_satnet.cc'
    s = (root/rel).read_text()
    s = once(s, '    std::string run_dir = "";',
        '    std::string run_dir = "";\n    bool hystart = true;')
    s = once(s, '    cmd.Parse(argc, argv);',
        '    cmd.AddValue("hystart", "CUBIC HyStart switch for the finite-flow diagnostic", hystart);\n'
        '    cmd.Parse(argc, argv);')
    s = once(s, '    // Load basic simulation environment',
        '    // Apply after parsing; the actual sending socket is checked independently.\n'
        '    Config::SetDefault("ns3::TcpCubic::HyStart", BooleanValue(hystart));\n\n'
        '    // Load basic simulation environment')
    s = once(s, '#include "study_drop_trace.h"',
        '#include "study_drop_trace.h"\n#include "orbit_hystart_queue.h"')
    s = once(s, '    cs30401study::Install(topology->GetNodes());',
        '    cs30401study::Install(topology->GetNodes());\n'
        '    orbithystart::Install(topology->GetNodes());')
    out[rel] = s
    out['scratch/main_satnet/orbit_hystart_queue.h'] = (
        Path(__file__).resolve().parent/'queue_observer.h').read_text()
    rel = 'contrib/basic-sim/model/apps/tcp-flow-send-application.cc'
    s = (root/rel).read_text()
    s = once(s, '#include "ns3/tcp-option-sack.h"',
        '#include "ns3/tcp-option-sack.h"\n#include "ns3/tcp-cubic.h"\n#include "ns3/pointer.h"')
    s = once(s, 'void TcpFlowSendApplication::InitializeStudy() {',
        'void TcpFlowSendApplication::InitializeStudy() {\n'
        '    const char* expectedHyStart = std::getenv("CS30401_HYSTART_EXPECTED");\n'
        '    if (expectedHyStart) {\n'
        '        PointerValue congestion;\n'
        '        m_socket->GetAttribute("CongestionOps", congestion);\n'
        '        auto cubic = DynamicCast<TcpCubic>(congestion.Get<TcpCongestionOps>());\n'
        '        NS_ABORT_MSG_IF(!cubic, "HyStart diagnostic requires an actual CUBIC socket");\n'
        '        BooleanValue actual;\n'
        '        cubic->GetAttribute("HyStart", actual);\n'
        '        NS_ABORT_MSG_IF((std::string(expectedHyStart) == "1") != actual.Get(),\n'
        '                        "Actual sending socket HyStart differs from parsed option");\n'
        '        cubic->SetOrbitObservationFlow(m_tcpFlowId);\n'
        '        std::ofstream config(m_baseLogsDir + "/hystart_socket.csv");\n'
        '        config << "flow_id,actual_type,hystart_enabled,segment_size,initial_cwnd,initial_ssthresh\\n";\n'
        '        UintegerValue segment, initialCwnd, initialSs;\n'
        '        m_socket->GetAttribute("SegmentSize", segment);\n'
        '        m_socket->GetAttribute("InitialCwnd", initialCwnd);\n'
        '        m_socket->GetAttribute("InitialSlowStartThreshold", initialSs);\n'
        '        config << m_tcpFlowId << "," << cubic->GetInstanceTypeId().GetName() << ","\n'
        '               << actual.Get() << "," << segment.Get() << "," << initialCwnd.Get()\n'
        '               << "," << initialSs.Get() << "\\n";\n'
        '    }')
    out[rel] = s
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3-root', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--baseline', type=Path, default=Path('/work/code/kim-study/ns3.patch'))
    p.add_argument('--patch', type=Path, required=True)
    a = p.parse_args()
    r = a.ns3_root.resolve()
    if a.patch.exists():
        raise ValueError('Refusing existing exported patch')
    if subprocess.check_output(['git','status','--porcelain'], cwd=r).strip():
        raise ValueError('Expected clean official source')
    subprocess.run(['git','apply','--check',str(a.baseline)], cwd=r, check=True)
    subprocess.run(['git','apply',str(a.baseline)], cwd=r, check=True)
    subprocess.run(['git','add','-N','scratch/main_satnet/study_drop_trace.h',
                    'scratch/study_micro/study_micro.cc'], cwd=r, check=True)
    baseline = subprocess.check_output(['git','diff','--binary'], cwd=r)
    if baseline != a.baseline.read_bytes():
        raise ValueError('Installed canonical v6 differs from its artifact')
    outputs = transform(r)
    for rel, content in outputs.items():
        (r/rel).write_text(content, newline='\n')
    subprocess.run(['git','add','-N','scratch/main_satnet/orbit_hystart_queue.h'], cwd=r, check=True)
    subprocess.run(['git','diff','--check'], cwd=r, check=True)
    a.patch.parent.mkdir(parents=True, exist_ok=True)
    a.patch.write_bytes(subprocess.check_output(['git','diff','--binary'], cwd=r))
    subprocess.run(['git','apply','--reverse','--check',str(a.patch)], cwd=r, check=True)
    print(json.dumps({'patch_sha256':sha(a.patch),'baseline_sha256':sha(a.baseline),
                      'helper_sha256':sha(Path(__file__)),
                      'changed_sources':{rel:sha(r/rel) for rel in outputs}}, indent=2))


if __name__ == '__main__':
    main()
