#ifndef ORBIT_QUEUE_FLOW_OBSERVER_H
#define ORBIT_QUEUE_FLOW_OBSERVER_H
#include "queue_observer.h"
#include "ns3/net-device-queue-interface.h"
#include "ns3/queue-limits.h"
#include "ns3/queue-disc.h"
namespace ns3 { namespace orbitqueueflow {
static std::unique_ptr<std::ofstream> states, mappedDrops, devices;
static std::map<std::pair<uint32_t,uint32_t>,orbitqueue::QueueRecord*> mapping;
static std::string LimitsType(NetDeviceQueue* q) {
    auto limits=q->GetQueueLimits();
    return limits ? limits->GetInstanceTypeId().GetName() : "none";
}
static void State(orbitqueue::QueueRecord* r,NetDevice* device,uint32_t txq,
                  NetDeviceQueue* q,std::string reason,bool oldDevice,bool oldLimits,
                  bool newDevice,bool newLimits,bool wakeWillRun) {
    *states << Simulator::Now().GetNanoSeconds() << ',' << r->node << ',' << r->device
        << ',' << txq << ',' << reason << ',' << oldDevice << ',' << oldLimits
        << ',' << newDevice << ',' << newLimits << ',' << (newDevice||newLimits)
        << ',' << wakeWillRun << ',' << r->queue->GetNPackets() << ',' << r->queue->GetNBytes()
        << ',' << r->queue->GetMaxSize() << ',' << r->queue->WouldOverflow(1,device->GetMtu())
        << ',' << LimitsType(q) << '\n';
}
static void TcDrop(uint32_t node,Ptr<NetDevice> device,uint32_t txq,Ptr<const Packet> p,
                   bool deviceStop,bool limitsStop) {
    auto record=mapping.find({node,device->GetIfIndex()});
    auto ndqi=device->GetObject<NetDeviceQueueInterface>();
    TcpStudyTxTag tag;const bool tagged=p->PeekPacketTag(tag);
    auto copy=p->Copy();Ipv4Header ip;TcpHeader tcp;
    bool parsed=copy->GetSize()>=20 && copy->RemoveHeader(ip)>0 && ip.GetProtocol()==6 &&
                ip.GetFragmentOffset()==0 && copy->GetSize()>=20 && copy->RemoveHeader(tcp)>0;
    *mappedDrops << Simulator::Now().GetNanoSeconds() << ',' << node << ','
        << device->GetIfIndex() << ',' << txq << ',' << device->GetInstanceTypeId().GetName()
        << ',' << p->GetUid() << ',';
    if(tagged) *mappedDrops << tag.GetFlowId();
    *mappedDrops << ',';if(tagged) *mappedDrops << tag.GetTxId();
    *mappedDrops << ',';if(tagged) *mappedDrops << tag.GetTxTimeNs();
    *mappedDrops << ',';if(parsed) *mappedDrops << tcp.GetSequenceNumber().GetValue();
    *mappedDrops << ',';if(parsed) *mappedDrops << copy->GetSize();
    *mappedDrops << ',' << deviceStop << ',' << limitsStop << ',' << (deviceStop||limitsStop)
        << ',' << (record!=mapping.end());
    if(record!=mapping.end()) {
        auto queue=record->second->queue;
        *mappedDrops << ',' << queue->GetNPackets() << ',' << queue->GetNBytes()
            << ',' << queue->GetMaxSize() << ',' << queue->WouldOverflow(1,device->GetMtu());
    } else *mappedDrops << ",,,,";
    *mappedDrops << ',' << (ndqi ? LimitsType(PeekPointer(ndqi->GetTxQueue(txq))) : "no-interface") << '\n';
}
static void Finish() {states->flush();mappedDrops->flush();devices->flush();}
static void Install(NodeContainer nodes) {
    const char* enabled=std::getenv("CS30401_QUEUE_FLOW_TRACE");
    if(!enabled || std::string(enabled)!="1") return;
    const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");
    NS_ABORT_MSG_IF(!directory,"Missing flow-control observation directory");
    states=std::make_unique<std::ofstream>(std::string(directory)+"/queue_flow_state.csv");
    mappedDrops=std::make_unique<std::ofstream>(std::string(directory)+"/queue_tc_drop.csv");
    devices=std::make_unique<std::ofstream>(std::string(directory)+"/queue_devices.csv");
    NS_ABORT_MSG_IF(!states->good() || !mappedDrops->good() || !devices->good(),"Cannot open flow-control observers");
    *states << "time_ns,node_id,device_id,txq,reason,old_device_stop,old_bql_stop,new_device_stop,new_bql_stop,is_stopped,wake_callback_will_run,queue_packets,queue_bytes,max_size,would_overflow_one_mtu,queue_limits_type\n";
    *mappedDrops << "time_ns,node_id,device_id,txq,device_type,packet_uid,flow_id,tx_id,tx_time_ns,seq,payload_bytes,device_stop,bql_stop,is_stopped,queue_mapped,queue_packets,queue_bytes,max_size,would_overflow_one_mtu,queue_limits_type\n";
    *devices << "node_id,device_id,if_index,device_type,queue_type,max_size,txq,queue_limits_type,root_qdisc_type\n";
    for(auto& item:orbitqueue::records) {
        auto r=item.get();auto node=nodes.Get(r->node);auto device=node->GetDevice(r->device);
        NS_ABORT_MSG_IF(device->GetIfIndex()!=r->device,"Node device index differs from interface identity");
        mapping[{r->node,r->device}]=r;
        auto tc=node->GetObject<TrafficControlLayer>();
        auto root=tc->GetRootQueueDiscOnDevice(device);
        auto ndqi=device->GetObject<NetDeviceQueueInterface>();
        NS_ABORT_MSG_IF(!ndqi,"Missing device queue interface");
        for(uint32_t txq=0;txq<ndqi->GetNTxQueues();++txq) {
            auto q=ndqi->GetTxQueue(txq);
            // Raw self/device pointers avoid an observer reference cycle. The
            // callback runs inside this queue's live state-changing method.
            q->SetOrbitObserver(MakeBoundCallback(&State,r,PeekPointer(device),txq,PeekPointer(q)));
            *devices << r->node << ',' << r->device << ',' << device->GetIfIndex()
                << ',' << device->GetInstanceTypeId().GetName() << ',' << r->queue->GetInstanceTypeId().GetName()
                << ',' << r->queue->GetMaxSize() << ',' << txq << ',' << LimitsType(PeekPointer(q))
                << ',' << (root ? root->GetInstanceTypeId().GetName() : "none") << '\n';
        }
    }
    for(auto it=nodes.Begin();it!=nodes.End();++it) {
        auto node=*it;auto tc=node->GetObject<TrafficControlLayer>();
        NS_ABORT_MSG_IF(!tc,"Missing TrafficControlLayer");
        tc->SetOrbitDropObserver(MakeBoundCallback(&TcDrop,node->GetId()));
    }
    devices->flush();Simulator::ScheduleDestroy(&Finish);
}
}}
#endif
