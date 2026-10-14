"""Apply an opt-in ELT-inspired overlay to the exact frozen ace08 source.

This helper touches only tcp-socket-base.cc/.h in a NEW supplied ns-3 tree.
It does not build, run, reset Git, apply the frozen base, or alter old volumes.
"""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    'tcp-socket-base.cc': 'baed29017f11b6f984adc3307fbe9c4d1e63d07a40114a9f42c117293a7461cb',
    'tcp-socket-base.h': '2303f2a83affaf95439a547d416bf8a4153cf442f4a7c7afed303723eb182e12',
}


def replace(source, old, new):
    assert source.count(old) == 1, 'Unexpected source anchor: ' + old[:100]
    return source.replace(old, new, 1)


METHODS = r'''
// Bounded ELT-inspired transmission within the existing selective wait.
// This is not the complete TCP-NCR algorithm: K3 and the short deadline stay.
void
TcpSocketBase::TraceOrbitElt(const char* event, SequenceNumber32 seq, uint32_t sent)
{
    if (m_orbitEltMode == 0 || m_orbitEltPath.empty()) return;
    std::ofstream out(m_orbitEltPath, std::ios::app);
    const auto high = m_tcb->m_highTxMark.Get();
    const auto right = m_highRxAckMark + SequenceNumber32(m_rWnd.Get());
    out << m_orbitLossFlow << ',' << Simulator::Now().GetNanoSeconds() << ',' << event
        << ',' << m_orbitEltMode << ',' << m_orbitEpoch.GetNanoSeconds()
        << ',' << m_orbitDeadline.GetNanoSeconds() << ',' << m_orbitEltFlight
        << ',' << BytesInFlight() << ',' << m_orbitEltSkipped
        << ',' << m_tcb->m_cWnd.Get() << ',' << m_tcb->m_ssThresh.Get()
        << ',' << m_txBuffer->SizeFromSequence(high) << ',' << m_orbitEltSackBytes
        << ',' << sent << ',' << seq.GetValue() << ',' << m_txBuffer->HeadSequence().GetValue()
        << ',' << high.GetValue() << ',' << right.GetValue()
        << ',' << m_orbitEltActive << ',' << m_orbitEltUsed << '\n';
}

void
TcpSocketBase::BeginOrbitElt(uint32_t flight, uint32_t newSackBytes)
{
    if (m_orbitEltMode == 0 || m_orbitEltUsed || !OrbitHeadWaiting()) return;
    NS_ABORT_MSG_IF(!m_sackEnabled || m_fackEnabled || flight == 0,
                    "ELT requires a nonempty SACK/no-FACK selective flight");
    m_orbitEltFlight = flight; // HighTx - Head, sampled before this ACK's SACK update.
    m_orbitEltSkipped = 0;
    m_orbitEltSackBytes = newSackBytes;
    m_orbitEltUsed = true; // Never refresh/restart within the existing wait episode.
    m_orbitEltCackPending = false;
    m_orbitEltActive = true;
    TraceOrbitElt("ELT_BEGIN", m_tcb->m_highTxMark);
}

void
TcpSocketBase::EndOrbitElt(const char* reason, bool cumulativeAck)
{
    if (!m_orbitEltActive && !m_orbitEltCackPending) return;
    if (cumulativeAck)
    {
        // RFC4653 T1/T2, after DiscardUpTo/NewAck/CC callbacks and before sending.
        TraceOrbitElt("ELT_CACK_BEFORE", m_tcb->m_highTxMark);
        // FIN consumes sequence space but is not an outstanding data byte.
        const auto high = m_tcb->m_highTxMark.Get();
        const auto head = m_txBuffer->HeadSequence();
        const uint64_t postAckFlight = high >= head ? uint32_t(high - head) : 0;
        m_tcb->m_cWnd = static_cast<uint32_t>(std::min<uint64_t>(
            postAckFlight + m_tcb->m_segmentSize, m_orbitEltFlight));
        m_tcb->m_cWndInfl = m_tcb->m_cWnd.Get();
        m_tcb->m_ssThresh = m_orbitEltFlight;
    }
    m_orbitEltActive = false;
    m_orbitEltCackPending = false;
    m_orbitEltAckDriven = false;
    const std::string event = std::string("ELT_EXIT_") + reason;
    TraceOrbitElt(event.c_str(), m_tcb->m_highTxMark);
}

bool
TcpSocketBase::OrbitEltOwnsNewData() const
{
    return m_orbitEltMode != 0 && m_orbitEltActive && OrbitHeadWaiting() &&
        m_tcb->m_congState == TcpSocketState::CA_DISORDER;
}

uint32_t
TcpSocketBase::OrbitEltWindow()
{
    if (m_orbitEltMode == 0 || !m_orbitEltActive) return AvailableWindow();
    if (!OrbitEltOwnsNewData() || m_txBuffer->GetLost() != 0)
    {
        EndOrbitElt("WAIT_OR_LOSS_STATE", false);
        return AvailableWindow();
    }
    if (!m_orbitEltAckDriven)
    {
        TraceOrbitElt("ELT_SKIP_NO_NEW_SACK", m_tcb->m_highTxMark);
        return 0; // Application/pacing callbacks cannot manufacture SACK progress.
    }
    const uint64_t used = uint64_t(BytesInFlight()) + m_orbitEltSkipped;
    const uint32_t room = used < m_orbitEltFlight ? m_orbitEltFlight - used : 0;
    const SequenceNumber32 seq = m_tcb->m_highTxMark;
    const auto right = m_highRxAckMark + SequenceNumber32(m_rWnd.Get());
    const uint32_t receiverRoom = right > seq ? right - seq : 0;
    if (room < m_tcb->m_segmentSize)
    {
        TraceOrbitElt("ELT_SKIP_CEILING", seq);
        return 0;
    }
    if (receiverRoom < m_tcb->m_segmentSize)
    {
        TraceOrbitElt("ELT_SKIP_RECEIVER", seq);
        return 0;
    }
    // Temporary E2 permission is bounded by fixed FlightSizePrev, not cwnd.
    // The ordinary cwnd field is never inflated to create sending credit.
    return std::min(room, receiverRoom);
}

'''


