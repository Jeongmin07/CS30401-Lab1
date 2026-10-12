#include "queue_area.h"
#include <cassert>
#include <iostream>
using ns3::queuemitigation::QueueArea;
void fill(QueueArea& a,bool bytesFirst) {
    auto change=[&](int64_t t,uint32_t oldN,uint32_t n,uint32_t oldB,uint32_t b) {
        if(bytesFirst) {a.Bytes(oldB,b,t);a.Packets(oldN,n,t);}
        else {a.Packets(oldN,n,t);a.Bytes(oldB,b,t);}
    };
    change(30000000,0,2,0,2000);change(80000000,2,3,2000,3000);
    change(110000000,3,2,3000,2000);change(180000000,2,0,2000,0);
    a.Advance(250000000);
}
int main() {
    QueueArea a(3),b(3);fill(a,false);fill(b,true);
    assert(a.Bins().size()==2 && b.Bins().size()==2);
    const uint64_t expectedPacket[]={160000000,170000000};
    const uint64_t expectedFull[]={20000000,10000000};
    for(int i=0;i<2;++i) {
        auto x=a.Bins().at(i),y=b.Bins().at(i);
        assert(x.packetNs==expectedPacket[i] && x.byteNs==expectedPacket[i]*1000);
        assert(x.fullNs==expectedFull[i] && x.peakPackets==3 && x.peakBytes==3000);
        assert(x.packetNs==y.packetNs && x.byteNs==y.byteNs && x.fullNs==y.fullNs);
    }
    assert(a.ObservedUntilNs()==250000000 && a.PacketState()==0 && a.ByteState()==0);
    QueueArea pending(2);pending.Bytes(0,2000,150000000);pending.Packets(0,2,150000000);
    pending.Advance(250000000);
    assert(pending.Bins().at(1).packetNs==100000000 && pending.Bins().at(2).packetNs==100000000);
    assert(pending.Bins().at(1).fullNs==50000000 && pending.Bins().at(2).fullNs==50000000);
    QueueArea combined;combined.Packets(0,102,10000000);combined.Bytes(0,146268,10000000);
    combined.Advance(11000000);
    assert(combined.Bins().at(0).packetNs==102000000 && combined.Bins().at(0).fullNs==0);
    std::cout << "{\"nonuniform_two_bin_integrals\":true,\"packet_byte_callback_order_independent\":true,"
              << "\"partial_final_bin_pending\":true,\"idle_intervals_exact_zero\":true,"
              << "\"combined_no_false_strict_capacity\":true,\"ns3_simulations\":0}" << std::endl;
}
