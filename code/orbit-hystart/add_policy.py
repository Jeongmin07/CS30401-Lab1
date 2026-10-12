"""Add the predeclared ACK-train-only forecast control to the observed study tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def once(s,old,new):
    if s.count(old)!=1: raise ValueError('Expected one source anchor: '+repr(old[:100]))
    return s.replace(old,new)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3-root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--observed-patch',type=Path,default=Path('/work/code/orbit-hystart/observed.patch'))
    p.add_argument('--patch',type=Path,required=True)
    a=p.parse_args(); root=a.ns3_root
    if a.patch.exists(): raise ValueError('Refusing existing patch artifact')
    if subprocess.check_output(['git','diff','--binary'],cwd=root)!=a.observed_patch.read_bytes():
        raise ValueError('Expected the exact pre-policy observed study source')
    out={}
    rel='src/internet/model/tcp-cubic.h'; s=(root/rel).read_text()
    s=once(s,'#include "tcp-socket-base.h"','#include "tcp-socket-base.h"\n#include <vector>')
    s=once(s,'    uint64_t m_orbitFlow{0};',
        '    uint64_t m_orbitFlow{0};\n'
        '    std::string m_orbitForecastWindows;\n'
        '    std::vector<std::pair<int64_t,int64_t>> m_orbitForecastIntervals;\n'
        '    bool OrbitForecastActive() const;')
    out[rel]=s
    rel='src/internet/model/tcp-cubic.cc'; s=(root/rel).read_text()
    s=once(s,'#include <memory>','#include <memory>\n#include <sstream>\n#include "ns3/string.h"')
    s=once(s,'            .AddAttribute("CubicDelta",',
        '            .AddAttribute("OrbitForecastWindows",\n'
        '                          "Optional oracle intervals for ACK-train-only exit deferral",\n'
        '                          StringValue(""),\n'
        '                          MakeStringAccessor(&TcpCubic::m_orbitForecastWindows),\n'
        '                          MakeStringChecker())\n'
        '            .AddAttribute("CubicDelta",')
    s=once(s,'      m_fastConvergence(sock.m_fastConvergence),',
        '      m_orbitForecastWindows(sock.m_orbitForecastWindows),\n'
        '      m_fastConvergence(sock.m_fastConvergence),')
    s=once(s,'    m_orbitFlow = flowId;\n}',
        '    m_orbitFlow = flowId;\n'
        '    m_orbitForecastIntervals.clear();\n'
        '    std::stringstream input(m_orbitForecastWindows);\n'
        '    std::string interval;\n'
        '    while (std::getline(input, interval, \'|\')) {\n'
        '        auto colon = interval.find(\':\');\n'
        '        NS_ABORT_MSG_IF(colon == std::string::npos, "Invalid forecast interval");\n'
        '        int64_t start = std::stoll(interval.substr(0,colon));\n'
        '        int64_t end = std::stoll(interval.substr(colon+1));\n'
        '        NS_ABORT_MSG_IF(start < 0 || start >= end ||\n'
        '            (!m_orbitForecastIntervals.empty() &&\n'
        '             start < m_orbitForecastIntervals.back().second), "Invalid forecast bounds");\n'
        '        m_orbitForecastIntervals.emplace_back(start,end);\n'
        '    }\n'
        '}\n'
        'bool TcpCubic::OrbitForecastActive() const {\n'
        '    const int64_t now = Simulator::Now().GetNanoSeconds();\n'
        '    for (const auto& interval : m_orbitForecastIntervals)\n'
        '        if (interval.first <= now && now < interval.second) return true;\n'
        '    return false;\n'
        '}')
    s=once(s,'        /*\n         * Either one of two conditions are met,',
        '        // Defer only a train-only decision inside the predeclared oracle window.\n'
        '        // A simultaneous DELAY decision and all decisions outside remain stock.\n'
        '        if (m_found && reasons == 1 && OrbitForecastActive()) {\n'
        '            m_found = false;\n'
        '            ObserveOrbitHyStart("FORECAST_DEFER", tcb, delay, reasons, beforeSs, ackGap);\n'
        '        }\n\n'
        '        /*\n         * Either one of two conditions are met,')
    s=once(s,'cached_last_rtt_ns,srtt_ns\\n','cached_last_rtt_ns,srtt_ns,forecast_active\\n')
    s=once(s,"    *out << '\\n';\n}\n", "    *out << ',' << OrbitForecastActive() << '\\n';\n}\n")
    out[rel]=s
    rel='scratch/main_satnet/main_satnet.cc'; s=(root/rel).read_text()
    s=once(s,'    bool hystart = true;',
        '    bool hystart = true;\n    std::string hystart_forecast_windows;')
    s=once(s,'    cmd.Parse(argc, argv);',
        '    cmd.AddValue("hystart_forecast_windows", "Optional oracle start:end intervals (ns)",\n'
        '                 hystart_forecast_windows);\n    cmd.Parse(argc, argv);')
    s=once(s,'    Config::SetDefault("ns3::TcpCubic::HyStart", BooleanValue(hystart));',
        '    Config::SetDefault("ns3::TcpCubic::HyStart", BooleanValue(hystart));\n'
        '    Config::SetDefault("ns3::TcpCubic::OrbitForecastWindows", StringValue(hystart_forecast_windows));')
    out[rel]=s
    rel='contrib/basic-sim/model/apps/tcp-flow-send-application.cc'; s=(root/rel).read_text()
    s=once(s,'        cubic->SetOrbitObservationFlow(m_tcpFlowId);',
        '        StringValue windows;\n'
        '        cubic->GetAttribute("OrbitForecastWindows", windows);\n'
        '        const char* expectedWindows = std::getenv("CS30401_HYSTART_FORECAST_EXPECTED");\n'
        '        NS_ABORT_MSG_IF(expectedWindows && windows.Get() != expectedWindows,\n'
        '                        "Actual CUBIC forecast intervals differ from parsed option");\n'
        '        cubic->SetOrbitObservationFlow(m_tcpFlowId);')
    s=once(s,'initial_cwnd,initial_ssthresh\\n','initial_cwnd,initial_ssthresh,forecast_windows_ns\\n')
    s=once(s,'               << "," << initialSs.Get() << "\\n";',
        '               << "," << initialSs.Get() << "," << windows.Get() << "\\n";')
    out[rel]=s
    for rel,text in out.items(): (root/rel).write_text(text,newline='\n')
    subprocess.run(['git','diff','--check'],cwd=root,check=True)
    a.patch.write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=root))
    subprocess.run(['git','apply','--reverse','--check',str(a.patch)],cwd=root,check=True)
    print(json.dumps({'patch_sha256':hashlib.sha256(a.patch.read_bytes()).hexdigest(),
                      'previous_patch_sha256':hashlib.sha256(a.observed_patch.read_bytes()).hexdigest(),
                      'changed_sources':list(out)},indent=2))


if __name__=='__main__': main()
