"""Compose an opt-in, ProbeBW-only orbit BDP target with the passive observer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

METHODS = r'''
void
TcpBbr::ConfigureOrbitBdp(bool enabled, const std::string& path)
{
    m_orbitEnabled = enabled;
    std::ifstream input(path);
    NS_ABORT_MSG_IF(!input.good(), "Cannot open declared orbit geometry");
    std::string line;
    std::getline(input, line);
    NS_ABORT_MSG_IF(line != "time_ns,prop_rtt_ns", "Unexpected orbit CSV header");
    while (std::getline(input, line))
    {
        std::istringstream fields(line);
        std::string a, b, extra;
        NS_ABORT_MSG_IF(!std::getline(fields,a,',') || !std::getline(fields,b,',') ||
                        std::getline(fields,extra,','), "Invalid orbit geometry row");
        const int64_t t = std::stoll(a), rtt = std::stoll(b);
        NS_ABORT_MSG_IF(t < 0 || rtt <= 0 ||
                        (!m_orbitRows.empty() && t <= m_orbitRows.back().first),
                        "Invalid orbit geometry ordering/value");
        m_orbitRows.emplace_back(t,rtt);
    }
    NS_ABORT_MSG_IF(m_orbitRows.empty() || m_orbitRows.front().first != 0,
                    "Orbit geometry must start at zero");
}

int64_t
TcpBbr::OrbitRttAt(int64_t t) const
{
    NS_ABORT_MSG_IF(m_orbitRows.empty() || t < 0 || t > m_orbitRows.back().first,
                    "Orbit lookup outside declared geometry");
    auto it = std::upper_bound(m_orbitRows.begin(), m_orbitRows.end(), t,
        [](int64_t value, const std::pair<int64_t,int64_t>& row) {
            return value < row.first;
        });
    return std::prev(it)->second;
}

void
TcpBbr::ApplyOrbitTarget(Ptr<TcpSocketState> tcb)
{
    if (m_orbitRows.empty()) return;
    const int64_t now = Simulator::Now().GetNanoSeconds();
    const int64_t current = OrbitRttAt(now);
    const int64_t lookup = now + current;
    const int64_t future = OrbitRttAt(lookup);
    const uint32_t original = m_targetCWnd;
    const bool active = m_orbitEnabled && m_isPipeFilled &&
                        m_state == BbrMode_t::BBR_PROBE_BW;
    if (active)
    {
        const double bdp = m_maxBwFilter.GetBest() * NanoSeconds(future) / 8.0;
        double target = m_cWndGain.Get() * bdp + 3 * m_sendQuantum;
        if (m_cycleIndex == 0) target += 2 * tcb->m_segmentSize;
        NS_ABORT_MSG_IF(target < 0 || target > std::numeric_limits<uint32_t>::max(),
                        "Orbit target outside cwnd integer range");
        m_targetCWnd = static_cast<uint32_t>(target) + AckAggregationCwnd();
    }
    const int64_t bucket = now / 100000000;
    if (bucket == m_orbitLastBucket && active == m_orbitLastActive) return;
    static std::unique_ptr<std::ofstream> out;
    if (!out)
    {
        const char* directory = std::getenv("CS30401_BBR_OBSERVE_DIR");
        NS_ABORT_MSG_IF(!directory, "Missing orbit trace directory");
        out = std::make_unique<std::ofstream>(std::string(directory)+"/orbit_bdp_state.csv");
        NS_ABORT_MSG_IF(!out->good(), "Cannot open orbit trace");
        *out << "time_ns,flow_id,enabled,active,bbr_state,min_rtt_ns,geo_now_ns,geo_future_ns,lookup_time_ns,max_bw_bps,cwnd_gain,original_target_bytes,actual_target_bytes,cwnd_before_bytes,inflight_bytes\n";
        out->precision(17);
    }
    *out << now << ',' << m_observeFlow << ',' << m_orbitEnabled << ',' << active
         << ',' << static_cast<int>(m_state) << ',' << m_minRtt.Get().GetNanoSeconds()
         << ',' << current << ',' << future << ',' << lookup << ','
         << m_maxBwFilter.GetBest().GetBitRate() << ',' << m_cWndGain.Get()
         << ',' << original << ',' << m_targetCWnd << ',' << tcb->m_cWnd.Get()
         << ',' << tcb->m_bytesInFlight.Get() << '\n';
    m_orbitLastBucket = bucket;
    m_orbitLastActive = active;
}
'''

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def replace(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Source anchor missing/ambiguous: '+old[:90])
    return s.replace(old,new)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--patch',type=Path,required=True)
    a=p.parse_args()
    if a.patch.exists(): raise ValueError('Refusing patch overwrite')
    def git(*args): return subprocess.check_output(['git','-c','core.autocrlf=false',*args],cwd=a.root)
    observer=Path('/work/code/bbr-route/ns3-observe.patch')
    if git('diff','--binary','HEAD').strip()!=observer.read_bytes().strip():
        raise ValueError('Expected exact passive observer source diff')
    cc=a.root/'src/internet/model/tcp-bbr.cc'
    h=a.root/'src/internet/model/tcp-bbr.h'
    app=a.root/'contrib/basic-sim/model/apps/tcp-flow-send-application.cc'
    s=cc.read_text()
    s=replace(s,'#include "tcp-bbr.h"','#include "tcp-bbr.h"\n#include <limits>\n#include <sstream>\n#include <algorithm>')
    s=replace(s,'    m_targetCWnd = InFlight(tcb, m_cWndGain) + AckAggregationCwnd();',
              '    m_targetCWnd = InFlight(tcb, m_cWndGain) + AckAggregationCwnd();\n    ApplyOrbitTarget(tcb);')
    s=replace(s,'      m_hasSeenRtt(sock.m_hasSeenRtt)',
              '      m_hasSeenRtt(sock.m_hasSeenRtt),\n      m_orbitEnabled(sock.m_orbitEnabled),\n      m_orbitRows(sock.m_orbitRows)')
    s += '\nnamespace ns3\n{\n'+METHODS+'\n} // namespace ns3\n'
    hs=h.read_text()
    hs=replace(hs,'#include "tcp-congestion-ops.h"','#include "tcp-congestion-ops.h"\n#include <string>\n#include <vector>\n#include <utility>')
    hs=replace(hs,'    void SetObservationFlow(uint64_t flowId);',
               '    void SetObservationFlow(uint64_t flowId);\n    void ConfigureOrbitBdp(bool enabled, const std::string& path);')
    hs=replace(hs,'    bool m_observeEnabled{false};',
               '    int64_t OrbitRttAt(int64_t t) const;\n    void ApplyOrbitTarget(Ptr<TcpSocketState> tcb);\n'
               '    bool m_orbitEnabled{false};\n    std::vector<std::pair<int64_t,int64_t>> m_orbitRows;\n'
               '    int64_t m_orbitLastBucket{-1};\n    bool m_orbitLastActive{false};\n    bool m_observeEnabled{false};')
    aps=app.read_text()
    aps=replace(aps,'        bbr->SetObservationFlow(m_tcpFlowId);',
                '    {\n        bbr->SetObservationFlow(m_tcpFlowId);\n'
                '        if (const char* csv = std::getenv("CS30401_ORBIT_BDP_CSV")) {\n'
                '            const char* flag = std::getenv("CS30401_ORBIT_BDP");\n'
                '            NS_ABORT_MSG_IF(!flag || (std::string(flag)!="0" && std::string(flag)!="1"), "Invalid orbit flag");\n'
                '            bbr->ConfigureOrbitBdp(std::string(flag)=="1", csv);\n        }\n    }')
    for path,value in [(cc,s),(h,hs),(app,aps)]: path.write_text(value,newline='\n')
    subprocess.run(['git','diff','--check'],cwd=a.root,check=True)
    a.patch.parent.mkdir(parents=True,exist_ok=True)
    a.patch.write_bytes(git('diff','--binary','HEAD'))
    subprocess.run(['git','apply','--reverse','--check',str(a.patch)],cwd=a.root,check=True)
    print(json.dumps({'patch_sha256':sha(a.patch),'observer_patch_sha256':sha(observer),
                      'installer_sha256':sha(__file__),'source_head':git('rev-parse','HEAD').decode().strip()}))

if __name__=='__main__': main()
