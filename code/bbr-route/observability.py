"""Install/export passive BBR course observers, or compare original measurement CSVs.

Only new observer state, read-only trace callbacks and packet metadata are added.
No TCP attributes, timers, recovery rules, routes or wire headers are changed.
Run inside the official container on a clean ns-3 checkout. Observation is OFF
unless CS30401_BBR_OBSERVE=1 and CS30401_BBR_OBSERVE_DIR names an existing directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


BBR_METHODS = r'''
void
TcpBbr::SetObservationFlow(uint64_t flowId)
{
    const char* enabled = std::getenv("CS30401_BBR_OBSERVE");
    m_observeEnabled = enabled && std::string(enabled) == "1";
    m_observeFlow = flowId;
}

void
TcpBbr::ObserveAck(Ptr<TcpSocketState> tcb, const TcpRateOps::TcpRateSample& rs)
{
    if (!m_observeEnabled) return;
    ++m_observeAcks;
    m_observeAcked += rs.m_ackedSacked;
    m_observeLost += rs.m_bytesLoss;
    const int64_t now = Simulator::Now().GetNanoSeconds();
    const int64_t bucket = now / 100000000;
    const int state = static_cast<int>(m_state);
    const double gain = m_pacingGain.Get();
    if (bucket == m_observeBucket && state == m_observeState && gain == m_observeGain) return;
    static std::unique_ptr<std::ofstream> out;
    if (!out)
    {
        const char* directory = std::getenv("CS30401_BBR_OBSERVE_DIR");
        NS_ABORT_MSG_IF(!directory, "CS30401_BBR_OBSERVE_DIR is required");
        out = std::make_unique<std::ofstream>(std::string(directory) + "/bbr_state.csv");
        NS_ABORT_MSG_IF(!out->good(), "Cannot open BBR observation CSV");
        *out << "time_ns,flow_id,reason,bbr_state,rtprop_ns,last_rtt_ns,srtt_ns,max_bw_bps,delivery_rate_bps,rate_interval_ns,pacing_gain,cwnd_gain,cwnd_bytes,inflight_bytes,pacing_rate_bps,cong_state,round_count,min_rtt_expired,pipe_filled,packet_conservation,ack_calls_total,acked_sacked_bytes_total,loss_bytes_total\n";
        out->precision(17);
    }
    *out << now << ',' << m_observeFlow << ','
         << ((state != m_observeState || gain != m_observeGain) ? "transition" : "sample")
         << ',' << state << ',';
    if (m_minRtt.Get() != Time::Max()) *out << m_minRtt.Get().GetNanoSeconds();
    *out << ',';
    if (tcb->m_lastRtt.Get() != Time::Max()) *out << tcb->m_lastRtt.Get().GetNanoSeconds();
    *out << ',';
    if (tcb->m_srtt.Get() != Time::Max()) *out << tcb->m_srtt.Get().GetNanoSeconds();
    *out << ',' << m_maxBwFilter.GetBest().GetBitRate() << ',' << rs.m_deliveryRate.GetBitRate()
         << ',' << rs.m_interval.GetNanoSeconds() << ',' << gain << ',' << m_cWndGain.Get()
         << ',' << tcb->m_cWnd.Get() << ',' << tcb->m_bytesInFlight.Get()
         << ',' << tcb->m_pacingRate.Get().GetBitRate() << ',' << static_cast<int>(tcb->m_congState)
         << ',' << m_roundCount << ',' << m_minRttExpired << ',' << m_isPipeFilled
         << ',' << m_packetConservation << ',' << m_observeAcks << ',' << m_observeAcked
         << ',' << m_observeLost << '\n';
    m_observeBucket = bucket;
    m_observeState = state;
    m_observeGain = gain;
}
'''

TAG_DECL = r'''
// PacketTag is simulator-only metadata: it contributes no bytes to the wire.
class TcpBbrObserveTag : public Tag
{
public:
  static TypeId GetTypeId();
  TypeId GetInstanceTypeId() const override;
  uint32_t GetSerializedSize() const override;
  void Serialize(TagBuffer buffer) const override;
  void Deserialize(TagBuffer buffer) override;
  void Print(std::ostream& os) const override;
  TcpBbrObserveTag() = default;
  explicit TcpBbrObserveTag(uint64_t flow) : m_flow(flow) {}
  uint64_t GetFlowId() const { return m_flow; }
private:
  uint64_t m_flow{0};
};
'''

TAG_METHODS = r'''
NS_OBJECT_ENSURE_REGISTERED(TcpBbrObserveTag);
TypeId TcpBbrObserveTag::GetTypeId() {
    static TypeId tid = TypeId("ns3::TcpBbrObserveTag").SetParent<Tag>()
        .SetGroupName("Applications").AddConstructor<TcpBbrObserveTag>();
    return tid;
}
TypeId TcpBbrObserveTag::GetInstanceTypeId() const { return GetTypeId(); }
uint32_t TcpBbrObserveTag::GetSerializedSize() const { return 8; }
void TcpBbrObserveTag::Serialize(TagBuffer buffer) const { buffer.WriteU64(m_flow); }
void TcpBbrObserveTag::Deserialize(TagBuffer buffer) { m_flow = buffer.ReadU64(); }
void TcpBbrObserveTag::Print(std::ostream& os) const { os << m_flow; }

void TcpFlowSendApplication::InitializeBbrObservation() {
    const char* enabled = std::getenv("CS30401_BBR_OBSERVE");
    if (!enabled || std::string(enabled) != "1") return;
    PointerValue congestion;
    m_socket->GetAttribute("CongestionOps", congestion);
    if (auto bbr = DynamicCast<TcpBbr>(congestion.Get<TcpCongestionOps>()))
        bbr->SetObservationFlow(m_tcpFlowId);
    NS_ABORT_MSG_IF(!m_socket->TraceConnectWithoutContext("Tx",
        MakeCallback(&TcpFlowSendApplication::ObserveBbrTx, this)), "Missing TCP Tx observer");
}
void TcpFlowSendApplication::ObserveBbrTx(Ptr<const Packet> packet, const TcpHeader&,
                                       Ptr<const TcpSocketBase>) {
    auto copy = ConstCast<Packet>(packet);
    TcpBbrObserveTag previous;
    copy->RemovePacketTag(previous);
    copy->AddPacketTag(TcpBbrObserveTag(m_tcpFlowId));
}
'''

SINK_METHODS = r'''
void TcpFlowSink::StartBbrObservation(Ptr<Socket> socket) {
    const char* enabled = std::getenv("CS30401_BBR_OBSERVE");
    if (!enabled || std::string(enabled) != "1") return;
    const char* directory = std::getenv("CS30401_BBR_OBSERVE_DIR");
    NS_ABORT_MSG_IF(!directory, "CS30401_BBR_OBSERVE_DIR is required");
    if (!m_observeApp.is_open()) {
        m_observeApp.open(std::string(directory) + "/bbr_app_rx_node_" +
                         std::to_string(GetNode()->GetId()) + ".csv");
        NS_ABORT_MSG_IF(!m_observeApp.good(), "Cannot open app observation CSV");
        m_observeApp << "bin_start_ns,bin_end_ns,observed_until_ns,node_id,connection_id,flow_id,local_port,peer_port,app_bytes,connection_total_bytes,sink_total_bytes\n";
    }
    BbrConnection row;
    row.id = m_observeConnections.size();
    Address local, peer;
    socket->GetSockName(local);
    socket->GetPeerName(peer);
    if (InetSocketAddress::IsMatchingType(local)) row.localPort = InetSocketAddress::ConvertFrom(local).GetPort();
    if (InetSocketAddress::IsMatchingType(peer)) row.peerPort = InetSocketAddress::ConvertFrom(peer).GetPort();
    m_observeConnections[PeekPointer(socket)] = row;
    NS_ABORT_MSG_IF(!socket->TraceConnectWithoutContext("Rx",
        MakeCallback(&TcpFlowSink::ObserveBbrRx, this)), "Missing TCP Rx observer");
}
void TcpFlowSink::ObserveBbrRx(Ptr<const Packet> packet, const TcpHeader&,
                            Ptr<const TcpSocketBase> socket) {
    auto it = m_observeConnections.find(PeekPointer(socket));
    if (it == m_observeConnections.end()) return;
    TcpBbrObserveTag tag;
    if (packet->PeekPacketTag(tag)) {
        it->second.tagged = true;
        it->second.flow = tag.GetFlowId();
    }
}
void TcpFlowSink::RecordBbrApp(Ptr<Socket> socket, uint32_t bytes) {
    auto it = m_observeConnections.find(PeekPointer(socket));
    if (it == m_observeConnections.end()) return;
    auto& row = it->second;
    const int64_t bucket = Simulator::Now().GetNanoSeconds() / 100000000;
    if (row.bucket != bucket) {
        FlushBbrApp(row);
        row.bucket = bucket;
    }
    row.bytes += bytes;
    row.total += bytes;
    row.sinkTotal = m_totalRx;
}
void TcpFlowSink::FlushBbrApp(BbrConnection& row) {
    if (row.bucket < 0 || row.bytes == 0) return;
    m_observeApp << row.bucket * 100000000 << ',' << (row.bucket + 1) * 100000000
        << ',' << Simulator::Now().GetNanoSeconds() << ',' << GetNode()->GetId()
        << ',' << row.id << ',';
    if (row.tagged) m_observeApp << row.flow;
    m_observeApp << ',' << row.localPort << ',' << row.peerPort << ',' << row.bytes
                 << ',' << row.total << ',' << row.sinkTotal << '\n';
    row.bytes = 0;
}
void TcpFlowSink::FlushBbrApps() {
    for (auto& entry : m_observeConnections) FlushBbrApp(entry.second);
    if (m_observeApp.is_open()) m_observeApp.flush();
}
'''

NETWORK_HEADER = r'''#ifndef CS30401_BBR_ROUTE_OBSERVER_H
#define CS30401_BBR_ROUTE_OBSERVER_H
#include "ns3/ipv4-l3-protocol.h"
#include "ns3/ipv4-header.h"
#include "ns3/tcp-header.h"
#include "ns3/ppp-header.h"
#include "ns3/point-to-point-laser-net-device.h"
#include "ns3/gsl-net-device.h"
#include "ns3/point-to-point-net-device.h"
#include "ns3/tcp-flow-send-application.h"
#include "ns3/traffic-control-layer.h"
#include <cstdlib>
#include <fstream>
#include <map>
#include <memory>
#include <vector>
#include <algorithm>
#include <cstdint>

namespace ns3 { namespace bbrroute {
static std::unique_ptr<std::ofstream> drops, coverage, queues, pendingCsv;
struct Counters { uint64_t enq{0}, deq{0}, before{0}, after{0}, samples{0}, sum{0}, max{0}; };
struct Pending { int64_t time; uint64_t flow; };
struct QueueRecord {
    uint32_t node, device;
    Ptr<Queue<Packet>> queue;
    int64_t bucket{-1};
    std::map<uint64_t, Counters> counters;
    // Queue::DoEnqueue stores this same Ptr; DoDequeue traces the stored Ptr.
    // Fragments can share a UID, so UID is not a unique queue-entry identity.
    std::map<const Packet*, Pending> pending;
};
static std::vector<std::unique_ptr<QueueRecord>> records;
static uint64_t Flow(Ptr<const Packet> p) {
    TcpBbrObserveTag tag;
    return p->PeekPacketTag(tag) ? tag.GetFlowId() : UINT64_MAX;
}
static void FlushQueue(QueueRecord& r) {
    if (r.bucket < 0) return;
    for (const auto& entry : r.counters) {
        const auto& c = entry.second;
        *queues << r.bucket * 100000000 << ',' << (r.bucket + 1) * 100000000
                << ',' << r.node << ',' << r.device << ',';
        if (entry.first != UINT64_MAX) *queues << entry.first;
        *queues << ',' << c.enq << ',' << c.deq << ',' << c.before << ',' << c.after
                << ',' << c.samples << ',' << c.sum << ',' << c.max
                << ',' << Simulator::Now().GetNanoSeconds()
                << ',' << r.queue->GetNPackets() << ',' << r.queue->GetNBytes() << '\n';
    }
    r.counters.clear();
}
static Counters& At(QueueRecord* r, Ptr<const Packet> p) {
    const int64_t bucket = Simulator::Now().GetNanoSeconds() / 100000000;
    if (r->bucket != bucket) { FlushQueue(*r); r->bucket = bucket; }
    return r->counters[Flow(p)];
}
static void Enqueue(QueueRecord* r, Ptr<const Packet> p) {
    ++At(r,p).enq;
    const Packet* key = PeekPointer(p);
    NS_ABORT_MSG_IF(r->pending.count(key), "Same Packet object queued twice in one device queue");
    r->pending[key] = {Simulator::Now().GetNanoSeconds(), Flow(p)};
}
static void Dequeue(QueueRecord* r, Ptr<const Packet> p) {
    auto& c = At(r,p); ++c.deq;
    auto it = r->pending.find(PeekPointer(p));
    NS_ABORT_MSG_IF(it == r->pending.end(), "Dequeue without observed enqueue");
    NS_ABORT_MSG_IF(Flow(p) != it->second.flow, "Flow metadata changed inside device queue");
    const uint64_t wait = Simulator::Now().GetNanoSeconds() - it->second.time;
    ++c.samples; c.sum += wait; c.max = std::max(c.max, wait);
    r->pending.erase(it);
}
static void QueueBefore(QueueRecord* r, Ptr<const Packet> p) { ++At(r,p).before; }
static void QueueAfter(QueueRecord* r, Ptr<const Packet> p) {
    ++At(r,p).after;
    // Dequeue precedes DropAfterDequeue, so served-sojourn interpretation fails.
    NS_ABORT_MSG_IF(true,"DropAfterDequeue is outside served-sojourn observer semantics");
}
static void Drop(uint32_t node, uint32_t device, std::string layer,
                 Ptr<const Packet> p, const Ipv4Header* supplied=nullptr, int reason=-1) {
    auto copy = p->Copy();
    Ipv4Header ip;
    bool parsed = false;
    if (supplied) { ip = *supplied; parsed = true; }
    else if (copy->GetSize() >= 20) {
        uint8_t bytes[2]; copy->CopyData(bytes,2);
        if ((bytes[0] >> 4) != 4 && bytes[0] == 0 && bytes[1] == 0x21) {
            PppHeader ppp; copy->RemoveHeader(ppp);
        }
        copy->CopyData(bytes,1);
        if ((bytes[0] >> 4) == 4) parsed = copy->RemoveHeader(ip) > 0;
    }
    *drops << Simulator::Now().GetNanoSeconds() << ',' << node << ',' << device << ','
           << layer << ',' << reason << ',' << p->GetUid() << ',';
    const uint64_t flow = Flow(p);
    if (flow != UINT64_MAX) *drops << flow;
    *drops << ',';
    if (parsed) *drops << ip.GetSource() << ',' << ip.GetDestination(); else *drops << ',';
    *drops << ',';
    if (parsed && ip.GetProtocol() == 6 && ip.GetFragmentOffset() == 0 && copy->GetSize() >= 20) {
        TcpHeader tcp; copy->RemoveHeader(tcp);
        *drops << tcp.GetSourcePort() << ',' << tcp.GetDestinationPort() << ','
               << tcp.GetSequenceNumber().GetValue() << ',' << copy->GetSize();
    } else *drops << ",,,";
    *drops << '\n';
}
static void DeviceDrop(uint32_t node,uint32_t device,std::string layer,Ptr<const Packet> p) {
    Drop(node,device,layer,p);
}
static void IpDrop(uint32_t node,const Ipv4Header& ip,Ptr<const Packet> p,
                   Ipv4L3Protocol::DropReason reason,Ptr<Ipv4>,uint32_t interface) {
    Drop(node,interface,"ipv4",p,&ip,static_cast<int>(reason));
}
static void Finish() {
    const int64_t cutoff = Simulator::Now().GetNanoSeconds();
    for (auto& r : records) {
        FlushQueue(*r);
        NS_ABORT_MSG_IF(r->pending.size() != r->queue->GetNPackets(),
                        "Observed pending count differs from actual device queue");
        std::map<uint64_t, Counters> byFlow;
        for (const auto& item : r->pending) {
            auto& row = byFlow[item.second.flow];
            const uint64_t age = cutoff - item.second.time;
            ++row.samples; row.sum += age; row.max = std::max(row.max,age);
        }
        for (const auto& item : byFlow) {
            *pendingCsv << cutoff << ',' << r->node << ',' << r->device << ',';
            if (item.first != UINT64_MAX) *pendingCsv << item.first;
            *pendingCsv << ',' << item.second.samples << ',' << item.second.sum
                        << ',' << item.second.max << '\n';
        }
    }
    queues->flush(); drops->flush(); coverage->flush(); pendingCsv->flush();
}
static void Install(NodeContainer nodes) {
    const char* enabled = std::getenv("CS30401_BBR_OBSERVE");
    if (!enabled || std::string(enabled) != "1") return;
    const char* directory = std::getenv("CS30401_BBR_OBSERVE_DIR");
    NS_ABORT_MSG_IF(!directory, "Observation directory is required");
    drops = std::make_unique<std::ofstream>(std::string(directory)+"/bbr_drops.csv");
    coverage = std::make_unique<std::ofstream>(std::string(directory)+"/bbr_coverage.csv");
    queues = std::make_unique<std::ofstream>(std::string(directory)+"/bbr_queue_bins.csv");
    pendingCsv = std::make_unique<std::ofstream>(std::string(directory)+"/bbr_queue_pending.csv");
    NS_ABORT_MSG_IF(!drops->good() || !coverage->good() || !queues->good() || !pendingCsv->good(), "Cannot open network observers");
    *drops << "time_ns,node_id,device_id,layer,reason,packet_uid,flow_id,src,dst,src_port,dst_port,seq,payload_bytes\n";
    *coverage << "node_id,device_id,layer,connected\n";
    *queues << "bin_start_ns,bin_end_ns,node_id,device_id,flow_id,enqueued,dequeued,drop_before,drop_after,sojourn_samples,sojourn_sum_ns,sojourn_max_ns,flush_time_ns,queue_packets_at_flush,queue_bytes_at_flush\n";
    *pendingCsv << "cutoff_ns,node_id,device_id,flow_id,pending_packets,pending_age_sum_ns,max_pending_age_ns\n";
    for (auto it=nodes.Begin();it!=nodes.End();++it) {
        auto node=*it;
        auto ip=node->GetObject<Ipv4L3Protocol>();
        bool ok=ip && ip->TraceConnectWithoutContext("Drop",MakeBoundCallback(&IpDrop,node->GetId()));
        *coverage << node->GetId() << ",-1,ipv4," << ok << '\n';
        NS_ABORT_MSG_IF(!ok,"Missing IPv4 drop observer");
        auto tc=node->GetObject<TrafficControlLayer>();
        ok=tc && tc->TraceConnectWithoutContext("TcDrop",MakeBoundCallback(&DeviceDrop,node->GetId(),UINT32_MAX,std::string("TcDrop")));
        *coverage << node->GetId() << ",-1,TcDrop," << ok << '\n';
        NS_ABORT_MSG_IF(!ok,"Missing TcDrop observer");
        for (uint32_t i=0;i<node->GetNDevices();++i) {
            auto device=node->GetDevice(i);
            Ptr<Queue<Packet>> queue;
            if (auto isl=DynamicCast<PointToPointLaserNetDevice>(device)) queue=isl->GetQueue();
            else if (auto gsl=DynamicCast<GSLNetDevice>(device)) queue=gsl->GetQueue();
            else if (auto p2p=DynamicCast<PointToPointNetDevice>(device)) queue=p2p->GetQueue();
            else continue;
            NS_ABORT_MSG_IF(!queue,"Missing device queue");
            ok=!tc->GetRootQueueDiscOnDevice(device);
            *coverage << node->GetId() << ',' << i << ",root_queue_disc_absent," << ok << '\n';
            NS_ABORT_MSG_IF(!ok,"Root QueueDisc is outside this observer's coverage");
            auto r=std::make_unique<QueueRecord>(); r->node=node->GetId(); r->device=i; r->queue=queue;
            for (const std::string layer : {"MacTxDrop","PhyTxDrop","PhyRxDrop"}) {
                ok=device->TraceConnectWithoutContext(layer,MakeBoundCallback(&DeviceDrop,node->GetId(),i,layer));
                *coverage << node->GetId() << ',' << i << ',' << layer << ',' << ok << '\n';
                NS_ABORT_MSG_IF(!ok,"Missing device drop observer");
            }
            for (const auto& hook : std::vector<std::pair<std::string,Callback<void,Ptr<const Packet>>>>{
                {"Enqueue",MakeBoundCallback(&Enqueue,r.get())},
                {"Dequeue",MakeBoundCallback(&Dequeue,r.get())},
                {"DropBeforeEnqueue",MakeBoundCallback(&QueueBefore,r.get())},
                {"DropAfterDequeue",MakeBoundCallback(&QueueAfter,r.get())}}) {
                ok=queue->TraceConnectWithoutContext(hook.first,hook.second);
                *coverage << node->GetId() << ',' << i << ',' << hook.first << ',' << ok << '\n';
                NS_ABORT_MSG_IF(!ok,"Missing queue observer");
            }
            // Also preserve sparse, attributable drop records at the device queue layer.
            for (const std::string layer : {"DropBeforeEnqueue","DropAfterDequeue"})
                NS_ABORT_MSG_IF(!queue->TraceConnectWithoutContext(layer,MakeBoundCallback(&DeviceDrop,node->GetId(),i,layer)),"Missing queue drop observer");
            records.push_back(std::move(r));
        }
    }
    coverage->flush();
    Simulator::ScheduleDestroy(&Finish);
}
}} // ns3::bbrroute
#endif
'''


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one unmodified anchor: {old[:100]!r}")
    return text.replace(old, new)


def transformed(root):
    result = {}
    def read(rel):
        return (root / rel).read_text()
    rel = 'src/internet/model/tcp-bbr.h'
    text = replace(read(rel), '    static TypeId GetTypeId();', '    static TypeId GetTypeId();\n    void SetObservationFlow(uint64_t flowId);')
    text = replace(text, '  private:\n    BbrMode_t m_state', '''  private:
    void ObserveAck(Ptr<TcpSocketState> tcb, const TcpRateOps::TcpRateSample& rs);
    bool m_observeEnabled{false};
    uint64_t m_observeFlow{0}, m_observeAcks{0}, m_observeAcked{0}, m_observeLost{0};
    int64_t m_observeBucket{-1};
    int m_observeState{-1};
    double m_observeGain{-1};
    BbrMode_t m_state''')
    result[rel] = text
    rel = 'src/internet/model/tcp-bbr.cc'
    text = replace(read(rel), '#include "tcp-bbr.h"', '#include "tcp-bbr.h"\n#include <cstdlib>\n#include <fstream>\n#include <memory>')
    text = replace(text, '    UpdateControlParameters(tcb, rs);\n}', '    UpdateControlParameters(tcb, rs);\n    ObserveAck(tcb, rs);\n}')
    result[rel] = replace(text, '} // namespace ns3', BBR_METHODS + '\n} // namespace ns3')
    rel = 'contrib/basic-sim/model/apps/tcp-flow-send-application.h'
    text = replace(read(rel), '#include "ns3/traced-callback.h"', '#include "ns3/traced-callback.h"\n#include "ns3/tag.h"')
    text = replace(text, 'class TcpFlowSendApplication : public Application', 'class TcpHeader;\nclass TcpSocketBase;\n' + TAG_DECL + '\nclass TcpFlowSendApplication : public Application')
    result[rel] = replace(text, '  void ConnectionSucceeded (Ptr<Socket> socket);', '''  void InitializeBbrObservation();
  void ObserveBbrTx(Ptr<const Packet> packet, const TcpHeader& header, Ptr<const TcpSocketBase> socket);
  void ConnectionSucceeded (Ptr<Socket> socket);''')
    rel = 'contrib/basic-sim/model/apps/tcp-flow-send-application.cc'
    text = replace(read(rel), '#include <fstream>', '#include <fstream>\n#include <cstdlib>\n#include "ns3/tcp-bbr.h"\n#include "ns3/pointer.h"')
    text = replace(text, '        // Connect, no receiver', '        InitializeBbrObservation();\n\n        // Connect, no receiver')
    result[rel] = replace(text, 'NS_OBJECT_ENSURE_REGISTERED (TcpFlowSendApplication);', 'NS_OBJECT_ENSURE_REGISTERED (TcpFlowSendApplication);\n' + TAG_METHODS)
    rel = 'contrib/basic-sim/model/apps/tcp-flow-sink.h'
    text = replace(read(rel), '#include "ns3/address.h"', '#include "ns3/address.h"\n#include <fstream>\n#include <map>')
    text = replace(text, 'class Packet;', 'class Packet;\nclass TcpHeader;\nclass TcpSocketBase;')
    result[rel] = replace(text, '  void HandleRead (Ptr<Socket> socket);', '''  struct BbrConnection {
    uint64_t id{0}, flow{0}, bytes{0}, total{0}, sinkTotal{0};
    int64_t bucket{-1};
    uint16_t localPort{0}, peerPort{0};
    bool tagged{false};
  };
  std::map<const Socket*, BbrConnection> m_observeConnections;
  std::ofstream m_observeApp;
  void StartBbrObservation(Ptr<Socket> socket);
  void ObserveBbrRx(Ptr<const Packet>, const TcpHeader&, Ptr<const TcpSocketBase>);
  void RecordBbrApp(Ptr<Socket> socket, uint32_t bytes);
  void FlushBbrApp(BbrConnection& row);
  void FlushBbrApps();
  void HandleRead (Ptr<Socket> socket);''')
    rel = 'contrib/basic-sim/model/apps/tcp-flow-sink.cc'
    text = replace(read(rel), '#include "tcp-flow-sink.h"', '#include "tcp-flow-sink.h"\n#include "tcp-flow-send-application.h"\n#include "ns3/tcp-socket-base.h"\n#include "ns3/tcp-header.h"\n#include <cstdlib>')
    for anchor in ['TcpFlowSink::~TcpFlowSink() {', 'void TcpFlowSink::DoDispose(void) {', 'void TcpFlowSink::StopApplication() {  // Called at time specified by Stop']:
        text = replace(text, anchor, anchor + '\n    FlushBbrApps();')
    text = replace(text, 'void TcpFlowSink::HandleAccept(Ptr<Socket> socket, const Address &from) {', 'void TcpFlowSink::HandleAccept(Ptr<Socket> socket, const Address &from) {\n    StartBbrObservation(socket);')
    text = replace(text, '        m_totalRx += packet->GetSize ();', '        m_totalRx += packet->GetSize ();\n        RecordBbrApp(socket, packet->GetSize());')
    result[rel] = replace(text, '} // Namespace ns3', SINK_METHODS + '\n} // Namespace ns3')
    rel = 'scratch/main_satnet/main_satnet.cc'
    text = replace(read(rel), '#include "ns3/gsl-if-bandwidth-helper.h"', '#include "ns3/gsl-if-bandwidth-helper.h"\n#include "bbr_route_observer.h"')
    result[rel] = replace(text, '    // Schedule flows', '    bbrroute::Install(topology->GetNodes());\n\n    // Schedule flows')
    rel = 'scratch/main_satnet/bbr_route_observer.h'
    if (root / rel).exists():
        raise ValueError('Observer header already exists; refusing to overwrite')
    result[rel] = NETWORK_HEADER
    return result


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def install(args):
    root = args.ns3_root.resolve()
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
    if status.strip():
        raise ValueError('Apply only to a clean official ns-3 checkout')
    if args.patch.exists():
        raise ValueError('Refusing to overwrite an existing exported patch')
    outputs = transformed(root)  # Validate all anchors before changing any source.
    before = {rel: sha(root / rel) for rel in outputs if (root / rel).exists()}
    for rel, text in outputs.items():
        (root / rel).write_text(text, newline='\n')
    subprocess.run(['git', 'add', '-N', 'scratch/main_satnet/bbr_route_observer.h'], cwd=root, check=True)
    patch = subprocess.check_output(['git', 'diff', '--binary', '--', *sorted(outputs)], cwd=root)
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    args.patch.write_bytes(patch)
    print(json.dumps({'patch': str(args.patch), 'patch_sha256': sha(args.patch),
                      'files': sorted(outputs), 'original_sources': before,
                      'after_sources': {rel: sha(root / rel) for rel in outputs}}, indent=2))


def checked_manifest(run, state_root):
    """Validate completion and all preserved outputs before comparing measurements."""
    record = json.loads((run / 'manifest.json').read_text())
    if record.get('status') != 'success' or type(record.get('returncode')) is not int or record['returncode'] != 0:
        raise ValueError(f'Run did not complete successfully: {run}')
    definition, environment = record.get('definition'), record.get('environment')
    if not isinstance(definition, dict) or not isinstance(environment, dict):
        raise ValueError(f'Missing definition/environment: {run}')
    observe = environment.get('CS30401_BBR_OBSERVE')
    if observe not in ('0', '1') or type(definition.get('observe')) is not bool or definition['observe'] != (observe == '1'):
        raise ValueError(f'Observation flag disagrees with definition: {run}')
    for name, key in [('config_ns3.properties', 'config_sha256'), ('schedule.csv', 'schedule_sha256')]:
        if sha(run / name) != record.get(key):
            raise ValueError(f'Actual input differs from launch receipt: {run / name}')
    state = record.get('state_static_sha256')
    if not isinstance(state, dict) or not state:
        raise ValueError(f'Missing static-state receipt: {run}')
    for name, digest in state.items():
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError(f'Invalid static-state member: {name!r}')
        if sha(state_root / name) != digest:
            raise ValueError(f'Actual static state differs from receipt: {name}')
    outputs = record.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError(f'Missing output receipt: {run}')
    actual_set = {p.relative_to(run).as_posix() for p in (run / 'logs_ns3').iterdir() if p.is_file()}
    if set(outputs) != actual_set:
        raise ValueError(f'Output file set differs from manifest: {run}')
    for relative, item in outputs.items():
        path = run / relative
        if path.is_symlink() or not path.resolve().is_relative_to(run):
            raise ValueError(f'Output escapes run or uses symlink: {relative}')
        if not isinstance(item, dict) or type(item.get('bytes')) is not int or path.stat().st_size != item['bytes'] or sha(path) != item.get('sha256'):
            raise ValueError(f'Actual output differs from manifest: {path}')
    return record


def compare(args):
    if args.out.exists():
        raise ValueError('Refusing to overwrite an equivalence result')
    reference, observed = args.reference.resolve(), args.observed.resolve()
    if reference == observed:
        raise ValueError('Reference and observed directories must be distinct')
    state_root = args.state_root.resolve()
    left_record = checked_manifest(reference, state_root)
    right_record = checked_manifest(observed, state_root)
    expected_fields = ['config_sha256', 'schedule_sha256', 'state_static_sha256',
                       'sim_seconds', 'rate_mbps', 'queue_packets', 'seed']
    for key in expected_fields:
        if key not in left_record or key not in right_record or left_record[key] != right_record[key]:
            raise ValueError(f'Matched-condition input differs: {key}')
    left_definition = {k: v for k, v in left_record['definition'].items() if k not in ('reference', 'observe')}
    right_definition = {k: v for k, v in right_record['definition'].items() if k not in ('reference', 'observe')}
    if left_definition != right_definition:
        raise ValueError('Flow/traffic definitions differ')
    for record, expected, label in [(left_record, args.reference_observe, 'reference'),
                                    (right_record, args.observed_observe, 'observed')]:
        if expected is not None and record['environment']['CS30401_BBR_OBSERVE'] != expected:
            raise ValueError(f'{label} observation flag differs from requested flag')
    if left_record.get('image_digest') and right_record.get('image_digest') and left_record['image_digest'] != right_record['image_digest']:
        raise ValueError('Declared image digests differ')
    def measurement_names(run):
        return {p.name for p in (run / 'logs_ns3').glob('*.csv')
                if p.name != 'timing_results.csv' and not p.name.startswith('bbr_')}
    paths = measurement_names(reference)
    if not paths or paths != measurement_names(observed):
        raise ValueError('Existing measurement CSV sets are empty or differ')
    checks = []
    for name in sorted(paths):
        left, right = reference / 'logs_ns3' / name, observed / 'logs_ns3' / name
        checks.append({'file': name, 'reference_sha256': sha(left),
                       'observed_sha256': sha(right), 'equal': left.stat().st_size == right.stat().st_size
                       and sha(left) == sha(right)})
    supplemental = None
    if args.state_receipt is not None:
        receipt = args.state_receipt.resolve()
        if not isinstance(json.loads(receipt.read_text()), dict):
            raise ValueError('Supplemental state receipt must contain a JSON object')
        supplemental = {'path': str(receipt), 'bytes': receipt.stat().st_size, 'sha256': sha(receipt)}
    record = {'status': 'PASS' if all(c['equal'] for c in checks) else 'FAIL',
              'reference': str(reference), 'observed': str(observed), 'checks': checks,
              'matched_fields': expected_fields, 'flow_definitions_equal': True,
              'all_manifest_output_hashes_match_actual': True,
              'reference_observe': left_record['environment']['CS30401_BBR_OBSERVE'],
              'observed_observe': right_record['environment']['CS30401_BBR_OBSERVE'],
              'manifest_sha256': {'reference': sha(reference / 'manifest.json'), 'observed': sha(observed / 'manifest.json')},
              'provenance': {label: {key: source.get(key) for key in ['repo_commit', 'runner_sha256',
                    'effective_build_diff_sha256', 'observer_patch_sha256', 'image_digest', 'runtime_files']}
                    for label, source in [('reference', left_record), ('observed', right_record)]},
              'state_static_verified_against_actual': True, 'state_root': str(state_root),
              'supplemental_state_receipt': supplemental,
              'measurement_csv_count': len(checks), 'helper_sha256': sha(Path(__file__)),
              'limits': ['One matched condition only; not proof of global behavior equivalence.',
                         'Timing CSV, console output and new observer files are excluded from equality; manifest output hashes are checked for every output.',
                         'Static state receipt does not by itself validate every dynamic forwarding file; supplemental receipt identity is linked, not re-audited.',
                         'Source/binary/library provenance can differ after instrumentation; each launch identity is retained.']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + '\n', newline='\n')
    print(json.dumps(record, indent=2))
    if record['status'] != 'PASS':
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    apply = sub.add_parser('install', help='Apply passive observers to a clean ns-3 tree and export a patch')
    apply.add_argument('--ns3-root', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    apply.add_argument('--patch', type=Path, required=True)
    diff = sub.add_parser('compare', help='Byte-compare original measurement CSVs from two matched runs')
    diff.add_argument('--reference', type=Path, required=True)
    diff.add_argument('--observed', type=Path, required=True)
    diff.add_argument('--out', type=Path, required=True)
    diff.add_argument('--state-root', type=Path, default=Path('/home/ubuntu/lab/data/seoul_london/state'))
    diff.add_argument('--state-receipt', type=Path, help='Link an independently verified full-state JSON receipt by SHA; does not re-audit it')
    diff.add_argument('--reference-observe', choices=['0', '1'], help='Require the recorded reference observer flag')
    diff.add_argument('--observed-observe', choices=['0', '1'], help='Require the recorded observed observer flag')
    args = parser.parse_args()
    (install if args.command == 'install' else compare)(args)


if __name__ == '__main__':
    main()
