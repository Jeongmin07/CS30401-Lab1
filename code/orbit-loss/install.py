"""Install a shared-deadline old-flight SACK wait on an exact forecast-loss tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

APP='contrib/basic-sim/model/apps/tcp-flow-send-application'
SOCKET='src/internet/model/tcp-socket-base'
BUFFER='src/internet/model/tcp-tx-buffer'


def replace(text, old, new):
    if text.count(old)!=1:
        raise ValueError('Source anchor count '+str(text.count(old))+': '+old[:100])
    return text.replace(old,new)


METHODS=r'''
void
TcpSocketBase::ConfigureOrbitLoss(const std::string& path, uint64_t flow)
{
    m_orbitLossPath = path;
    m_orbitLossFlow = flow;
    std::ofstream out(path);
    out << "flow_id,time_ns,event,epoch_ns,epoch_end_ns,seq,cohort_lo,cohort_hi,last_sent_ns,"
           "sacked_pkts,budget_pkts,deadline_ns,dupacks,lost_bytes,pipe_bytes,cong_state,threshold\n";
    m_txBuffer->SetOrbitLossCallback(MakeCallback(&TcpSocketBase::DeferOrbitLoss, this));
}

void
TcpSocketBase::TraceOrbitLoss(const char* event, SequenceNumber32 seq, uint32_t sacked, Time last)
{
    if (m_orbitLossPath.empty()) return;
    std::ofstream out(m_orbitLossPath, std::ios::app);
    out << m_orbitLossFlow << ',' << Simulator::Now().GetNanoSeconds() << ',' << event << ','
        << m_orbitEpoch.GetNanoSeconds() << ',' << m_orbitEpochEnd.GetNanoSeconds() << ','
        << seq.GetValue() << ',' << m_orbitCohortLo.GetValue() << ',' << m_orbitCohortHi.GetValue()
        << ',' << last.GetNanoSeconds() << ',' << sacked << ',' << m_orbitBudget << ','
        << m_orbitDeadline.GetNanoSeconds() << ',' << m_dupAckCount << ',' << m_txBuffer->GetLost()
        << ',' << m_txBuffer->BytesInFlight() << ',' << unsigned(m_tcb->m_congState)
        << ',' << m_retxThresh << '\n';
}

void
TcpSocketBase::RegisterOrbitLossEpoch(Time end, Time wait, uint32_t budget)
{
    NS_ABORT_MSG_IF(end <= Simulator::Now() || wait <= Time(0) || budget < 3,
                    "Invalid selective loss epoch");
    m_orbitEpoch = Simulator::Now();
    m_orbitEpochEnd = end;
    m_orbitWait = wait;
    m_orbitBudget = budget;
    if (m_orbitPending || m_retxThresh != 3 || !CanForecastGuardStart())
    {
        TraceOrbitLoss("EPOCH_SKIP", m_txBuffer->HeadSequence());
        return;
    }
    m_orbitCohortLo = m_txBuffer->HeadSequence();
    m_orbitCohortHi = m_tcb->m_highTxMark;
    m_orbitEpisodeStarted = false;
    m_orbitHadDefer = false;
    m_orbitActive = m_orbitCohortHi > m_orbitCohortLo;
    TraceOrbitLoss(m_orbitActive ? "EPOCH_REGISTER" : "EPOCH_EMPTY", m_orbitCohortLo);
}

bool
TcpSocketBase::OrbitHeadWaiting() const
{
    return m_orbitActive && m_orbitPending && Simulator::Now() < m_orbitDeadline &&
        Simulator::Now() < m_orbitEpochEnd &&
        m_txBuffer->OrbitEligibleHead(m_orbitEpoch, m_orbitCohortLo, m_orbitCohortHi);
}

bool
TcpSocketBase::DeferOrbitLoss(SequenceNumber32 seq, uint32_t size, uint32_t sacked,
                            Time last, bool retrans)
{
    const Time now = Simulator::Now();
    if (!m_orbitActive || now >= m_orbitEpochEnd || m_retxThresh != 3 ||
        (m_tcb->m_congState != TcpSocketState::CA_OPEN &&
         m_tcb->m_congState != TcpSocketState::CA_DISORDER)) return false;
    if (seq < m_orbitCohortLo || seq + size > m_orbitCohortHi || last > m_orbitEpoch ||
        retrans) return false;
    if (sacked > m_orbitBudget || m_txBuffer->GetLost() != 0)
    {
        CancelOrbitLoss(sacked > m_orbitBudget ? "BUDGET_EXCEEDED" : "OTHER_LOSS");
        return false;
    }
    if (!m_txBuffer->OrbitEligibleHead(m_orbitEpoch, m_orbitCohortLo, m_orbitCohortHi))
        return false;
    const bool first = !m_orbitEpisodeStarted;
    if (first)
    {
        m_orbitEpisodeStarted = true;
        m_orbitDeadline = std::min(now + m_orbitWait, m_orbitEpochEnd);
        m_orbitWaitingHead = m_txBuffer->HeadSequence();
    }
    // All eligible holes and any advancing head share the first episode deadline.
    if (now >= m_orbitDeadline) return false;
    m_orbitPending = true;
    m_orbitHadDefer = true;
    if (first)
    {
        m_orbitLossTimer.Cancel();
        m_orbitLossTimer = Simulator::Schedule(m_orbitDeadline-now,
                            &TcpSocketBase::ExpireOrbitLoss, this);
        TraceOrbitLoss("COHORT_WAIT_BEGIN", seq, sacked, last);
    }
    else TraceOrbitLoss("COHORT_WAIT_CONTINUE", seq, sacked, last);
    return true;
}

void
TcpSocketBase::CancelOrbitLoss(const char* reason)
{
    if (m_orbitActive || m_orbitPending) TraceOrbitLoss(reason, m_txBuffer->HeadSequence());
    m_orbitActive = false;
    m_orbitPending = false;
    m_orbitLossTimer.Cancel();
}

void
TcpSocketBase::ExpireOrbitLoss()
{
    m_orbitPending = false;
    TraceOrbitLoss("COHORT_DEADLINE", m_orbitWaitingHead);
    // The saved deadline makes the callback decline the expired head here.
    if (m_tcb->m_congState != TcpSocketState::CA_OPEN &&
        m_tcb->m_congState != TcpSocketState::CA_DISORDER) return;
    m_txBuffer->ReevaluateLoss();
    const bool dupLoss = m_dupAckCount >= m_retxThresh &&
        (m_highRxAckMark >= m_recover || !m_recoverActive);
    if (m_tcb->m_congState == TcpSocketState::CA_DISORDER && !OrbitHeadWaiting() &&
        (dupLoss || m_txBuffer->IsLost(m_highRxAckMark)))
    {
        TraceOrbitLoss("DEADLINE_RECOVERY", m_highRxAckMark);
        EnterRecovery(0); // A timer acknowledges no newly delivered bytes.
        SendPendingData(m_connected);
    }
}

void
TcpSocketBase::EndOrbitLossEpoch()
{
    const bool had = m_orbitHadDefer;
    CancelOrbitLoss("EPOCH_END");
    if (had) ReevaluateLossAfterThresholdRestore();
}
'''


def transformed(root):
    out={}
    h=(root/(SOCKET+'.h')).read_text()
    h=replace(h,'#include <queue>','#include <queue>\n#include <map>\n#include <string>')
    h=replace(h,'    bool ReevaluateLossAfterThresholdRestore();',
              '    bool ReevaluateLossAfterThresholdRestore();\n'
              '    void ConfigureOrbitLoss(const std::string& path, uint64_t flow);\n'
              '    void RegisterOrbitLossEpoch(Time end, Time wait, uint32_t budget);\n'
              '    void EndOrbitLossEpoch();')
    anchor='    uint32_t m_retxThresh'
    at=h.index(anchor)
    h=h[:at]+'''    bool DeferOrbitLoss(SequenceNumber32 seq, uint32_t size, uint32_t sacked,
                        Time last, bool retrans);
    bool OrbitHeadWaiting() const;
    void ExpireOrbitLoss();
    void CancelOrbitLoss(const char* reason);
    void TraceOrbitLoss(const char* event, SequenceNumber32 seq,
                        uint32_t sacked=0, Time last=Time(0));
    std::string m_orbitLossPath;
    uint64_t m_orbitLossFlow{0};
    bool m_orbitActive{false}, m_orbitPending{false}, m_orbitHadDefer{false};
    Time m_orbitEpoch{0}, m_orbitEpochEnd{0}, m_orbitWait{0}, m_orbitDeadline{0};
    uint32_t m_orbitBudget{3};
    SequenceNumber32 m_orbitCohortLo{0}, m_orbitCohortHi{0}, m_orbitWaitingHead{0};
    bool m_orbitEpisodeStarted{false};
    EventId m_orbitLossTimer;
''' +h[at:]
    out[SOCKET+'.h']=h
    cc=(root/(SOCKET+'.cc')).read_text()
    cc=replace(cc,'#include <algorithm>','#include <algorithm>\n#include <fstream>')
    cc=replace(cc,'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)',METHODS+'\nvoid\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)')
    cc=replace(cc,'    NS_ASSERT((m_dupAckCount <= m_retxThresh) || m_recoverActive);',
                  '    NS_ASSERT((m_dupAckCount <= m_retxThresh) || m_recoverActive || m_orbitHadDefer);')
    cc=replace(cc,'((m_dupAckCount == m_retxThresh) &&\n',
       '((!OrbitHeadWaiting() && (m_dupAckCount == m_retxThresh ||\n'
       '               (m_orbitHadDefer && m_highRxAckMark >= m_orbitCohortLo &&\n'
       '                m_highRxAckMark < m_orbitCohortHi &&\n'
       '                m_dupAckCount >= m_retxThresh))) &&\n')
    cc=replace(cc,'else if (m_txBuffer->IsLost(m_highRxAckMark))',
                     'else if (!OrbitHeadWaiting() && m_txBuffer->IsLost(m_highRxAckMark))')
    cc=replace(cc,'    NS_ASSERT(m_tcb->m_congState != TcpSocketState::CA_RECOVERY);',
       '    NS_ASSERT(m_tcb->m_congState != TcpSocketState::CA_RECOVERY);\n'
       '    CancelOrbitLoss("STOCK_RECOVERY");\n    m_orbitHadDefer = false;')
    cc=replace(cc,'    uint32_t oldDupAckCount = m_dupAckCount; // remember the old value',
       '    if (m_orbitPending && ackNumber >= m_orbitCohortHi)\n'
       '    {\n        CancelOrbitLoss("ACK_MOVED_OUTSIDE_COHORT");\n    }\n'
       '    uint32_t oldDupAckCount = m_dupAckCount; // remember the old value')
    cc=replace(cc,'        if (!isDupack)\n        {\n            m_dupAckCount = 0;\n',
       '        if (!isDupack)\n        {\n            m_dupAckCount = 0;\n'
       '            m_orbitHadDefer = false;\n')
    # Cleanup only; the stock retransmission-timeout body is otherwise unchanged.
    cc=replace(cc,'TcpSocketBase::ReTxTimeout()\n{',
       'TcpSocketBase::ReTxTimeout()\n{\n    CancelOrbitLoss("STOCK_RTO");\n    m_orbitHadDefer = false;')
    cc=replace(cc,'TcpSocketBase::EnterCwr(uint32_t currentDelivered)\n{',
       'TcpSocketBase::EnterCwr(uint32_t currentDelivered)\n{\n    CancelOrbitLoss("STOCK_ECN");')
    cc=replace(cc,'TcpSocketBase::CancelAllTimers()\n{',
       'TcpSocketBase::CancelAllTimers()\n{\n    m_orbitLossTimer.Cancel();\n'
       '    m_orbitActive = false;\n    m_orbitPending = false;')
    cc=replace(cc,'        uint32_t fackDiff = 0;',
       '        if (m_orbitHadDefer && !m_orbitActive) m_txBuffer->ReevaluateLoss();\n'
       '        uint32_t fackDiff = 0;')
    out[SOCKET+'.cc']=cc
    h=(root/(BUFFER+'.h')).read_text()
    h=replace(h,'    void ReevaluateLoss();','    void ReevaluateLoss();\n'
       '    void SetOrbitLossCallback(Callback<bool, SequenceNumber32, uint32_t, uint32_t, Time, bool> cb)\n'
       '    { m_orbitLossCallback = cb; }\n'
       '    bool OrbitEligibleHead(Time epoch, SequenceNumber32 low, SequenceNumber32 high) const;')
    h=replace(h,'    uint32_t m_lostOut{0};',
       '    Callback<bool, SequenceNumber32, uint32_t, uint32_t, Time, bool> m_orbitLossCallback;\n'
       '    uint32_t m_lostOut{0};')
    out[BUFFER+'.h']=h
    cc=(root/(BUFFER+'.cc')).read_text()
    cc=replace(cc,'void\nTcpTxBuffer::UpdateLostCount()', '''bool
TcpTxBuffer::OrbitEligibleHead(Time epoch, SequenceNumber32 low, SequenceNumber32 high) const
{
    if (m_sentList.empty()) return false;
    const auto* item=m_sentList.front();
    return !item->m_lost && !item->m_sacked && !item->m_retrans && item->m_lastSent<=epoch &&
        item->m_startSeq>=low && item->m_startSeq+item->m_packet->GetSize()<=high;
}

void
TcpTxBuffer::UpdateLostCount()''')
    cc=replace(cc,'            if (!item->m_sacked && !item->m_lost)\n',
       '            if (!item->m_sacked && !item->m_lost &&\n'
       '                (m_orbitLossCallback.IsNull() ||\n'
       '                 !m_orbitLossCallback(item->m_startSeq, item->m_packet->GetSize(),\n'
       '                                      sacked, item->m_lastSent, item->m_retrans)))\n')
    old='''        TcpTxItem* item = *m_sentList.begin();
        if (!item->m_lost)
        {
            item->m_lost = true;'''
    new='''        TcpTxItem* item = *m_sentList.begin();
        if (!item->m_lost && (m_orbitLossCallback.IsNull() ||
            !m_orbitLossCallback(item->m_startSeq, item->m_packet->GetSize(),
                                 sacked, item->m_lastSent, item->m_retrans)))
        {
            item->m_lost = true;'''
    cc=replace(cc,old,new)
    out[BUFFER+'.cc']=cc
    h=(root/(APP+'.h')).read_text()
    h='#include <array>\n'+h
    h=replace(h,'  void BeginStudyWindow();',
                '  void BeginStudyWindow();\n  void BeginOrbitLossEpoch(uint32_t index);')
    h=replace(h,'  std::vector<std::pair<int64_t, int64_t>> m_studyWindows;',
       '  std::vector<std::pair<int64_t, int64_t>> m_studyWindows;\n'
       '  std::vector<std::array<int64_t, 4>> m_orbitEpochs;\n'
       '  SequenceNumber32 m_orbitNewTxHigh{0};')
    h=replace(h,'class TcpFlowSendApplication : public Application', '''// Observer-only original/retransmission metadata, zero on-wire bytes.
class OrbitOriginalTag : public Tag {
public:
  OrbitOriginalTag(bool original=false) : m_original(original) {}
  static TypeId GetTypeId() {
    static TypeId t=TypeId("ns3::OrbitOriginalTag").SetParent<Tag>()
       .SetGroupName("Applications").AddConstructor<OrbitOriginalTag>();
    return t;
  }
  TypeId GetInstanceTypeId() const override { return GetTypeId(); }
  uint32_t GetSerializedSize() const override { return 1; }
  void Serialize(TagBuffer b) const override { b.WriteU8(m_original); }
  void Deserialize(TagBuffer b) override { m_original=b.ReadU8(); }
  void Print(std::ostream& out) const override { out << m_original; }
  bool IsOriginal() const { return m_original; }
private: bool m_original;
};

class TcpFlowSendApplication : public Application''')
    out[APP+'.h']=h
    cc=(root/(APP+'.cc')).read_text()
    cc=replace(cc,'key != "study_bounded_restore")',
                'key != "study_bounded_restore" && key != "study_selective_epochs")')
    cc=replace(cc,'            } else if (key == "study_restore_limit_ns") {',
       '''            } else if (key == "study_selective_epochs") {
                for (const auto& epoch : split_string(value, "|")) {
                    const auto fields = split_string(epoch, ":");
                    NS_ABORT_MSG_IF(fields.size() != 4, "Expected start:end:wait:budget");
                    std::array<int64_t, 4> e;
                    for (uint32_t i=0; i<4; ++i) e[i]=parse_positive_int64(fields[i]);
                    NS_ABORT_MSG_IF(e[0]>=e[1] || e[2]<1000000 || e[2]>20000000 || e[3]<3 ||
                         e[3]>std::numeric_limits<uint32_t>::max(), "Invalid selective epoch");
                    NS_ABORT_MSG_IF(!m_orbitEpochs.empty() && e[0]<m_orbitEpochs.back()[1],
                                     "Selective epochs overlap");
                    m_orbitEpochs.push_back(e);
                }
            } else if (key == "study_restore_limit_ns") {''')
    anchor='    int64_t now = Simulator::Now().GetNanoSeconds();'
    cc=replace(cc,anchor,'''    NS_ABORT_MSG_IF(!m_orbitEpochs.empty() &&
                    (!m_studyWindows.empty() || m_studyEffectiveThreshold != 3),
                    "Selective epochs require baseline K3 without scalar windows");
    int64_t now = Simulator::Now().GetNanoSeconds();
    if (!m_orbitEpochs.empty()) {
        m_socket->GetObject<TcpSocketBase>()->ConfigureOrbitLoss(m_baseLogsDir + "/" +
            format_string("tcp_flow_%" PRIu64 "_orbit_loss.csv", m_tcpFlowId), m_tcpFlowId);
        for (uint32_t i=0; i<m_orbitEpochs.size(); ++i) {
            const auto& e=m_orbitEpochs[i];
            NS_ABORT_MSG_IF(e[0]<now, "Selective epoch precedes application start");
            m_studyWindowEvents.push_back(Simulator::Schedule(NanoSeconds(e[0]-now),
                &TcpFlowSendApplication::BeginOrbitLossEpoch, this, i));
        }
    }''')
    cc=replace(cc,'void TcpFlowSendApplication::BeginStudyWindow() {',
       '''void TcpFlowSendApplication::BeginOrbitLossEpoch(uint32_t index) {
    if (!m_socket) return;
    const auto& e=m_orbitEpochs.at(index);
    auto socket=m_socket->GetObject<TcpSocketBase>();
    socket->RegisterOrbitLossEpoch(NanoSeconds(e[1]), NanoSeconds(e[2]), uint32_t(e[3]));
    m_studyWindowEvents.push_back(Simulator::Schedule(
        NanoSeconds(e[1]-Simulator::Now().GetNanoSeconds()),
        &TcpSocketBase::EndOrbitLossEpoch, socket));
}

void TcpFlowSendApplication::BeginStudyWindow() {''')
    cc=replace(cc,'    InsertStudyPacket("TX", packet, header);', '''    const auto seq=header.GetSequenceNumber();
    const auto end=seq+packet->GetSize();
    const bool original=packet->GetSize()>0 && seq>=m_orbitNewTxHigh;
    if (original) m_orbitNewTxHigh=end;
    OrbitOriginalTag oldOriginal;
    mutablePacket->RemovePacketTag(oldOriginal);
    mutablePacket->AddPacketTag(OrbitOriginalTag(original));
    InsertStudyPacket("TX", packet, header);''')
    out[APP+'.cc']=cc
    main='scratch/main_satnet/main_satnet.cc'
    cc=(root/main).read_text()
    cc=replace(cc,'#include "study_drop_trace.h"',
                     '#include "study_drop_trace.h"\n#include "old_flight_drop.h"')
    cc=replace(cc,'    cs30401study::Install(topology->GetNodes());',
       '    cs30401study::Install(topology->GetNodes());\n'
       '    InstallOrbitOldFlightDrop(topology->GetNodes());')
    out[main]=cc
    out['scratch/main_satnet/old_flight_drop.h']=(Path(__file__).parent/'old_flight_drop.h').read_text()
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--base',type=Path,default=Path('/work/code/predict-loss/ns3.patch'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): raise ValueError('Output already exists')
    git=['git','-c','core.autocrlf=false']
    baseline=subprocess.check_output(git+['diff','--binary'],cwd=a.root)
    if baseline!=a.base.read_bytes(): raise ValueError('Not exact forecast-loss base')
    changes=transformed(a.root)
    before={k:hashlib.sha256((a.root/k).read_bytes()).hexdigest() if (a.root/k).exists() else None
            for k in changes}
    for k,v in changes.items(): (a.root/k).write_text(v,newline='\n')
    subprocess.run(git+['add','-N','scratch/main_satnet/old_flight_drop.h'],cwd=a.root,check=True)
    subprocess.run(git+['diff','--check'],cwd=a.root,check=True)
    patch=subprocess.check_output(git+['diff','--binary'],cwd=a.root)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(patch)
    subprocess.run(git+['apply','--reverse','--check',str(a.out)],cwd=a.root,check=True)
    print(json.dumps({'base_sha256':hashlib.sha256(baseline).hexdigest(),
        'patch_sha256':hashlib.sha256(patch).hexdigest(), 'before':before,
        'after':{k:hashlib.sha256((a.root/k).read_bytes()).hexdigest() for k in changes}},indent=2))


if __name__=='__main__': main()
