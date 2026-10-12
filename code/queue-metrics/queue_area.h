#ifndef CS30401_QUEUE_MITIGATION_AREA_H
#define CS30401_QUEUE_MITIGATION_AREA_H
#include "ns3/abort.h"
#include <algorithm>
#include <cstdint>
#include <map>

namespace ns3 { namespace queuemitigation {
struct AreaBin {
    uint64_t packetNs{0}, byteNs{0}, fullNs{0};
    uint32_t peakPackets{0}, peakBytes{0};
};

// Read-only metrics for a queue initially empty at simulation time zero.
// Two callbacks at the same time may change packet and byte state in either
// order: integrating the PREVIOUS state before each change adds zero area
// between them. No timer or new simulator event is introduced.
class QueueArea {
  public:
    explicit QueueArea(uint32_t maximumPackets = 0, int64_t stepNs = 100000000)
        : m_maximum(maximumPackets), m_step(stepNs) {
        NS_ABORT_MSG_IF(stepNs <= 0, "Queue area requires a positive bin width");
    }
    void Packets(uint32_t oldValue, uint32_t newValue, int64_t now) {
        NS_ABORT_MSG_IF(oldValue != m_packets, "Queue packet trace lost a transition");
        Advance(now); m_packets = newValue; Peak(now);
    }
    void Bytes(uint32_t oldValue, uint32_t newValue, int64_t now) {
        NS_ABORT_MSG_IF(oldValue != m_bytes, "Queue byte trace lost a transition");
        Advance(now); m_bytes = newValue; Peak(now);
    }
    void Advance(int64_t now) {
        NS_ABORT_MSG_IF(now < m_last || now < 0, "Queue area time decreased");
        // An omitted idle interval is exactly zero, not an unknown snapshot.
        if (!m_packets && !m_bytes) { m_last = now; return; }
        while (m_last < now) {
            const int64_t bucket = m_last / m_step;
            const int64_t end = std::min(now, (bucket + 1) * m_step);
            const uint64_t duration = static_cast<uint64_t>(end - m_last);
            auto& bin = m_bins[bucket];
            bin.packetNs += uint64_t(m_packets) * duration;
            bin.byteNs += uint64_t(m_bytes) * duration;
            if (m_maximum && m_packets == m_maximum) bin.fullNs += duration;
            bin.peakPackets = std::max(bin.peakPackets, m_packets);
            bin.peakBytes = std::max(bin.peakBytes, m_bytes);
            m_last = end;
        }
    }
    const std::map<int64_t, AreaBin>& Bins() const { return m_bins; }
    int64_t ObservedUntilNs() const { return m_last; }
    int64_t StepNs() const { return m_step; }
    uint32_t PacketState() const { return m_packets; }
    uint32_t ByteState() const { return m_bytes; }
    uint32_t MaximumPackets() const { return m_maximum; }
  private:
    void Peak(int64_t now) {
        if (!m_packets && !m_bytes) return;
        auto& bin = m_bins[now / m_step];
        bin.peakPackets = std::max(bin.peakPackets, m_packets);
        bin.peakBytes = std::max(bin.peakBytes, m_bytes);
    }
    uint32_t m_maximum, m_packets{0}, m_bytes{0};
    int64_t m_step, m_last{0};
    std::map<int64_t, AreaBin> m_bins;
};
}}
#endif
