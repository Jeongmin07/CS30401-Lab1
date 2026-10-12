"""Apply the exact V2 base plus an opt-in one-tail admission in a fresh ns-3 tree."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=Path('/home/ubuntu/ns-3.48')
BASE=REPO/'code/orbit-loss/ns3.patch'
EXPECTED='531bf802984af821afd928fb3932912aca383fcdec5771f30f78d75a806d5591'


def replace(text,old,new):
    if text.count(old)!=1: raise ValueError('Ambiguous source anchor '+old[:90])
    return text.replace(old,new)


METHOD=r'''
void
TcpSocketBase::TryOrbitTail(uint32_t newSackBytes, uint32_t normalPackets)
{
    if (!m_orbitTailEnabled || newSackBytes == 0 || !OrbitHeadWaiting() ||
        m_tcb->m_congState != TcpSocketState::CA_DISORDER) return;
    const SequenceNumber32 seq = m_tcb->m_highTxMark;
    const uint32_t unsent = m_txBuffer->SizeFromSequence(seq);
    const uint32_t pipe = BytesInFlight();
    const uint32_t cwnd = m_tcb->m_cWnd.Get();
    const SequenceNumber32 right = m_highRxAckMark + SequenceNumber32(m_rWnd.Get());
    const uint32_t window = AvailableWindow();
    const bool usedBefore = m_orbitTailUsed;
    const char* reason = nullptr;
    if (m_orbitTailUsed) reason = "ALREADY_USED";
    else if (!m_closeOnEmpty && !m_shutdownSend) reason = "APPLICATION_OPEN";
    else if (unsent == 0) reason = "NO_UNSENT";
    else if (unsent > m_tcb->m_segmentSize) reason = "MORE_THAN_ONE_MSS";
    else if (window >= unsent) reason = "ORDINARY_ALLOWANCE_AVAILABLE";
    else if (m_tcb->m_nextTxSequence != seq) reason = "NEXT_TX_NOT_NEW";
    else if (right < seq + SequenceNumber32(unsent)) reason = "RECEIVER_WINDOW";
    else if (uint64_t(pipe) + unsent > uint64_t(cwnd) + m_tcb->m_segmentSize)
        reason = "PIPE_BOUND";
    else if (IsPacingEnabled() && m_pacingTimer.IsRunning()) reason = "PACING_TIMER";
    uint32_t sent = 0;
    if (!reason)
    {
        // This allowance is not a delivered-ACK credit and never changes cwnd.
        m_orbitTailUsed = true; // Reserve before callbacks: one original per episode.
        sent = SendDataPacket(seq, unsent, m_connected);
        NS_ABORT_MSG_IF(sent != unsent, "Orbit tail did not send the declared original bytes");
        m_tcb->m_nextTxSequence = seq + SequenceNumber32(sent);
        NS_ABORT_MSG_IF(m_tcb->m_cWnd.Get() != cwnd, "Orbit tail changed cwnd");
        reason = "TAIL_ADMIT";
    }
    const uint32_t after = BytesInFlight();
    NS_ABORT_MSG_IF(sent && uint64_t(after) > uint64_t(cwnd) + m_tcb->m_segmentSize,
                    "Orbit tail exceeded the one-MSS flight allowance");
    if (!m_orbitTailPath.empty())
    {
        std::ofstream out(m_orbitTailPath, std::ios::app);
        out << m_orbitLossFlow << ',' << Simulator::Now().GetNanoSeconds() << ',' << reason
            << ',' << m_orbitEpoch.GetNanoSeconds() << ',' << m_orbitDeadline.GetNanoSeconds()
            << ',' << seq.GetValue() << ',' << sent << ',' << newSackBytes << ',' << unsent
            << ',' << pipe << ',' << after << ',' << cwnd << ',' << right.GetValue()
            << ',' << usedBefore << ',' << m_orbitTailUsed << ',' << unsigned(m_tcb->m_congState)
            << ',' << m_closeOnEmpty << ',' << m_shutdownSend << ',' << normalPackets
            << ',' << window << '\n';
    }
}
'''


if __name__=='__main__':
    if hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED: raise ValueError('Base patch changed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
        raise ValueError('Only a clean official tree is accepted')
    subprocess.run(['git','apply',str(BASE)],cwd=ROOT,check=True)
    cc=ROOT/'src/internet/model/tcp-socket-base.cc'
    hh=ROOT/'src/internet/model/tcp-socket-base.h'
    text=cc.read_text()
    text=replace(text,'            .AddAttribute("LimitedTransmit",',
        '            .AddAttribute("OrbitTailAdmission", "One extra final original segment in a selective wait",\n'
        '                          BooleanValue(false),\n'
        '                          MakeBooleanAccessor(&TcpSocketBase::m_orbitTailEnabled),\n'
        '                          MakeBooleanChecker())\n'
        '            .AddAttribute("LimitedTransmit",')
    text=replace(text,'      m_closeOnEmpty(sock.m_closeOnEmpty),',
        '      m_closeOnEmpty(sock.m_closeOnEmpty),\n      m_orbitTailEnabled(sock.m_orbitTailEnabled),')
    text=replace(text,'    SendPendingData(m_connected);\n}\n\nvoid\nTcpSocketBase::ProcessAck(',
        '    const uint32_t normalPackets = SendPendingData(m_connected);\n'
        '    TryOrbitTail(bytesSacked, normalPackets);\n}\n\nvoid\nTcpSocketBase::ProcessAck(')
    text=replace(text,'    m_txBuffer->SetOrbitLossCallback(MakeCallback(&TcpSocketBase::DeferOrbitLoss, this));',
        '    m_orbitTailPath = path.substr(0, path.size()-4) + "_tail.csv";\n'
        '    std::ofstream tail(m_orbitTailPath);\n'
        '    tail << "flow_id,time_ns,event,epoch_ns,deadline_ns,seq,admitted_bytes,new_sack_bytes,"'
        '\n            "unsent_bytes,pipe_before,pipe_after,cwnd_bytes,receiver_right_edge,used_before,used_after,"'
        '\n            "cong_state,close_on_empty,shutdown_send,normal_packets_sent,ordinary_window_bytes\\n";\n'
        '    m_txBuffer->SetOrbitLossCallback(MakeCallback(&TcpSocketBase::DeferOrbitLoss, this));')
    text=replace(text,'    m_orbitEpisodeStarted = false;\n    m_orbitHadDefer = false;',
        '    m_orbitEpisodeStarted = false;\n    m_orbitTailUsed = false;\n    m_orbitHadDefer = false;')
    text=replace(text,'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)',
        METHOD+'\nvoid\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)')
    cc.write_text(text)
    text=hh.read_text()
    text=replace(text,'    bool m_orbitActive{false}, m_orbitPending{false}, m_orbitHadDefer{false};',
        '    bool m_orbitActive{false}, m_orbitPending{false}, m_orbitHadDefer{false};\n'
        '    void TryOrbitTail(uint32_t newSackBytes, uint32_t normalPackets);\n'
        '    bool m_orbitTailEnabled{false}, m_orbitTailUsed{false};\n'
        '    std::string m_orbitTailPath;')
    hh.write_text(text)
    subprocess.run(['git','add','-N','scratch/main_satnet/study_drop_trace.h',
        'scratch/main_satnet/old_flight_drop.h','scratch/study_micro/study_micro.cc'],cwd=ROOT,check=True)
    patch=subprocess.check_output(['git','-c','core.autocrlf=false','diff','--binary','HEAD'],cwd=ROOT)
    (HERE/'ns3.patch').write_bytes(patch)
    (HERE/'install-receipt.json').write_text(json.dumps(dict(base_patch_sha256=EXPECTED,
        final_patch_sha256=hashlib.sha256(patch).hexdigest(),installer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ns3_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        tail_source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [cc,hh]}),indent=2)+'\n')
    print('Installed opt-in tail policy; combined patch exported')
