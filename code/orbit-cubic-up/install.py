"""Compose canonical v6 with passive socket-window, device queue/service observers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def once(s, old, new):
    if s.count(old) != 1: raise ValueError('Ambiguous source anchor: '+repr(old[:100]))
    return s.replace(old,new)

METHODS = r'''
void TcpSocketBase::SetOrbitWindowObservationFlow(uint64_t flow) {
    const char* enabled = std::getenv("CS30401_ORBIT_WINDOW_TRACE");
    m_orbitWindowEnabled = enabled && std::string(enabled) == "1";
    m_orbitWindowFlow = flow;
}
void TcpSocketBase::ObserveOrbitWindow(const char* phase, uint32_t available, uint32_t sent) {
    if (!m_orbitWindowEnabled) return;
    const int64_t now = Simulator::Now().GetNanoSeconds();
    const bool focus = (now>=26100000000 && now<26600000000) ||
                       (now>=74900000000 && now<75400000000) ||
                       (now>=121100000000 && now<124100000000) ||
                       (now>=186900000000 && now<189900000000);
    const int64_t bucket = now/100000000;
    if (!focus && bucket==m_orbitWindowBucket) return;
    m_orbitWindowBucket = bucket;
    static std::unique_ptr<std::ofstream> out;
    if (!out) {
        const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");
        NS_ABORT_MSG_IF(!directory,"Missing window trace directory");
        out=std::make_unique<std::ofstream>(std::string(directory)+"/orbit_window.csv");
        NS_ABORT_MSG_IF(!out->good(),"Cannot create window trace");
        *out << "time_ns,flow_id,phase,focus,cwnd_bytes,ssthresh_bytes,pipe_bytes,rwnd_bytes,available_window_bytes,unsent_bytes,buffer_bytes,segment_bytes,cong_state,socket_state,cwnd_limited,pacing_enabled,srtt_ns,last_rtt_ns,next_seq,high_tx_mark,packets_sent\n";
    }
    *out << now << ',' << m_orbitWindowFlow << ',' << phase << ',' << focus
         << ',' << m_tcb->m_cWnd.Get() << ',' << m_tcb->m_ssThresh.Get()
         << ',' << m_tcb->m_bytesInFlight.Get() << ',' << m_rWnd.Get() << ',' << available
         << ',' << m_txBuffer->SizeFromSequence(m_tcb->m_highTxMark.Get())
         << ',' << m_txBuffer->Size() << ',' << m_tcb->m_segmentSize
         << ',' << static_cast<int>(m_tcb->m_congState) << ',' << static_cast<int>(m_state)
         << ',' << m_tcb->m_isCwndLimited << ',' << IsPacingEnabled()
         << ',' << m_tcb->m_srtt.Get().GetNanoSeconds()
         << ',' << m_tcb->m_lastRtt.Get().GetNanoSeconds()
         << ',' << m_tcb->m_nextTxSequence.Get().GetValue()
         << ',' << m_tcb->m_highTxMark.Get().GetValue() << ',' << sent << '\n';
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3-root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--patch',type=Path,default=HERE/'ns3.patch')
    a=p.parse_args();r=a.ns3_root
    if a.patch.exists(): raise ValueError('Output patch must be new')
    def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false',*args],cwd=r)
    if git('status','--porcelain').strip():raise ValueError('Expected clean official source')
    base=REPO/'code/kim-study/ns3-v6.patch'
    subprocess.run(['git','apply','--check',str(base)],cwd=r,check=True)
    subprocess.run(['git','apply',str(base)],cwd=r,check=True)
    subprocess.run(['git','add','-N','scratch/main_satnet/study_drop_trace.h','scratch/study_micro/study_micro.cc'],cwd=r,check=True)
    if git('diff','--binary')!=base.read_bytes():raise ValueError('Installed canonical v6 differs')
    h=r/'src/internet/model/tcp-socket-base.h';s=h.read_text()
    s=once(s,'    static TypeId GetTypeId();','    static TypeId GetTypeId();\n    void SetOrbitWindowObservationFlow(uint64_t flow);')
    s=once(s,'    uint32_t SendPendingData(bool withAck = false);','    uint32_t SendPendingData(bool withAck = false);\n    void ObserveOrbitWindow(const char* phase, uint32_t available, uint32_t sent);\n    bool m_orbitWindowEnabled{false};\n    uint64_t m_orbitWindowFlow{0};\n    int64_t m_orbitWindowBucket{-1};')
    h.write_text(s,newline='\n')
    cc=r/'src/internet/model/tcp-socket-base.cc';s=cc.read_text()
    s=once(s,'#include "tcp-socket-base.h"','#include "tcp-socket-base.h"\n#include <cstdlib>\n#include <fstream>\n#include <memory>')
    s=once(s,'    uint32_t availableWindow = AvailableWindow();','    uint32_t availableWindow = AvailableWindow();\n    ObserveOrbitWindow("BEGIN", availableWindow, 0);')
    s=once(s,'    return nPacketsSent;','    ObserveOrbitWindow("END", availableWindow, nPacketsSent);\n    return nPacketsSent;')
    s=once(s,'} // namespace ns3',METHODS+'\n} // namespace ns3');cc.write_text(s,newline='\n')
    app=r/'contrib/basic-sim/model/apps/tcp-flow-send-application.cc';s=app.read_text()
    s=once(s,'void TcpFlowSendApplication::InitializeStudy() {','void TcpFlowSendApplication::InitializeStudy() {\n    m_socket->GetObject<TcpSocketBase>()->SetOrbitWindowObservationFlow(m_tcpFlowId);')
    app.write_text(s,newline='\n')
    main=r/'scratch/main_satnet/main_satnet.cc';s=main.read_text()
    s=once(s,'#include "study_drop_trace.h"','#include "study_drop_trace.h"\n#include "orbit_cubic_queue.h"\n#include "orbit_cubic_service.h"')
    s=once(s,'    cs30401study::Install(topology->GetNodes());','    cs30401study::Install(topology->GetNodes());\n    orbitcubicqueue::Install(topology->GetNodes());\n    orbitcubicservice::Install(topology->GetNodes());')
    main.write_text(s,newline='\n')
    for name in ['queue_observer.h','service_observer.h']:
        destination='scratch/main_satnet/'+('orbit_cubic_queue.h' if name.startswith('queue') else 'orbit_cubic_service.h')
        (r/destination).write_text((HERE/name).read_text(),newline='\n')
        subprocess.run(['git','add','-N',destination],cwd=r,check=True)
    subprocess.run(['git','diff','--check'],cwd=r,check=True)
    a.patch.write_bytes(git('diff','--binary','HEAD'))
    subprocess.run(['git','apply','--reverse','--check',str(a.patch)],cwd=r,check=True)
    print(json.dumps({'patch_sha256':hashlib.sha256(a.patch.read_bytes()).hexdigest(),'baseline_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'ns3_head':git('rev-parse','HEAD').decode().strip()}))

if __name__=='__main__':main()
