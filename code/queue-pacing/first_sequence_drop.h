#ifndef CS30401_QUEUE_PACING_FIRST_SEQUENCE_DROP_H
#define CS30401_QUEUE_PACING_FIRST_SEQUENCE_DROP_H
#include "ns3/error-model.h"
#include "ns3/gsl-net-device.h"
#include "ns3/point-to-point-net-device.h"
#include "ns3/ppp-header.h"
#include "ns3/ipv4-header.h"
#include "ns3/tcp-header.h"
#include "ns3/tcp-flow-send-application.h"
#include "ns3/pointer.h"
#include <cstdlib>
#include <fstream>

namespace ns3 { namespace queuepacing {
// Evaluation truth only, never an input to pacing or presumed-loss waiting.
class FirstOriginalLoss : public ErrorModel {
  public:
    explicit FirstOriginalLoss(std::string path):m_path(path) {}
  private:
    bool DoCorrupt(Ptr<Packet> p) override {
        if(m_used) return false;
        TcpStudyTxTag tag; OrbitOriginalTag original;
        if(!p->PeekPacketTag(tag) || !p->PeekPacketTag(original) || !original.IsOriginal() ||
           tag.GetFlowId()!=0 || p->GetSize()<42) return false;
        auto copy=p->Copy(); PppHeader ppp; Ipv4Header ip; TcpHeader tcp;
        copy->RemoveHeader(ppp);if(ppp.GetProtocol()!=0x21) return false;
        copy->RemoveHeader(ip);if(ip.GetProtocol()!=6 || ip.GetFragmentOffset()!=0) return false;
        copy->RemoveHeader(tcp);
        if(tcp.GetDestinationPort()!=1024 || tcp.GetSequenceNumber().GetValue()!=1 ||
           copy->GetSize()!=1380) return false;
        m_used=true;
        std::ofstream out(m_path);
        out << "time_ns,flow_id,tx_id,tx_time_ns,seq,payload_bytes,receiver_node\n"
            << Simulator::Now().GetNanoSeconds() << ',' << tag.GetFlowId() << ',' << tag.GetTxId()
            << ',' << tag.GetTxTimeNs() << ',' << tcp.GetSequenceNumber().GetValue()
            << ',' << copy->GetSize() << ",1585\n";
        return true; // Existing GSL receive path emits the physical drop.
    }
    void DoReset() override {}
    std::string m_path; bool m_used{false};
};
inline void InstallFirstOriginalLoss(NodeContainer nodes) {
    const char* enabled=std::getenv("CS30401_QUEUE_PACING_FIRST_LOSS");
    if(!enabled || std::string(enabled)!="1") return;
    const char* old=std::getenv("CS30401_ORBIT_ACTUAL_DROP");
    NS_ABORT_MSG_IF(old && std::string(old)=="1","Two evaluation loss models requested");
    const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");
    NS_ABORT_MSG_IF(!directory || nodes.GetN()<=1585,"Invalid first-sequence loss setup");
    auto error=CreateObject<FirstOriginalLoss>(std::string(directory)+"/pacing_first_loss.csv");
    uint32_t count=0;
    std::ofstream out(std::string(directory)+"/pacing_first_loss_install.csv");
    out << "node_id,device_id,device_type,flow_id,seq,payload_bytes\n";
    auto node=nodes.Get(1585);
    for(uint32_t i=0;i<node->GetNDevices();++i) {
        auto raw=node->GetDevice(i);
        if(!DynamicCast<GSLNetDevice>(raw) && !DynamicCast<PointToPointNetDevice>(raw)) continue;
        PointerValue existing;
        raw->GetAttribute("ReceiveErrorModel",existing);
        NS_ABORT_MSG_IF(existing.Get<ErrorModel>(),"Refusing to overwrite an existing physical receive error model");
        if(auto gsl=DynamicCast<GSLNetDevice>(raw)) gsl->SetReceiveErrorModel(error);
        else if(auto p2p=DynamicCast<PointToPointNetDevice>(raw))
            p2p->SetAttribute("ReceiveErrorModel",PointerValue(error));
        else continue;
        out << "1585," << i << ',' << raw->GetInstanceTypeId().GetName() << ",0,1,1380\n";
        ++count;
    }
    NS_ABORT_MSG_IF(count==0,"No physical destination device for first loss");
}
}}
#endif
