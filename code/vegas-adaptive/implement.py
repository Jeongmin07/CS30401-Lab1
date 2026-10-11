"""Apply the declared CA-only adaptation to the pinned PR14 source, once."""
from pathlib import Path
import hashlib

ROOT = Path('/home/ubuntu/ns-3.48')
def replace(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old))
    return s.replace(old, new)

p = ROOT / 'src/internet/model/tcp-vegas.h'
s = p.read_text()
s = replace(s, '    bool m_recentMinRenewal{false};', '''    void AdaptiveDecision(Ptr<TcpSocketState> tcb, uint32_t diff);
    bool m_adaptiveThresholds{false};
    bool m_previousRateValid{false};
    bool m_adaptiveFloorSet{false};
    double m_previousRate{0};
    uint32_t m_alphaFloor{2}, m_betaFloor{4};
    bool m_recentMinRenewal{false};''')
p.write_text(s)
p = ROOT / 'src/internet/model/tcp-vegas.cc'
s = p.read_text()
s = replace(s, '                            .AddAttribute("RecentMinRenewal",', '''                            .AddAttribute("AdaptiveThresholds",
                                          "Vegas-A-inspired CA threshold adaptation",
                                          BooleanValue(false),
                                          MakeBooleanAccessor(&TcpVegas::m_adaptiveThresholds),
                                          MakeBooleanChecker())
                            .AddAttribute("RecentMinRenewal",''')
s = replace(s, '      m_recentMinRenewal(sock.m_recentMinRenewal),', '''      m_adaptiveThresholds(sock.m_adaptiveThresholds),
      m_recentMinRenewal(sock.m_recentMinRenewal),''')
s = replace(s, '    m_doingVegasNow = false;', '    m_doingVegasNow = false;\n    m_previousRateValid = false;')
s = replace(s, '    m_begSndNxt = tcb->m_nextTxSequence;\n    m_cntRtt = 0;', '    m_begSndNxt = tcb->m_nextTxSequence;\n    m_previousRateValid = false;\n    m_cntRtt = 0;')
s = replace(s, '        if (m_recentMinRenewal && validRenewalCycle)', '''        NS_ABORT_MSG_IF(m_adaptiveThresholds && m_recentMinRenewal,
                        "Study policies must be evaluated separately");
        if (!validRenewalCycle) m_previousRateValid = false;
        if (m_recentMinRenewal && validRenewalCycle)''')
s = replace(s, '                if (diff > m_beta)\n                {', '''                if (m_adaptiveThresholds && validRenewalCycle)
                {
                    AdaptiveDecision(tcb, diff);
                }
                else if (diff > m_beta)
                {''')
method = '''
void
TcpVegas::AdaptiveDecision(Ptr<TcpSocketState> tcb, uint32_t diff)
{
    // Endpoint estimate, not receiver goodput. Inputs are unchanged course SRTT.
    const uint32_t before = tcb->m_cWnd.Get();
    uint32_t window = tcb->GetCwndInSegments();
    const double rate = window / m_minRtt.GetSeconds();
    if (!m_adaptiveFloorSet)
    {
        m_alphaFloor = m_alpha;
        m_betaFloor = m_beta;
        m_adaptiveFloorSet = true;
    }
    const uint32_t alphaBefore = m_alpha, betaBefore = m_beta;
    const bool hadPrevious = m_previousRateValid;
    const double previous = m_previousRate;
    const char* rule = "band-hold";
    int change = 0;
    if (!hadPrevious)
    {
        // No cross-startup/recovery comparison: ordinary Vegas seeds history.
        rule = "seed-ordinary";
        change = diff > m_beta ? -1 : (diff < m_alpha ? 1 : 0);
    }
    else if (diff > m_beta)
    {
        rule = "above-beta";
        change = -1;
        if (m_alpha > m_alphaFloor) --m_alpha;
        if (m_beta > m_betaFloor) --m_beta;
    }
    else if (diff < m_alpha)
    {
        if (m_alpha > m_alphaFloor && rate < previous)
        {
            rule = "below-alpha-rate-fell";
            change = -1;
            --m_alpha;
            if (m_beta > m_betaFloor) --m_beta;
        }
        else if (m_alpha == m_alphaFloor || rate > previous)
        {
            rule = "below-alpha-grow";
            change = 1;
        }
        else rule = "below-alpha-equal-hold";
    }
    else if (rate > previous)
    {
        rule = "band-rate-rose";
        change = 1;
        NS_ABORT_MSG_IF(m_alpha == UINT32_MAX || m_beta == UINT32_MAX,
                        "Adaptive threshold overflow");
        ++m_alpha;
        ++m_beta;
    }
    if (change < 0)
    {
        window = std::max(2u, window - 1);
        tcb->m_cWnd = window * tcb->m_segmentSize;
        tcb->m_ssThresh = GetSsThresh(tcb, 0);
    }
    else if (change > 0)
    {
        tcb->m_cWnd = (window + 1) * tcb->m_segmentSize;
    }
    const char* directory = std::getenv("CS30401_VEGAS_TRACE_DIR");
    if (directory && directory[0])
    {
        static std::unique_ptr<std::ofstream> out;
        if (!out)
        {
            out = std::make_unique<std::ofstream>(std::string(directory) + "/adaptive_state.csv");
            NS_ABORT_MSG_IF(!out->good(), "Cannot open adaptive trace");
            *out << "time_ns,vegas_instance,rule,diff_pkts,rate_pkts_s,previous_rate_pkts_s,previous_valid,alpha_before,beta_before,alpha_after,beta_after,cwnd_before_bytes,cwnd_after_bytes,segment_size,cycle_min_rtt_ns,base_rtt_ns,alpha_floor,beta_floor,cong_state\\n";
            out->precision(17);
        }
        *out << Simulator::Now().GetNanoSeconds() << ',' << m_traceInstance << ',' << rule << ','
             << diff << ',' << rate << ',' << previous << ',' << hadPrevious << ','
             << alphaBefore << ',' << betaBefore << ',' << m_alpha << ',' << m_beta << ','
             << before << ',' << tcb->m_cWnd.Get() << ',' << tcb->m_segmentSize << ','
             << m_minRtt.GetNanoSeconds() << ',' << m_baseRtt.GetNanoSeconds() << ','
             << m_alphaFloor << ',' << m_betaFloor << ',' << static_cast<int>(tcb->m_congState)
             << '\\n';
    }
    m_previousRate = rate;
    m_previousRateValid = true;
}

'''
s = replace(s, '\nvoid\nTcpVegas::TraceStudy', '\n' + method + 'void\nTcpVegas::TraceStudy')
p.write_text(s)
print('Applied CA-only adaptation; export/stage and build before launch')
