#ifndef ORBIT_OLD_FLIGHT_DROP_H
#define ORBIT_OLD_FLIGHT_DROP_H
#include "ns3/error-model.h"
#include "ns3/point-to-point-net-device.h"
#include "ns3/gsl-net-device.h"
#include "ns3/ppp-header.h"
#include "ns3/ipv4-header.h"
#include "ns3/tcp-header.h"
#include "ns3/tcp-flow-send-application.h"
#include "ns3/pointer.h"
#include <cstdlib>
#include <fstream>

// Adverse evaluation control only; this tag/rule is never a policy input.
class OrbitOldFlightDrop : public ns3::ErrorModel {
public:
    OrbitOldFlightDrop(int64_t event, int64_t oldForward, const std::string& path)
        : m_event(event), m_earliest(event-oldForward), m_path(path) {}
private:
    bool DoCorrupt(ns3::Ptr<ns3::Packet> p) override {
        using namespace ns3;
        const int64_t now=Simulator::Now().GetNanoSeconds();
        if (m_used || now<m_event) return false;
        TcpStudyTxTag tag;
        OrbitOriginalTag original;
        if (!p->PeekPacketTag(tag) || !p->PeekPacketTag(original) || !original.IsOriginal() ||
            tag.GetFlowId()!=0 || tag.GetTxTimeNs()<m_earliest || tag.GetTxTimeNs()>=m_event)
            return false;
        auto copy=p->Copy();
        PppHeader ppp; Ipv4Header ip; TcpHeader tcp;
        if (copy->GetSize()<42) return false;
        copy->RemoveHeader(ppp);
        if (ppp.GetProtocol()!=0x21) return false;
        copy->RemoveHeader(ip);
        if (ip.GetProtocol()!=6) return false;
        copy->RemoveHeader(tcp);
        if (copy->GetSize()==0 || tcp.GetDestinationPort()!=1024) return false;
        m_used=true;
        std::ofstream out(m_path);
        out << "time_ns,flow_id,tx_id,tx_time_ns,seq,payload_bytes,event_ns,earliest_tx_ns\n"
            << now << ',' << tag.GetFlowId() << ',' << tag.GetTxId() << ',' << tag.GetTxTimeNs()
            << ',' << tcp.GetSequenceNumber().GetValue() << ',' << copy->GetSize() << ','
            << m_event << ',' << m_earliest << '\n';
        return true; // PointToPointNetDevice emits the ordinary PhyRxDrop trace.
    }
    void DoReset() override {} // One drop for the whole run, shared across destination devices.
    int64_t m_event, m_earliest;
    std::string m_path;
    bool m_used{false};
};

inline void InstallOrbitOldFlightDrop(const ns3::NodeContainer& nodes) {
    using namespace ns3;
    const char* enabled=std::getenv("CS30401_ORBIT_ACTUAL_DROP");
    if (!enabled || std::string(enabled)!="1") return;
    const char* directory=std::getenv("CS30401_STUDY_TRACE_DIR");
    NS_ABORT_MSG_IF(!directory || nodes.GetN()<=1585, "Invalid old-flight drop setup");
    auto error=CreateObject<OrbitOldFlightDrop>(26200000000LL, 48847704LL,
                  std::string(directory)+"/orbit_actual_drop.csv");
    uint32_t installed=0;
    std::ofstream installation(std::string(directory)+"/orbit_drop_install.csv");
    installation << "node_id,device_id,device_type,event_ns,old_forward_ns\n";
    for (uint32_t i=0; i<nodes.Get(1585)->GetNDevices(); ++i) {
        auto raw=nodes.Get(1585)->GetDevice(i);
        auto gsl=DynamicCast<GSLNetDevice>(raw);
        auto p2p=DynamicCast<PointToPointNetDevice>(raw);
        if (gsl) gsl->SetReceiveErrorModel(error);
        else if (p2p) p2p->SetAttribute("ReceiveErrorModel", PointerValue(error));
        else continue;
        installation << "1585," << i << ',' << raw->GetInstanceTypeId().GetName()
                     << ",26200000000,48847704\n";
        ++installed;
    }
    NS_ABORT_MSG_IF(installed==0, "No destination GSL device for actual-drop control");
}
#endif
