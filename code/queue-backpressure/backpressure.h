#ifndef CS30401_QUEUE_BACKPRESSURE_H
#define CS30401_QUEUE_BACKPRESSURE_H
#include "queue_observer.h"
#include "ns3/traffic-control-helper.h"
#include "ns3/ipv4-queue-disc-item.h"
#include "ns3/error-model.h"
#include "ns3/pointer.h"
#include "ns3/net-device-queue-interface.h"
#include "ns3/boolean.h"
#include "ns3/uinteger.h"
#include <set>

namespace ns3 { namespace backpressure {
struct Identity {bool tagged{false};uint64_t flow{0},tx{0},txTime{0},uid{0};uint32_t seq{0},payload{0};};
struct Entry {uint64_t visit;int64_t ingress,qdEnq{-1},qdDeq{-1},devEnq{-1},devDeq{-1};Identity id;Ptr<const Packet> packet;};
struct Area {uint64_t packetNs{0},byteNs{0},qdPacketNs{0},devPacketNs{0},rqPacketNs{0},activeNs{0},changes{0};uint32_t peak{0},qdPeak{0},devPeak{0},rqPeak{0};};
static Ptr<GSLNetDevice> device;
static Ptr<Queue<Packet>> queue;
static Ptr<QueueDisc> disc;
static Ptr<NetDeviceQueueInterface> ndqi;
static std::string mode;
static std::map<const Packet*,Entry> entries;
static std::map<int64_t,Area> areas;
static uint64_t arrivals{0},served{0},dropped{0},nextVisit{0},requeues{0};
static int64_t stateTime{0};
static uint32_t qdPackets{0},devPackets{0},rqPackets{0};
static uint64_t qdBytes{0},devBytes{0},rqBytes{0};
static bool active{false},verified{false},physicalDropEnabled{false},physicalDropFired{false},firstReady{false};
static Identity firstOriginal;
static std::unique_ptr<std::ofstream> visits,drops,states,summary,config,receiverDrop;

static Identity ReadItem(Ptr<const QueueDiscItem> item) {
    Identity id;auto packet=item->GetPacket();id.uid=packet->GetUid();TcpStudyTxTag tag;
    id.tagged=packet->PeekPacketTag(tag);
    if(id.tagged){id.flow=tag.GetFlowId();id.tx=tag.GetTxId();id.txTime=tag.GetTxTimeNs();}
    auto ip=DynamicCast<const Ipv4QueueDiscItem>(item);
    if(ip && ip->GetHeader().GetProtocol()==6 && ip->GetHeader().GetFragmentOffset()==0) {
        auto copy=packet->Copy();TcpHeader tcp;
        if(copy->GetSize()>=20 && copy->RemoveHeader(tcp)>0){id.seq=tcp.GetSequenceNumber().GetValue();id.payload=copy->GetSize();}
    }
    return id;
}
static void Fields(std::ostream& out,const Identity& id) {
    out << id.uid << ',' << id.tagged << ',';
    if(id.tagged)out << id.flow;out << ',';if(id.tagged)out << id.tx;
    out << ',';if(id.tagged)out << id.txTime;
    out << ',' << id.seq << ',' << id.payload;
}
static void Integrate(int64_t now) {
    NS_ABORT_MSG_IF(now<stateTime,"Combined state time decreases");
    if(qdPackets || devPackets || rqPackets || active) {
        for(int64_t t=stateTime;t<now;) {
            const int64_t bucket=t/100000000,end=std::min(now,(bucket+1)*100000000);
            auto& a=areas[bucket];const uint64_t dt=end-t;
            a.packetNs+=uint64_t(qdPackets+devPackets+rqPackets)*dt;
            a.byteNs+=(qdBytes+devBytes+rqBytes)*dt;
            a.qdPacketNs+=uint64_t(qdPackets)*dt;a.devPacketNs+=uint64_t(devPackets)*dt;
            a.rqPacketNs+=uint64_t(rqPackets)*dt;a.activeNs+=uint64_t(active)*dt;
            a.peak=std::max(a.peak,qdPackets+devPackets+rqPackets);
            a.qdPeak=std::max(a.qdPeak,qdPackets);a.devPeak=std::max(a.devPeak,devPackets);a.rqPeak=std::max(a.rqPeak,rqPackets);t=end;
        }
    }
    stateTime=now;
}
static void Sync() {
    const int64_t now=Simulator::Now().GetNanoSeconds();Integrate(now);
    qdPackets=disc?disc->GetNPackets():0;qdBytes=disc?disc->GetNBytes():0;
    rqPackets=disc?disc->GetBackpressureRequeuedPackets():0;rqBytes=disc?disc->GetBackpressureRequeuedBytes():0;
    devPackets=queue->GetNPackets();devBytes=queue->GetNBytes();
    auto& a=areas[now/100000000];++a.changes;
    a.peak=std::max(a.peak,qdPackets+devPackets+rqPackets);
    a.qdPeak=std::max(a.qdPeak,qdPackets);a.devPeak=std::max(a.devPeak,devPackets);a.rqPeak=std::max(a.rqPeak,rqPackets);
}
static void Change(uint32_t,uint32_t){Sync();}
static void Verify() {
    if(verified)return;verified=true;
    NS_ABORT_MSG_IF(ndqi->GetNTxQueues()!=1,"Expected native single transmit queue");
    const bool wake=ndqi->GetTxQueue(0)->HasOrbitWakeCallback();
    NS_ABORT_MSG_IF(bool(disc)!=wake,"Native root/wake initialization mismatch");
    if(disc)NS_ABORT_MSG_IF(disc->GetNInternalQueues()!=1 || disc->GetInternalQueue(0)->GetMaxSize()!=QueueSize("96p"),"Unexpected internal queue size");
    *config << mode << ",1584,1,0," << queue->GetMaxSize() << ',' << (disc?disc->GetInstanceTypeId().GetName():"none")
        << ',' << (disc?disc->GetMaxSize():QueueSize("0p")) << ',' << wake << ',' << physicalDropEnabled << '\n';config->flush();
}
static void Ingress(Ptr<NetDevice> target,uint32_t txq,Ptr<const QueueDiscItem> item) {
    if(target!=device)return;Verify();NS_ABORT_MSG_IF(txq!=0,"Unexpected source transmit queue");
    auto packet=item->GetPacket();const auto key=PeekPointer(packet);
    NS_ABORT_MSG_IF(entries.count(key),"Same source Packet object entered twice");
    const auto id=ReadItem(item);entries.emplace(key,Entry{++nextVisit,Simulator::Now().GetNanoSeconds(),-1,-1,-1,-1,id,packet});++arrivals;
    if(!firstReady && id.tagged && id.flow==0 && id.seq==1 && id.payload>0){firstOriginal=id;firstReady=true;}
}
static Entry& Find(Ptr<const Packet> packet) {
    auto it=entries.find(PeekPointer(packet));NS_ABORT_MSG_IF(it==entries.end(),"Source event without ingress");
    TcpStudyTxTag tag;const bool tagged=packet->PeekPacketTag(tag);
    NS_ABORT_MSG_IF(tagged!=it->second.id.tagged || (tagged && (tag.GetFlowId()!=it->second.id.flow || tag.GetTxId()!=it->second.id.tx || tag.GetTxTimeNs()!=it->second.id.txTime)),"Source transmission tag changed");
    return it->second;
}
static void DeviceEnqueue(Ptr<const Packet> packet){auto& e=Find(packet);e.devEnq=Simulator::Now().GetNanoSeconds();Sync();}
static void DeviceDequeue(Ptr<const Packet> packet){auto& e=Find(packet);e.devDeq=Simulator::Now().GetNanoSeconds();Sync();}
static void QdEnqueue(Ptr<const QueueDiscItem> item){Find(item->GetPacket()).qdEnq=Simulator::Now().GetNanoSeconds();Sync();}
static void QdDequeue(Ptr<const QueueDiscItem> item){Find(item->GetPacket()).qdDeq=Simulator::Now().GetNanoSeconds();Sync();}
static void Requeue(Ptr<const QueueDiscItem>){++requeues;Sync();}
static void Loss(Ptr<const Packet> packet,const char* layer,const char* reason) {
    auto it=entries.find(PeekPointer(packet));if(it==entries.end())return;
    const auto& e=it->second;*drops << Simulator::Now().GetNanoSeconds() << ",1584,1," << layer << ',' << reason << ',' << e.visit << ',';
    Fields(*drops,e.id);*drops << ',' << e.ingress << ',' << Simulator::Now().GetNanoSeconds()-e.ingress << '\n';
    entries.erase(it);++dropped;Sync();
}
static void QdBefore(Ptr<const QueueDiscItem> item,const char* reason){Loss(item->GetPacket(),"qdisc_before",reason);}
static void QdAfter(Ptr<const QueueDiscItem> item,const char* reason){Loss(item->GetPacket(),"qdisc_after",reason);}
static void DeviceBefore(Ptr<const Packet> p){Loss(p,"device_before","Device queue overflow");}
static void DeviceAfter(Ptr<const Packet> p){Loss(p,"device_after","Device drop after dequeue");}
static void TcDrop(Ptr<const Packet> p){Loss(p,"source_tc","No root queue and stopped device");}
static void MacDrop(Ptr<const Packet> p){Loss(p,"source_mac","MacTxDrop");}
static void Begin(Ptr<const Packet> packet) {
    auto& e=Find(packet);const int64_t now=Simulator::Now().GetNanoSeconds();
    NS_ABORT_MSG_IF(active || e.devEnq<0 || e.devDeq<e.devEnq,"Invalid source serialization start");
    const int64_t qwait=e.qdEnq<0?0:e.qdDeq-e.qdEnq,devwait=e.devDeq-e.devEnq,total=now-e.ingress;
    NS_ABORT_MSG_IF(qwait<0 || devwait<0 || total<qwait+devwait,"Invalid source residence");
    *visits << now << ',' << e.visit << ',';Fields(*visits,e.id);
    *visits << ',' << e.ingress << ',' << e.qdEnq << ',' << e.qdDeq << ',' << e.devEnq << ',' << e.devDeq
        << ',' << qwait << ',' << devwait << ',' << total-qwait-devwait << ',' << total << '\n';
    entries.erase(PeekPointer(packet));++served;Integrate(now);active=true;Sync();
}
static void End(Ptr<const Packet>){NS_ABORT_MSG_IF(!active,"Source end without active serialization");Integrate(Simulator::Now().GetNanoSeconds());active=false;Sync();}

class FirstOriginalDrop : public ErrorModel {
public:
    static TypeId GetTypeId(){static TypeId tid=TypeId("ns3::BackpressureFirstOriginalDrop").SetParent<ErrorModel>().AddConstructor<FirstOriginalDrop>();return tid;}
private:
    bool DoCorrupt(Ptr<Packet> packet) override {
        if(!firstReady || physicalDropFired)return false;TcpStudyTxTag tag;
        if(!packet->PeekPacketTag(tag) || tag.GetFlowId()!=firstOriginal.flow || tag.GetTxId()!=firstOriginal.tx || tag.GetTxTimeNs()!=firstOriginal.txTime)return false;
        auto copy=packet->Copy();PppHeader ppp;Ipv4Header ip;TcpHeader tcp;
        if(copy->RemoveHeader(ppp)==0 || copy->RemoveHeader(ip)==0 || ip.GetProtocol()!=6 || copy->RemoveHeader(tcp)==0)return false;
        NS_ABORT_MSG_IF(tcp.GetSequenceNumber().GetValue()!=1 || copy->GetSize()!=firstOriginal.payload,"Receiver drop identity mismatch");
        *receiverDrop << Simulator::Now().GetNanoSeconds() << ",1585,1,";Fields(*receiverDrop,firstOriginal);*receiverDrop << '\n';receiverDrop->flush();physicalDropFired=true;return true;
    }
    void DoReset() override {}
};
static void Configure(NodeContainer nodes) {
    const char* flag=std::getenv("CS30401_BACKPRESSURE_MODE");mode=flag?flag:"off";
    NS_ABORT_MSG_IF(mode!="off" && mode!="fifo" && mode!="codel","Unknown queue mode");
    device=DynamicCast<GSLNetDevice>(nodes.Get(1584)->GetDevice(1));
    NS_ABORT_MSG_IF(!device || device->GetIfIndex()!=1,"Unexpected source GSL device");
    queue=device->GetQueue();ndqi=device->GetObject<NetDeviceQueueInterface>();
    auto tc=nodes.Get(1584)->GetObject<TrafficControlLayer>();
    NS_ABORT_MSG_IF(!queue || !ndqi || tc->GetRootQueueDiscOnDevice(device),"Unexpected initial root/device queue");
    NS_ABORT_MSG_IF(queue->GetMaxSize()!=QueueSize("100p") || queue->GetNPackets()!=0,"Expected untouched q100 source");
    if(mode!="off") {
        queue->SetMaxSize(QueueSize("4p"));TrafficControlHelper helper;
        helper.SetRootQueueDisc(mode=="fifo"?"ns3::FifoQueueDisc":"ns3::CoDelQueueDisc","MaxSize",QueueSizeValue(QueueSize("96p")));
        disc=helper.Install(device).Get(0);
        if(mode=="codel") {
            TimeValue target,interval;UintegerValue minimum;BooleanValue ecn,l4s;
            disc->GetAttribute("Target",target);disc->GetAttribute("Interval",interval);disc->GetAttribute("MinBytes",minimum);disc->GetAttribute("UseEcn",ecn);disc->GetAttribute("UseL4s",l4s);
            NS_ABORT_MSG_IF(target.Get()!=MilliSeconds(5) || interval.Get()!=MilliSeconds(100) || minimum.Get()!=1500 || ecn.Get() || l4s.Get(),"Native CoDel defaults differ");
        }
    }
    const char* drop=std::getenv("CS30401_BACKPRESSURE_DROP_FIRST_SEQ1");physicalDropEnabled=drop && std::string(drop)=="1";
    if(physicalDropEnabled) {
        auto receiver=DynamicCast<GSLNetDevice>(nodes.Get(1585)->GetDevice(1));PointerValue existing;
        NS_ABORT_MSG_IF(!receiver,"Unexpected receiver GSL");receiver->GetAttribute("ReceiveErrorModel",existing);
        NS_ABORT_MSG_IF(existing.Get<ErrorModel>(),"Cannot replace an existing receiver error model");receiver->SetReceiveErrorModel(CreateObject<FirstOriginalDrop>());
    }
}
static void Finish() {
    const int64_t now=Simulator::Now().GetNanoSeconds();Integrate(now);
    NS_ABORT_MSG_IF(arrivals!=served+dropped+entries.size(),"Source ingress conservation failed");
    uint64_t pendingQd=0,pendingDev=0,pendingTransit=0;
    for(const auto& item:entries) {
        const auto& e=item.second;
        if(e.devEnq>=0)++pendingDev;else if(e.qdEnq>=0 && e.qdDeq<0)++pendingQd;else ++pendingTransit;
        *drops << now << ",1584,1,pending,censored," << e.visit << ',';Fields(*drops,e.id);
        *drops << ',' << e.ingress << ',' << now-e.ingress << '\n';
    }
    NS_ABORT_MSG_IF(pendingDev!=queue->GetNPackets(),"Source device pending mismatch");
    NS_ABORT_MSG_IF(disc && (pendingQd!=disc->GetNPackets() || pendingTransit!=disc->GetBackpressureRequeuedPackets()),"Source qdisc pending mismatch");
    if(physicalDropEnabled)NS_ABORT_MSG_IF(!physicalDropFired,"Declared receiver physical drop did not occur");
    for(const auto& pair:areas) {
        const auto& a=pair.second;
        *states << pair.first*100000000 << ',' << std::min(now,(pair.first+1)*100000000)
            << ',' << a.packetNs << ',' << a.byteNs << ',' << a.qdPacketNs << ',' << a.devPacketNs << ',' << a.rqPacketNs
            << ',' << a.activeNs << ',' << a.peak << ',' << a.qdPeak << ',' << a.devPeak << ',' << a.rqPeak << ',' << a.changes << '\n';
    }
    const auto qs=disc?disc->GetStats():QueueDisc::Stats();
    NS_ABORT_MSG_IF(disc && (qs.nTotalReceivedPackets!=qs.nTotalEnqueuedPackets+qs.nTotalDroppedPacketsBeforeEnqueue || qs.nTotalEnqueuedPackets-qs.nTotalDequeuedPackets!=disc->GetNPackets()),"Qdisc native conservation failed");
    *summary << now << ',' << arrivals << ',' << served << ',' << dropped << ',' << entries.size() << ',' << pendingQd << ',' << pendingDev << ',' << pendingTransit << ',' << requeues << ',' << active
        << ',' << qs.nTotalReceivedPackets << ',' << qs.nTotalEnqueuedPackets << ',' << qs.nTotalDequeuedPackets << ',' << qs.nTotalDroppedPacketsBeforeEnqueue << ',' << qs.nTotalDroppedPacketsAfterDequeue << ',' << qs.nTotalSentPackets << ',' << physicalDropEnabled << ',' << physicalDropFired << '\n';
    visits->flush();drops->flush();states->flush();summary->flush();config->flush();receiverDrop->flush();
}
static void Install(NodeContainer nodes) {
    const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");NS_ABORT_MSG_IF(!directory,"Source queue observation directory required");
    auto open=[directory](const char* file){auto p=std::make_unique<std::ofstream>(std::string(directory)+"/"+file);NS_ABORT_MSG_IF(!p->good(),"Source observation output failed");return p;};
    visits=open("bp_served.csv");drops=open("bp_outcomes.csv");states=open("bp_state_bins.csv");summary=open("bp_summary.csv");config=open("bp_config.csv");receiverDrop=open("bp_receiver_drop.csv");
    *visits << "time_ns,visit_id,packet_uid,tagged,flow_id,tx_id,tx_time_ns,seq,payload_bytes,ingress_ns,qdisc_enqueue_ns,qdisc_dequeue_ns,device_enqueue_ns,device_dequeue_ns,qdisc_wait_ns,device_wait_ns,handoff_requeue_wait_ns,total_source_wait_ns\n";
    *drops << "time_ns,node_id,device_id,layer,reason,visit_id,packet_uid,tagged,flow_id,tx_id,tx_time_ns,seq,payload_bytes,ingress_ns,residence_ns\n";
    *states << "bin_start_ns,bin_end_ns,packet_ns,byte_ns,qdisc_packet_ns,device_packet_ns,requeue_packet_ns,serializing_ns,peak_queued_packets,qdisc_peak_packets,device_peak_packets,requeue_peak_packets,state_changes\n";
    *summary << "cutoff_ns,ingress,served,unique_source_discarded,pending,pending_qdisc,pending_device,pending_transit,requeue_events,serializing_at_cutoff,qdisc_received,qdisc_enqueued,qdisc_dequeued,qdisc_drop_before,qdisc_drop_after,qdisc_sent,physical_drop_enabled,physical_drop_fired\n";
    *config << "mode,node_id,device_id,txq,device_max,qdisc_type,qdisc_max,wake_initialized,physical_drop_enabled\n";
    *receiverDrop << "time_ns,node_id,device_id,packet_uid,tagged,flow_id,tx_id,tx_time_ns,seq,payload_bytes\n";
    auto tc=nodes.Get(1584)->GetObject<TrafficControlLayer>();tc->SetBackpressureIngressObserver(MakeCallback(&Ingress));
    NS_ABORT_MSG_IF(!tc->TraceConnectWithoutContext("TcDrop",MakeCallback(&TcDrop)),"Missing source TcDrop hook");
    for(auto hook:std::vector<std::pair<std::string,Callback<void,Ptr<const Packet>>>>{{"Enqueue",MakeCallback(&DeviceEnqueue)},{"Dequeue",MakeCallback(&DeviceDequeue)},{"DropBeforeEnqueue",MakeCallback(&DeviceBefore)},{"DropAfterDequeue",MakeCallback(&DeviceAfter)}})
        NS_ABORT_MSG_IF(!queue->TraceConnectWithoutContext(hook.first,hook.second),"Missing source device queue hook");
    NS_ABORT_MSG_IF(!queue->TraceConnectWithoutContext("PacketsInQueue",MakeCallback(&Change)),"Missing source occupancy hook");
    NS_ABORT_MSG_IF(!device->TraceConnectWithoutContext("PhyTxBegin",MakeCallback(&Begin)) || !device->TraceConnectWithoutContext("PhyTxEnd",MakeCallback(&End)) || !device->TraceConnectWithoutContext("MacTxDrop",MakeCallback(&MacDrop)),"Missing source device service/drop hook");
    if(disc) {
        NS_ABORT_MSG_IF(!disc->TraceConnectWithoutContext("Enqueue",MakeCallback(&QdEnqueue)) || !disc->TraceConnectWithoutContext("Dequeue",MakeCallback(&QdDequeue)) || !disc->TraceConnectWithoutContext("Requeue",MakeCallback(&Requeue)),"Missing source qdisc visit hooks");
        NS_ABORT_MSG_IF(!disc->TraceConnectWithoutContext("DropBeforeEnqueue",MakeCallback(&QdBefore)) || !disc->TraceConnectWithoutContext("DropAfterDequeue",MakeCallback(&QdAfter)),"Missing source qdisc drop hooks");
        NS_ABORT_MSG_IF(!disc->TraceConnectWithoutContext("PacketsInQueue",MakeCallback(&Change)) || !disc->TraceConnectWithoutContext("BytesInQueue",MakeCallback(&Change)),"Missing source qdisc state hooks");
    }
    Simulator::ScheduleDestroy(&Finish);
}
}} // ns3::backpressure
#endif
