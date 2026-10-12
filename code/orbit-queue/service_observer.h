#ifndef CS30401_ORBIT_QUEUE_SERVICE_H
#define CS30401_ORBIT_QUEUE_SERVICE_H
#include "queue_observer.h"
namespace ns3 { namespace orbitqueueservice {
struct Count {uint64_t busy{0}, packets{0}, bytes{0};};
struct Record {
    uint32_t node,device;
    Ptr<const Packet> active;
    int64_t start{-1};
    uint64_t flow{UINT64_MAX};
    std::map<std::pair<int64_t,uint64_t>,Count> bins;
};
static std::vector<std::unique_ptr<Record>> records;
static std::unique_ptr<std::ofstream> output,coverage;
static uint64_t Flow(Ptr<const Packet> p) {TcpStudyTxTag t;return p->PeekPacketTag(t)?t.GetFlowId():UINT64_MAX;}
static void AddBusy(Record& r,int64_t end) {
    NS_ABORT_MSG_IF(end<r.start,"Service time decreases");
    for (int64_t t=r.start;t<end;) {
        const int64_t bucket=t/100000000;
        const int64_t next=std::min(end,(bucket+1)*100000000);
        r.bins[{bucket,r.flow}].busy+=next-t;t=next;
    }
}
static void Begin(Record* r,Ptr<const Packet> p) {
    NS_ABORT_MSG_IF(r->active,"Overlapping transmission on one device");
    r->active=p;r->start=Simulator::Now().GetNanoSeconds();r->flow=Flow(p);
    auto& c=r->bins[{r->start/100000000,r->flow}];++c.packets;c.bytes+=p->GetSize();
}
static void End(Record* r,Ptr<const Packet> p) {
    NS_ABORT_MSG_IF(!r->active || PeekPointer(r->active)!=PeekPointer(p),"Service end packet differs from begin");
    NS_ABORT_MSG_IF(Flow(p)!=r->flow,"Flow changed during serialization");
    AddBusy(*r,Simulator::Now().GetNanoSeconds());r->active=nullptr;r->start=-1;
}
static void Finish() {
    const int64_t cutoff=Simulator::Now().GetNanoSeconds();
    for (auto& r:records) {
        if (r->active) AddBusy(*r,cutoff);
        for (const auto& e:r->bins) {
            const auto& c=e.second;
            *output << e.first.first*100000000 << ',' << (e.first.first+1)*100000000
                    << ',' << r->node << ',' << r->device << ',';
            if (e.first.second!=UINT64_MAX) *output << e.first.second;
            *output << ',' << c.busy << ',' << c.packets << ',' << c.bytes
                    << ',' << cutoff << ',' << bool(r->active) << '\n';
        }
    }
    output->flush();coverage->flush();
}
static void Install(NodeContainer nodes) {
    const char* enabled=std::getenv("CS30401_ORBIT_SERVICE_TRACE");
    if (!enabled || std::string(enabled)!="1") return;
    const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");
    NS_ABORT_MSG_IF(!directory,"Missing service directory");
    output=std::make_unique<std::ofstream>(std::string(directory)+"/orbit_service_bins.csv");
    coverage=std::make_unique<std::ofstream>(std::string(directory)+"/orbit_service_coverage.csv");
    NS_ABORT_MSG_IF(!output->good() || !coverage->good(),"Cannot create service trace");
    *output << "bin_start_ns,bin_end_ns,node_id,device_id,flow_id,busy_ns,tx_packets,serialized_bytes_started,cutoff_ns,device_tx_active_at_cutoff\n";
    *coverage << "node_id,device_id,hook,connected\n";
    for (auto it=nodes.Begin();it!=nodes.End();++it) {
        auto node=*it;
        for (uint32_t i=0;i<node->GetNDevices();++i) {
            auto dev=node->GetDevice(i);
            if (!DynamicCast<GSLNetDevice>(dev) && !DynamicCast<PointToPointLaserNetDevice>(dev) && !DynamicCast<PointToPointNetDevice>(dev)) continue;
            auto r=std::make_unique<Record>();r->node=node->GetId();r->device=i;
            bool ok=dev->TraceConnectWithoutContext("PhyTxBegin",MakeBoundCallback(&Begin,r.get()));
            *coverage << node->GetId() << ',' << i << ",PhyTxBegin," << ok << '\n';
            NS_ABORT_MSG_IF(!ok,"Missing PhyTxBegin");
            ok=dev->TraceConnectWithoutContext("PhyTxEnd",MakeBoundCallback(&End,r.get()));
            *coverage << node->GetId() << ',' << i << ",PhyTxEnd," << ok << '\n';
            NS_ABORT_MSG_IF(!ok,"Missing PhyTxEnd");records.push_back(std::move(r));
        }
    }
    Simulator::ScheduleDestroy(&Finish);
}
}}
#endif
