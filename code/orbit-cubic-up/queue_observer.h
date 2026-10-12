#ifndef CS30401_ORBIT_CUBIC_QUEUE_OBSERVER_H
#define CS30401_ORBIT_CUBIC_QUEUE_OBSERVER_H
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

namespace ns3 { namespace orbitcubicqueue {
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
    TcpStudyTxTag tag;
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
    const char* enabled = std::getenv("CS30401_ORBIT_QUEUE_TRACE");
    if (!enabled || std::string(enabled) != "1") return;
    const char* directory = std::getenv("CS30401_ORBIT_QUEUE_TRACE_DIR");
    NS_ABORT_MSG_IF(!directory, "Observation directory is required");
    drops = std::make_unique<std::ofstream>(std::string(directory)+"/orbit_drops.csv");
    coverage = std::make_unique<std::ofstream>(std::string(directory)+"/orbit_coverage.csv");
    queues = std::make_unique<std::ofstream>(std::string(directory)+"/orbit_queue_bins.csv");
    pendingCsv = std::make_unique<std::ofstream>(std::string(directory)+"/orbit_queue_pending.csv");
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
}} // ns3::orbitcubicqueue
#endif
