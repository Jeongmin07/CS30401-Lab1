"""Compose canonical v6 tracing with opt-in new-data hold. No simulation."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

APP='contrib/basic-sim/model/apps/tcp-flow-send-application'
SOCKET='src/internet/model/tcp-socket-base'


def replace(text,old,new):
    if text.count(old)!=1:
        raise ValueError('Expected one source anchor: '+repr(old[:80]))
    return text.replace(old,new)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--patch',type=Path,required=True)
    a=p.parse_args(); r=a.root
    if a.patch.exists(): raise ValueError('Refusing existing patch')
    baseline=Path('/work/code/kim-study/ns3.patch').read_bytes()
    paths=[p.decode() for p in re.findall(rb'^diff --git a/[^\n]+ b/([^\n]+)$',baseline,re.M)]
    for path in paths:
        if subprocess.run(['git','ls-files','--error-unmatch',path],cwd=r,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            subprocess.run(['git','add','-N','--',path],cwd=r,check=True)
    if subprocess.check_output(['git','diff','--binary','HEAD'],cwd=r)!=baseline:
        raise ValueError('Expected byte-exact canonical v6 source')
    changed={}
    text=(r/(APP+'.cc')).read_text()
    text=replace(text,'key != "study_restore_limit_ns" && key != "study_short_flow_cutoff_pkts")',
                 'key != "study_restore_limit_ns" && key != "study_short_flow_cutoff_pkts" &&\n'
                 '                key != "orbit_hold_windows")')
    text=replace(text,'            } else if (key == "study_restore_limit_ns") {',
        '            } else if (key == "orbit_hold_windows") {\n'
        '                for (const std::string& interval : split_string(value, "|")) {\n'
        '                    auto bounds = split_string(interval, ":", 2);\n'
        '                    int64_t start = parse_positive_int64(trim(bounds[0]));\n'
        '                    int64_t end = parse_positive_int64(trim(bounds[1]));\n'
        '                    NS_ABORT_MSG_IF(start >= end || (!m_orbitHoldWindows.empty() &&\n'
        '                        start < m_orbitHoldWindows.back().second), "Invalid hold windows");\n'
        '                    m_orbitHoldWindows.emplace_back(start, end);\n'
        '                }\n'
        '            } else if (key == "study_restore_limit_ns") {')
    text=replace(text,'    for (const auto& interval : m_studyWindows) {',
        '    for (const auto& interval : m_orbitHoldWindows) {\n'
        '        if (interval.second <= now) continue;\n'
        '        if (interval.first <= now) BeginOrbitHold(interval.second);\n'
        '        else m_studyWindowEvents.push_back(Simulator::Schedule(\n'
        '            NanoSeconds(interval.first - now),\n'
        '            &TcpFlowSendApplication::BeginOrbitHold, this, interval.second));\n'
        '        m_studyWindowEvents.push_back(Simulator::Schedule(\n'
        '            NanoSeconds(interval.second - now),\n'
        '            &TcpFlowSendApplication::EndOrbitHold, this));\n'
        '    }\n'
        '    for (const auto& interval : m_studyWindows) {')
    text=replace(text,'void TcpFlowSendApplication::SetStudyThreshold(uint32_t threshold, const std::string& event) {',
        'void TcpFlowSendApplication::BeginOrbitHold(int64_t endNs) {\n'
        '    if (!m_socket) return;\n'
        '    m_socket->GetObject<TcpSocketBase>()->HoldNewDataUntil(NanoSeconds(endNs));\n'
        '    InsertStudyEvent("NEW_DATA_HOLD_BEGIN", 0, endNs);\n'
        '}\n\n'
        'void TcpFlowSendApplication::EndOrbitHold() {\n'
        '    if (!m_socket) return;\n'
        '    InsertStudyEvent("NEW_DATA_HOLD_END", 0, 0);\n'
        '}\n\n'
        'void TcpFlowSendApplication::SetStudyThreshold(uint32_t threshold, const std::string& event) {')
    changed[APP+'.cc']=text
    text=(r/(APP+'.h')).read_text()
    text=replace(text,'  void InitializeStudy();',
                 '  void InitializeStudy();\n  void BeginOrbitHold(int64_t endNs);\n  void EndOrbitHold();')
    text=replace(text,'  std::vector<std::pair<int64_t, int64_t>> m_studyWindows;',
                 '  std::vector<std::pair<int64_t, int64_t>> m_studyWindows;\n'
                 '  std::vector<std::pair<int64_t, int64_t>> m_orbitHoldWindows;')
    changed[APP+'.h']=text
    text=(r/(SOCKET+'.h')).read_text()
    text=replace(text,'    void SetRetxThresh(uint32_t retxThresh);',
                 '    void SetRetxThresh(uint32_t retxThresh);\n'
                 '    void HoldNewDataUntil(Time until);\n    void ReleaseNewDataHold();')
    text=replace(text,'    EventId m_sendPendingDataEvent{};',
                 '    Time m_orbitHoldUntil{};\n    EventId m_orbitHoldRelease{};\n'
                 '    EventId m_sendPendingDataEvent{};')
    changed[SOCKET+'.h']=text
    text=(r/(SOCKET+'.cc')).read_text()
    text=replace(text,'            // It\'s time to transmit, but before do silly window and Nagle\'s check',
        '            // Hold only previously unsent data; loss recovery remains available.\n'
        '            if (Simulator::Now() < m_orbitHoldUntil &&\n'
        '                next >= m_tcb->m_highTxMark.Get())\n'
        '            {\n                break;\n            }\n'
        '            // It\'s time to transmit, but before do silly window and Nagle\'s check')
    text=replace(text,'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)',
        'void\nTcpSocketBase::HoldNewDataUntil(Time until)\n'
        '{\n'
        '    if (until <= Simulator::Now()) return;\n'
        '    m_orbitHoldUntil = std::max(m_orbitHoldUntil, until);\n'
        '    m_orbitHoldRelease.Cancel();\n'
        '    m_orbitHoldRelease = Simulator::Schedule(m_orbitHoldUntil - Simulator::Now(),\n'
        '        &TcpSocketBase::ReleaseNewDataHold, this);\n'
        '}\n\n'
        'void\nTcpSocketBase::ReleaseNewDataHold()\n'
        '{\n'
        '    m_orbitHoldUntil = Time();\n'
        '    if (m_endPoint != nullptr || m_endPoint6 != nullptr) SendPendingData(m_connected);\n'
        '}\n\n'
        'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)')
    text=replace(text,'    m_sendPendingDataEvent.Cancel();',
        '    m_sendPendingDataEvent.Cancel();\n'
        '    m_orbitHoldRelease.Cancel();\n    m_orbitHoldUntil = Time();')
    changed[SOCKET+'.cc']=text
    for name,content in changed.items(): (r/name).write_text(content,newline='\n')
    subprocess.run(['git','diff','--check'],cwd=r,check=True)
    data=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=r)
    a.patch.parent.mkdir(parents=True,exist_ok=True)
    a.patch.write_bytes(data)
    subprocess.run(['git','apply','--reverse','--check',str(a.patch.resolve())],cwd=r,check=True)
    print('Patch SHA256',hashlib.sha256(data).hexdigest(),flush=True)


if __name__=='__main__': main()