def transform(cc, header):
    cc = replace(cc, '            .AddAttribute("OrbitTailAdmission",', '''            .AddAttribute("OrbitEltMode", "0=OFF, 1=Aggressive, 2=Careful bounded ELT-inspired send",
                          UintegerValue(0),
                          MakeUintegerAccessor(&TcpSocketBase::m_orbitEltMode),
                          MakeUintegerChecker<uint32_t>(0, 2))
            .AddAttribute("OrbitTailAdmission",''')
    cc = replace(cc, '      m_orbitTailEnabled(sock.m_orbitTailEnabled),',
                    '      m_orbitTailEnabled(sock.m_orbitTailEnabled),\n      m_orbitEltMode(sock.m_orbitEltMode),')
    cc = replace(cc, '    uint32_t previousLost = m_txBuffer->GetLost();', '''    // ReadOptions may start the existing wait inside UpdateLostCount.
    const bool eltWasWaiting = m_orbitEltMode != 0 && OrbitHeadWaiting();
    const uint32_t eltFlightSnapshot = m_orbitEltMode != 0 ? UnAckDataCount() : 0;
    if (m_orbitEltMode != 0) m_orbitEltSackBytes = 0;
    uint32_t previousLost = m_txBuffer->GetLost();''')
    cc = replace(cc, '    if ((ackNumber > oldHeadSequence) && (ackNumber < m_recover) &&', '''    if (m_orbitEltMode != 0 && !eltWasWaiting && OrbitHeadWaiting())
    {
        BeginOrbitElt(eltFlightSnapshot, bytesSacked);
    }
    if ((ackNumber > oldHeadSequence) && (ackNumber < m_recover) &&''')
    cc = replace(cc, '    const uint32_t normalPackets = SendPendingData(m_connected);\n    TryOrbitTail(bytesSacked, normalPackets);', '''    if (m_orbitEltMode != 0)
    {
        m_orbitEltSackBytes = bytesSacked;
        if ((m_orbitEltActive || m_orbitEltCackPending) && ackNumber > oldHeadSequence)
        {
            EndOrbitElt("CACK", true);
        }
        m_orbitEltAckDriven = m_orbitEltActive && bytesSacked > 0;
    }
    const uint32_t normalPackets = SendPendingData(m_connected);
    TryOrbitTail(bytesSacked, normalPackets);
    m_orbitEltAckDriven = false;
    m_orbitEltSackBytes = 0;''')
    cc = replace(cc, '    uint32_t availableWindow = AvailableWindow();',
                    '    uint32_t availableWindow = OrbitEltWindow();')
    cc = replace(cc, '                NS_LOG_INFO("Skipping Packet due to pacing" << m_pacingTimer.GetDelayLeft());', '''                NS_LOG_INFO("Skipping Packet due to pacing" << m_pacingTimer.GetDelayLeft());
                if (OrbitEltOwnsNewData()) TraceOrbitElt("ELT_SKIP_PACING", m_tcb->m_highTxMark);''')
    cc = replace(cc, '''            // It's time to transmit, but before do silly window and Nagle's check
            uint32_t availableData = m_txBuffer->SizeFromSequence(next);''', '''            if (OrbitEltOwnsNewData() && next != m_tcb->m_highTxMark)
            {
                // A stored loss keeps the stock retransmission path and allowance.
                EndOrbitElt("NON_NEW_SELECTION", false);
                availableWindow = AvailableWindow();
                if (availableWindow == 0) break;
            }
            const bool eltNewData = OrbitEltOwnsNewData();
            // It's time to transmit, but before do silly window and Nagle's check
            uint32_t availableData = m_txBuffer->SizeFromSequence(next);
            if (eltNewData && availableData < m_tcb->m_segmentSize)
            {
                TraceOrbitElt("ELT_SKIP_PARTIAL", next);
                break; // The initial pilot intentionally admits only full MSS.
            }''')
    cc = replace(cc, '''            s = std::min(s, maxSizeToSend);

            // (C.2)''', '''            s = std::min(s, maxSizeToSend);
            if (eltNewData && s != m_tcb->m_segmentSize)
            {
                TraceOrbitElt("ELT_SKIP_PARTIAL", next);
                break;
            }

            // (C.2)''')
    cc = replace(cc, '''            uint32_t sz = SendDataPacket(m_tcb->m_nextTxSequence, s, withAck);

            NS_LOG_LOGIC''', '''            if (eltNewData)
            {
                NS_ABORT_MSG_IF(uint64_t(BytesInFlight()) + m_orbitEltSkipped + s > m_orbitEltFlight,
                                "ELT pre-send E2 permission changed");
                TraceOrbitElt("ELT_SEND_BEFORE", next, s);
            }
            uint32_t sz = SendDataPacket(m_tcb->m_nextTxSequence, s, withAck);
            if (eltNewData)
            {
                NS_ABORT_MSG_IF(sz != m_tcb->m_segmentSize, "ELT sent a partial original");
                if (m_orbitEltMode == 2) m_orbitEltSkipped += sz;
                NS_ABORT_MSG_IF(BytesInFlight() > m_orbitEltFlight,
                                "ELT exceeded physical entry-flight permission");
                NS_ABORT_MSG_IF(uint64_t(BytesInFlight()) + m_orbitEltSkipped >
                                uint64_t(m_orbitEltFlight) + (m_orbitEltMode == 2 ? sz : 0),
                                "ELT post-send virtual accounting changed");
                TraceOrbitElt("ELT_NEW_TX", next, sz);
            }

            NS_LOG_LOGIC''')
    cc = replace(cc, '\n        availableWindow = AvailableWindow();\n\n        // (C.5)',
                    '\n        availableWindow = OrbitEltWindow();\n\n        // (C.5)')
    cc = replace(cc, '    m_orbitTailPath = path.substr(0, path.size()-4) + "_tail.csv";', '''    m_orbitEltPath = path.substr(0, path.size()-4) + "_elt.csv";
    std::ofstream elt(m_orbitEltPath);
    elt << "flow_id,time_ns,event,mode,epoch_ns,deadline_ns,saved_flight_bytes,pipe_bytes,"
           "skipped_bytes,cwnd_bytes,ssthresh_bytes,unsent_bytes,new_sack_bytes,sent_bytes,"
           "seq,head_seq,high_tx,receiver_right_edge,active,phase_used\\n";
    m_orbitTailPath = path.substr(0, path.size()-4) + "_tail.csv";''')
    cc = replace(cc, '    m_orbitEpisodeStarted = false;\n    m_orbitTailUsed = false;', '''    EndOrbitElt("NEW_EPOCH", false);
    m_orbitEltUsed = false;
    m_orbitEltCackPending = false;
    m_orbitEltAckDriven = false;
    m_orbitEpisodeStarted = false;
    m_orbitTailUsed = false;''')
    cc = replace(cc, '''TcpSocketBase::CancelOrbitLoss(const char* reason)
{
''', '''TcpSocketBase::CancelOrbitLoss(const char* reason)
{
    if (m_orbitEltActive && std::string(reason) == "ACK_MOVED_OUTSIDE_COHORT")
    {
        // ProcessAck is before its CC/NewAck callbacks. Apply T1/T2 only later.
        m_orbitEltCackPending = true;
        m_orbitEltActive = false;
        m_orbitEltAckDriven = false;
        TraceOrbitElt("ELT_CACK_PENDING", m_tcb->m_highTxMark);
    }
    else EndOrbitElt(reason, false);
''')
    cc = replace(cc, '''TcpSocketBase::ExpireOrbitLoss()
{
''', '''TcpSocketBase::ExpireOrbitLoss()
{
    EndOrbitElt("DEADLINE", false);
''')
    cc = replace(cc, '''TcpSocketBase::CancelAllTimers()
{
''', '''TcpSocketBase::CancelAllTimers()
{
    EndOrbitElt("SOCKET_TIMERS", false);
''')
    cc = replace(cc, '    if (!m_orbitTailEnabled || newSackBytes == 0 || !OrbitHeadWaiting() ||',
                    '    if (m_orbitEltMode != 0 || !m_orbitTailEnabled || newSackBytes == 0 || !OrbitHeadWaiting() ||')
    cc = replace(cc, 'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)',
                    METHODS + 'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)')
    header = replace(header, '    std::string m_orbitTailPath;', '''    std::string m_orbitTailPath;
    void BeginOrbitElt(uint32_t flight, uint32_t newSackBytes);
    void EndOrbitElt(const char* reason, bool cumulativeAck);
    void TraceOrbitElt(const char* event, SequenceNumber32 seq, uint32_t sent=0);
    bool OrbitEltOwnsNewData() const;
    uint32_t OrbitEltWindow();
    uint32_t m_orbitEltMode{0};
    uint32_t m_orbitEltFlight{0}, m_orbitEltSkipped{0}, m_orbitEltSackBytes{0};
    bool m_orbitEltActive{false}, m_orbitEltUsed{false}, m_orbitEltAckDriven{false};
    bool m_orbitEltCackPending{false};
    std::string m_orbitEltPath;''')
    return cc, header


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ns3', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--check-only', action='store_true')
    a = p.parse_args()
    assert not a.receipt.exists(), 'Refuse an existing receipt'
    folder = a.ns3 / 'src/internet/model'
    originals = {name: (folder/name).read_bytes() for name in EXPECTED}
    assert all(hashlib.sha256(b).hexdigest() == EXPECTED[n] for n,b in originals.items()), 'Not exact frozen ace08 sources'
    cc, header = transform(*(originals[n].decode('utf-8') for n in EXPECTED))
    changed = dict(zip(EXPECTED, [cc.encode('utf-8'), header.encode('utf-8')]))
    if not a.check_only:
        for name,b in changed.items(): (folder/name).write_bytes(b)
    record = dict(schema=1,check_only=a.check_only,source_before=EXPECTED,
                  source_after={n:hashlib.sha256(b).hexdigest() for n,b in changed.items()},
                  helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  modes={'0':'OFF; existing tail setting retained','1':'Aggressive','2':'Careful'},
                  interpretation='ELT-inspired fixed entry-flight permission within existing K3 selective wait; partial RFC4653 adaptation, full-MSS pilot.')
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record))


if __name__ == '__main__': main()
