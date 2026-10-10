// Controlled propagation/queue diagnostic, not the multi-hop LEO model.
// Copy to scratch/vegas_micro/vegas_micro.cc in the official patched ns-3.48 environment.
// Requires the team's existing study packet/sink instrumentation and Vegas patch.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/traffic-control-module.h"
#include "ns3/tcp-flow-send-helper.h"
#include "ns3/tcp-flow-sink-helper.h"
#include "ns3/tcp-flow-send-application.h"
#include "../main_satnet/study_drop_trace.h"

#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using namespace ns3;

namespace {

void Require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

Time ChannelDelay(Ptr<PointToPointChannel> channel) {
    TimeValue delay;
    channel->GetAttribute("Delay", delay);
    return delay.Get();
}

void SetEnvironment(const char* name, const std::string& value) {
#ifdef _WIN32
    Require(_putenv_s(name, value.c_str()) == 0, "Cannot set environment variable");
#else
    Require(setenv(name, value.c_str(), 1) == 0, "Cannot set environment variable");
#endif
}

std::string JsonString(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 0x20) out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                               << unsigned(c) << std::dec;
        else out << c;
    }
    out << '"';
    return out.str();
}

struct PacketIdentity {
    uint64_t uid;
    bool tagged;
    uint64_t flowId{0};
    uint64_t txId{0};
    int64_t txTimeNs{0};

    using Key = std::tuple<uint64_t, bool, uint64_t, uint64_t>;
    Key GetKey() const { return {uid, tagged, flowId, txId}; }
};

PacketIdentity Identify(Ptr<const Packet> packet) {
    PacketIdentity id{packet->GetUid(), false};
    TcpStudyTxTag tag;
    id.tagged = packet->PeekPacketTag(tag);
    if (id.tagged) {
        id.flowId = tag.GetFlowId();
        id.txId = tag.GetTxId();
        id.txTimeNs = tag.GetTxTimeNs();
    }
    return id;
}

void WriteIdentity(std::ostream& out, const PacketIdentity& id) {
    out << id.uid << ',' << (id.tagged ? 1 : 0) << ',';
    if (id.tagged) out << id.flowId;
    out << ',';
    if (id.tagged) out << id.txId;
    out << ',';
    if (id.tagged) out << id.txTimeNs;
}

struct QueueLogs {
    std::ofstream events, sojourn, occupancy, coverage, pending, summary;
    explicit QueueLogs(const std::string& folder)
        : events(folder + "/queue_events.csv"), sojourn(folder + "/queue_sojourn.csv"),
          occupancy(folder + "/queue_occupancy.csv"), coverage(folder + "/queue_coverage.csv"),
          pending(folder + "/queue_pending.csv"), summary(folder + "/queue_summary.csv") {
        Require(events && sojourn && occupancy && coverage && pending && summary,
                "Cannot open queue trace files");
        events << "time_ns,node_id,device_id,direction,event,packet_uid,tagged,flow_id,tx_id,"
                  "tx_time_ns,packet_bytes,queue_packets,queue_bytes\n";
        sojourn << "dequeue_time_ns,enqueue_time_ns,sojourn_ns,node_id,device_id,direction,"
                   "packet_uid,tagged,flow_id,tx_id,tx_time_ns,packet_bytes\n";
        occupancy << "time_ns,node_id,device_id,direction,old_packets,new_packets,queue_bytes\n";
        coverage << "node_id,device_id,direction,layer,connected\n";
        pending << "observation_end_ns,enqueue_time_ns,age_ns,node_id,device_id,direction,"
                   "packet_uid,tagged,flow_id,tx_id,tx_time_ns,packet_bytes\n";
        summary << "node_id,device_id,direction,enqueued,dequeued,drop_before_enqueue,"
                   "drop_after_dequeue,pending,zero_sojourn\n";
    }
};

// DropTail uses Dequeue for service, but Queue::Remove also emits Dequeue before
// DropAfterDequeue. Log both traces; analysis must exclude those removal records
// from service statistics. This driver never calls Remove or installs an AQM.
class QueueObserver {
public:
    QueueObserver(Ptr<PointToPointNetDevice> device, std::string direction,
                  std::shared_ptr<QueueLogs> logs)
        : m_device(device), m_queue(device->GetQueue()), m_direction(std::move(direction)),
          m_logs(std::move(logs)) {
        Require(m_queue != nullptr, "Missing point-to-point device queue");
        Connect("Enqueue", MakeCallback(&QueueObserver::Enqueue, this));
        Connect("Dequeue", MakeCallback(&QueueObserver::Dequeue, this));
        Connect("DropBeforeEnqueue", MakeCallback(&QueueObserver::DropBefore, this));
        Connect("DropAfterDequeue", MakeCallback(&QueueObserver::DropAfter, this));
        Connect("PacketsInQueue", MakeCallback(&QueueObserver::Occupancy, this));
        Snapshot();
    }

    void Finish() {
        Snapshot();
        Require(m_waiting.size() == m_queue->GetNPackets(), "Queue tracking count mismatch");
        Require(m_enqueued == m_dequeued + m_waiting.size(), "Queue conservation mismatch");
        // This assertion also makes every logged sojourn a served dequeue in
        // this DropTail scenario; a future queue implementation must revisit it.
        Require(m_dropAfter == 0, "Unexpected Remove/DropAfterDequeue; service analysis invalid");
        for (const auto& [key, waiting] : m_waiting) {
            (void) key;
            const int64_t now = Simulator::Now().GetNanoSeconds();
            m_logs->pending << now << ',' << waiting.enqueueNs << ',' << now - waiting.enqueueNs << ',';
            WriteLocation(m_logs->pending);
            WriteIdentity(m_logs->pending, waiting.id);
            m_logs->pending << ',' << waiting.bytes << '\n';
        }
        WriteLocation(m_logs->summary);
        m_logs->summary << m_enqueued << ',' << m_dequeued << ',' << m_dropBefore << ','
                        << m_dropAfter << ',' << m_waiting.size() << ',' << m_zeroSojourn << '\n';
    }

private:
    struct Waiting { int64_t enqueueNs; uint32_t bytes; PacketIdentity id; };
    Ptr<PointToPointNetDevice> m_device;
    Ptr<Queue<Packet>> m_queue;
    std::string m_direction;
    std::shared_ptr<QueueLogs> m_logs;
    std::map<PacketIdentity::Key, Waiting> m_waiting;
    uint64_t m_enqueued{0}, m_dequeued{0}, m_dropBefore{0}, m_dropAfter{0}, m_zeroSojourn{0};

    template<typename CallbackType>
    void Connect(const std::string& layer, CallbackType callback) {
        const bool ok = m_queue->TraceConnectWithoutContext(layer, callback);
        WriteLocation(m_logs->coverage);
        m_logs->coverage << layer << ',' << (ok ? 1 : 0) << '\n';
        Require(ok, "Missing queue trace: " + layer);
    }

    void WriteLocation(std::ostream& out) const {
        out << m_device->GetNode()->GetId() << ',' << m_device->GetIfIndex() << ',' << m_direction << ',';
    }

    void LogPacket(const std::string& event, Ptr<const Packet> packet) {
        m_logs->events << Simulator::Now().GetNanoSeconds() << ',';
        WriteLocation(m_logs->events);
        m_logs->events << event << ',';
        WriteIdentity(m_logs->events, Identify(packet));
        m_logs->events << ',' << packet->GetSize() << ',' << m_queue->GetNPackets() << ','
                       << m_queue->GetNBytes() << '\n';
    }

    void Enqueue(Ptr<const Packet> packet) {
        const auto id = Identify(packet);
        Require(m_waiting.emplace(id.GetKey(), Waiting{Simulator::Now().GetNanoSeconds(),
                                                      packet->GetSize(), id}).second,
                "Duplicate transmission identity concurrently in queue");
        ++m_enqueued;
        LogPacket("Enqueue", packet);
    }

    void Dequeue(Ptr<const Packet> packet) {
        const auto id = Identify(packet);
        auto entry = m_waiting.find(id.GetKey());
        Require(entry != m_waiting.end(), "Dequeue without observed enqueue");
        const int64_t now = Simulator::Now().GetNanoSeconds();
        const int64_t wait = now - entry->second.enqueueNs;
        Require(wait >= 0 && entry->second.bytes == packet->GetSize(), "Queue packet changed");
        m_logs->sojourn << now << ',' << entry->second.enqueueNs << ',' << wait << ',';
        WriteLocation(m_logs->sojourn);
        WriteIdentity(m_logs->sojourn, id);
        m_logs->sojourn << ',' << packet->GetSize() << '\n';
        if (wait == 0) ++m_zeroSojourn;
        m_waiting.erase(entry);
        ++m_dequeued;
        LogPacket("Dequeue", packet);
    }

    void DropBefore(Ptr<const Packet> packet) {
        ++m_dropBefore;
        LogPacket("DropBeforeEnqueue", packet);
    }

    void DropAfter(Ptr<const Packet> packet) {
        ++m_dropAfter;
        LogPacket("DropAfterDequeue", packet);
    }

    void Occupancy(uint32_t oldValue, uint32_t newValue) {
        m_logs->occupancy << Simulator::Now().GetNanoSeconds() << ',';
        WriteLocation(m_logs->occupancy);
        // ns-3.48 Queue::DoEnqueue/DoDequeue update m_nBytes before m_nPackets.
        // Thus GetNBytes is the post-change queued-byte count at this callback.
        m_logs->occupancy << oldValue << ',' << newValue << ',' << m_queue->GetNBytes() << '\n';
    }

    void Snapshot() { Occupancy(m_queue->GetNPackets(), m_queue->GetNPackets()); }
};

// TcpFlowSendApplication creates its socket in StartApplication, not Install.
// A node-local SocketType switch before the later start affects only NEW sockets.
// Inspect the actual sender sockets rather than inferring CCA from defaults.
void VerifySocketType(Ptr<TcpL4Protocol> tcp, uint16_t port, uint32_t flowId,
                      const std::string& expected, std::ofstream* out) {
    ObjectMapValue sockets;
    tcp->GetAttribute("SocketList", sockets);
    uint32_t found = 0;
    for (auto it = sockets.Begin(); it != sockets.End(); ++it) {
        auto socket = DynamicCast<TcpSocketBase>(it->second);
        Address peer;
        if (!socket || socket->GetPeerName(peer) != 0 || !InetSocketAddress::IsMatchingType(peer)) continue;
        if (InetSocketAddress::ConvertFrom(peer).GetPort() != port) continue;
        PointerValue algorithm;
        socket->GetAttribute("CongestionOps", algorithm);
        auto ops = algorithm.Get<TcpCongestionOps>();
        Require(ops != nullptr, "Missing socket congestion-control object");
        const std::string actual = ops->GetInstanceTypeId().GetName();
        Require(actual == expected, "Wrong congestion-control type on flow " + std::to_string(flowId));
        *out << Simulator::Now().GetNanoSeconds() << ',' << flowId << ',' << port << ','
             << expected << ',' << actual << '\n';
        ++found;
    }
    Require(found == 1, "Expected exactly one sender socket for port " + std::to_string(port));
}

struct AppDelivery { uint64_t bytes{0}; int64_t lastNs{-1}; };

AppDelivery ReadAppDelivery(const std::string& path, uint32_t flowId) {
    std::ifstream input(path);
    Require(bool(input), "Missing receiver application trace: " + path);
    std::string line;
    std::getline(input, line);
    Require(line == "time_ns,node_id,connection_id,local_ip,local_port,peer_ip,peer_port,"
                    "flow_id,packet_uid,payload_bytes,connection_total_rx_bytes,sink_total_rx_bytes",
            "Unexpected receiver application trace schema");
    AppDelivery delivery;
    while (std::getline(input, line)) {
        std::vector<std::string> fields;
        std::istringstream row(line);
        std::string field;
        while (std::getline(row, field, ',')) fields.push_back(field);
        Require(fields.size() == 12, "Malformed receiver application row");
        Require(fields[7] == std::to_string(flowId), "Receiver trace has missing/wrong flow tag");
        delivery.bytes += std::stoull(fields[9]);
        Require(delivery.bytes == std::stoull(fields[10]), "Application cumulative bytes mismatch");
        Require(delivery.bytes == std::stoull(fields[11]), "Unexpected second connection on sink port");
        delivery.lastNs = std::stoll(fields[0]);
    }
    return delivery;
}

} // namespace

int main(int argc, char** argv) {
    Time::SetResolution(Time::NS);
    std::string runDir, parameters, cc = "TcpVegas";
    double duration = 200, rate = 100, beforeMs = 45, afterMs = 48, eventS = 100, flowStartS = 0;
    bool competitor = false, renewal = false, renewalPreserveBeta = false;
    double competitorStartS = 80, renewalMinRiseMs = 1;
    uint32_t queuePackets = 100, initialSsthreshPackets = 900, renewalRounds = 20;
    uint32_t seed = 123456789;
    uint64_t run = 1, maxBytes = 100000000000ULL;
    CommandLine cmd;
    cmd.AddValue("run_dir", "Output directory", runDir);
    cmd.AddValue("parameters", "Flow 0 additional study parameters; normally empty", parameters);
    cmd.AddValue("cc", "Flow 0 TCP class name (default TcpVegas)", cc);
    cmd.AddValue("duration", "Observation duration, seconds", duration);
    cmd.AddValue("rate", "Fixed rate of BOTH full-duplex directions, Mbit/s", rate);
    cmd.AddValue("before_ms", "Initial ONE-WAY propagation delay, fractional ms preserved", beforeMs);
    cmd.AddValue("after_ms", "ONE-WAY propagation delay after the step, fractional ms preserved", afterMs);
    cmd.AddValue("event_s", "Propagation-delay change time, seconds", eventS);
    cmd.AddValue("flow_start_s", "Vegas application start time, seconds", flowStartS);
    cmd.AddValue("queue_pkts", "DropTail queue packet limit PER DIRECTION", queuePackets);
    cmd.AddValue("initial_ssthresh_pkts", "Initial TCP slow-start threshold, MSS equivalents", initialSsthreshPackets);
    cmd.AddValue("max_bytes", "Bytes per bulk sender (0 means unlimited)", maxBytes);
    cmd.AddValue("competitor", "Enable a later same-direction CUBIC bulk sender", competitor);
    cmd.AddValue("competitor_start_s", "CUBIC start time; default80 precedes default event100", competitorStartS);
    cmd.AddValue("renewal", "Enable the experimental recent-min Vegas renewal", renewal);
    cmd.AddValue("renewal_preserve_beta", "Keep existing Vegas beta packet budget at renewal", renewalPreserveBeta);
    cmd.AddValue("renewal_rounds", "Recent-min Vegas round window", renewalRounds);
    cmd.AddValue("renewal_min_rise_ms", "Recent-min rise gate in fractional ms", renewalMinRiseMs);
    cmd.AddValue("seed", "ns-3 RNG seed", seed);
    cmd.AddValue("run", "ns-3 RNG run number (not an independent deterministic replay)", run);
    cmd.Parse(argc, argv);

    Require(!runDir.empty(), "run_dir is required");
    for (double value : {duration, rate, beforeMs, afterMs, eventS, flowStartS,
                         competitorStartS, renewalMinRiseMs})
        Require(std::isfinite(value), "Time/rate arguments must be finite");
    Require(duration > 0 && rate > 0 && beforeMs > 0 && afterMs > 0 && queuePackets > 0,
            "Duration, link rate, propagation delays and queue limit must be positive");
    const Time endTime = Seconds(duration), eventTime = Seconds(eventS), flowStart = Seconds(flowStartS);
    const Time beforeDelay = Seconds(beforeMs / 1000.0), afterDelay = Seconds(afterMs / 1000.0);
    const Time competitorStart = Seconds(competitorStartS);
    Require(eventTime >= Time(0) && eventTime < endTime && flowStart >= Time(0) && flowStart < endTime,
            "Flow start and delay event must be within the observation");
    if (competitor)
        Require(competitorStart > flowStart + NanoSeconds(1) && competitorStart + NanoSeconds(1) < endTime,
                "Competitor must start later than flow 0; simultaneous-start is unsupported");
    Require(initialSsthreshPackets > 0 && uint64_t(initialSsthreshPackets) * 1380 <= UINT32_MAX,
            "Initial slow-start threshold does not fit TCP byte field");
    Require(renewalRounds >= 2 && renewalMinRiseMs > 0, "Invalid Vegas renewal parameters");
    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);

    const std::string logsDir = runDir + "/logs_ns3";
    std::filesystem::create_directories(logsDir);
    // Enable existing passive packet/sink observations in this driver's folder.
    SetEnvironment("CS30401_STUDY_TRACE", "1");
    SetEnvironment("CS30401_STUDY_TRACE_DIR", logsDir);
    SetEnvironment("CS30401_VEGAS_TRACE_DIR", logsDir);
    const std::string candidateType = "ns3::" + cc;
    Config::SetDefault("ns3::TcpL4Protocol::SocketType", TypeIdValue(TypeId::LookupByName(candidateType)));
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1380));
    Config::SetDefault("ns3::TcpSocket::InitialCwnd", UintegerValue(10));
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(32 * 1024 * 1024));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(32 * 1024 * 1024));
    Config::SetDefault("ns3::TcpSocket::InitialSlowStartThreshold", UintegerValue(initialSsthreshPackets * 1380));
    Config::SetDefault("ns3::TcpSocketState::EnablePacing", BooleanValue(cc == "TcpBbr"));
    Config::SetDefault("ns3::TcpVegas::RecentMinRenewal", BooleanValue(renewal));
    Config::SetDefault("ns3::TcpVegas::RenewalPreserveBeta", BooleanValue(renewalPreserveBeta));
    Config::SetDefault("ns3::TcpVegas::RenewalRounds", UintegerValue(renewalRounds));
    Config::SetDefault("ns3::TcpVegas::RenewalMinRise", TimeValue(Seconds(renewalMinRiseMs / 1000.0)));

    NodeContainer nodes;
    nodes.Create(2);
    InternetStackHelper stack;
    stack.Install(nodes);
    PointToPointHelper link;
    link.SetDeviceAttribute("DataRate", StringValue(std::to_string(rate) + "Mbps"));
    link.SetChannelAttribute("Delay", TimeValue(beforeDelay));
    link.SetQueue("ns3::DropTailQueue<Packet>", "MaxSize",
                  QueueSizeValue(QueueSize(std::to_string(queuePackets) + "p")));
    auto devices = link.Install(nodes);
    Ipv4AddressHelper addresses;
    addresses.SetBase("10.1.1.0", "255.255.255.0");
    auto interfaces = addresses.Assign(devices);
    TrafficControlHelper traffic;
    traffic.Uninstall(devices); // Address assignment otherwise installs a root qdisc.
    for (uint32_t i = 0; i < devices.GetN(); ++i) {
        auto device = devices.Get(i);
        Require(!device->GetNode()->GetObject<TrafficControlLayer>()->GetRootQueueDiscOnDevice(device),
                "Unexpected root queue disc");
    }
    cs30401study::Install(nodes);
    auto queueLogs = std::make_shared<QueueLogs>(logsDir);
    std::vector<std::unique_ptr<QueueObserver>> queueObservers;
    for (uint32_t i = 0; i < devices.GetN(); ++i)
        queueObservers.push_back(std::make_unique<QueueObserver>(
            DynamicCast<PointToPointNetDevice>(devices.Get(i)), i == 0 ? "forward" : "reverse", queueLogs));

    std::ofstream socketTypes(logsDir + "/socket_types.csv");
    std::ofstream delayEvents(logsDir + "/delay_events.csv");
    Require(socketTypes && delayEvents, "Cannot open driver audit traces");
    socketTypes << "time_ns,flow_id,peer_port,expected_cc,actual_cc\n";
    delayEvents << "time_ns,event,old_one_way_delay_ns,new_one_way_delay_ns,propagation_rtt_ns\n";
    auto channel = DynamicCast<PointToPointChannel>(devices.Get(0)->GetChannel());
    Require(channel && devices.Get(1)->GetChannel() == channel, "Flows do not share one physical link");
    const Time initialDelay = ChannelDelay(channel);
    delayEvents << "0,INITIAL," << initialDelay.GetNanoSeconds() << ','
                << initialDelay.GetNanoSeconds() << ',' << 2 * initialDelay.GetNanoSeconds() << '\n';

    std::vector<Ptr<TcpFlowSendApplication>> sources;
    auto senderTcp = nodes.Get(0)->GetObject<TcpL4Protocol>();
    for (uint32_t id = 0; id < (competitor ? 2U : 1U); ++id) {
        const uint16_t port = uint16_t(1024 + id);
        TcpFlowSinkHelper sink("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
        auto sinks = sink.Install(nodes.Get(1));
        sinks.Start(Seconds(0));
        TcpFlowSendHelper source("ns3::TcpSocketFactory", InetSocketAddress(interfaces.GetAddress(1), port),
                                 maxBytes, id, true, logsDir, id == 0 ? parameters : "");
        auto apps = source.Install(nodes.Get(0));
        sources.push_back(apps.Get(0)->GetObject<TcpFlowSendApplication>());
        const Time start = id == 0 ? flowStart : competitorStart;
        apps.Start(start);
        if (id == 1) {
            Simulator::Schedule(start - NanoSeconds(1), [senderTcp]() {
                senderTcp->SetAttribute("SocketType", TypeIdValue(TcpCubic::GetTypeId()));
            });
        }
        Simulator::Schedule(start + NanoSeconds(1), [senderTcp, id, port, candidateType, &socketTypes]() {
            VerifySocketType(senderTcp, port, id, id == 0 ? candidateType : "ns3::TcpCubic", &socketTypes);
            if (id == 1) VerifySocketType(senderTcp, 1024, 0, candidateType, &socketTypes);
        });
    }
    Simulator::Schedule(eventTime, [channel, afterDelay, &delayEvents]() {
        const Time oldDelay = ChannelDelay(channel);
        channel->SetAttribute("Delay", TimeValue(afterDelay));
        const Time actualDelay = ChannelDelay(channel);
        delayEvents << Simulator::Now().GetNanoSeconds() << ",SET_DELAY," << oldDelay.GetNanoSeconds()
                    << ',' << actualDelay.GetNanoSeconds() << ',' << 2 * actualDelay.GetNanoSeconds() << '\n';
    });

    std::ofstream config(runDir + "/config_driver.json");
    Require(bool(config), "Cannot open driver configuration");
    config << std::setprecision(17)
           << "{\n  \"topology\": \"two nodes, one full-duplex point-to-point link\",\n"
           << "  \"cc\": " << JsonString(candidateType) << ",\n"
           << "  \"renewal\": " << (renewal ? "true" : "false") << ",\n"
           << "  \"renewal_preserve_beta\": " << (renewalPreserveBeta ? "true" : "false") << ",\n"
           << "  \"renewal_rounds\": " << renewalRounds << ",\n"
           << "  \"renewal_min_rise_ns\": " << Seconds(renewalMinRiseMs / 1000.0).GetNanoSeconds() << ",\n"
           << "  \"duration_ns\": " << endTime.GetNanoSeconds() << ",\n"
           << "  \"rate_mbps\": " << rate << ",\n"
           << "  \"queue_pkts_per_direction\": " << queuePackets << ",\n"
           << "  \"root_queue_disc\": false,\n  \"receive_error_model\": false,\n"
           << "  \"before_one_way_delay_ns\": " << beforeDelay.GetNanoSeconds() << ",\n"
           << "  \"after_one_way_delay_ns\": " << afterDelay.GetNanoSeconds() << ",\n"
           << "  \"before_propagation_rtt_ns\": " << 2 * beforeDelay.GetNanoSeconds() << ",\n"
           << "  \"after_propagation_rtt_ns\": " << 2 * afterDelay.GetNanoSeconds() << ",\n"
           << "  \"event_ns\": " << eventTime.GetNanoSeconds() << ",\n"
           << "  \"flow0_start_ns\": " << flowStart.GetNanoSeconds() << ",\n"
           << "  \"flow0_port\": 1024,\n  \"flow0_parameters\": " << JsonString(parameters) << ",\n"
           << "  \"competitor\": " << (competitor ? "true" : "false") << ",\n"
           << "  \"competitor_start_ns\": " << competitorStart.GetNanoSeconds() << ",\n"
           << "  \"competitor_cc\": \"ns3::TcpCubic\",\n  \"competitor_port\": 1025,\n"
           << "  \"both_flows_share_forward_device\": true,\n"
           << "  \"max_bytes_each\": " << maxBytes << ",\n"
           << "  \"mss_bytes\": 1380,\n  \"initial_cwnd_pkts\": 10,\n"
           << "  \"initial_ssthresh_pkts\": " << initialSsthreshPackets << ",\n"
           << "  \"seed\": " << seed << ",\n  \"run\": " << run << ",\n"
           << "  \"queue_measurement\": \"Enqueue-to-Dequeue wait; includes zero, excludes serialization and propagation; censored packets in queue_pending.csv\",\n"
           << "  \"queue_bytes_at_packets_callback\": \"post-change ns3.48 Queue byte count\",\n"
           << "  \"logs_dir\": " << JsonString(logsDir) << "\n}\n";
    config.close();
    std::ofstream properties(runDir + "/config_ns3.properties");
    properties << "simulation_end_time_ns=" << endTime.GetNanoSeconds() << '\n';
    properties.close();

    Simulator::Stop(endTime);
    Simulator::Run();
    std::vector<int64_t> acked;
    std::vector<bool> completed;
    for (const auto& source : sources) {
        source->FinalizeDetailedLogs();
        acked.push_back(source->GetAckedBytes());
        completed.push_back(source->IsCompleted());
    }
    for (const auto& observer : queueObservers) observer->Finish();
    socketTypes.close();
    delayEvents.close();
    Simulator::Destroy(); // Closes existing sink app CSV files before reading.

    std::ofstream flowSummary(logsDir + "/flow_summary.csv");
    Require(bool(flowSummary), "Cannot open flow summary");
    flowSummary << "flow_id,sender_node,receiver_node,destination_port,cc,start_ns,observation_end_ns,"
                   "acked_bytes,application_rx_bytes,application_goodput_mbps,last_application_rx_ns,completed\n";
    flowSummary << std::setprecision(17);
    for (uint32_t id = 0; id < sources.size(); ++id) {
        const uint16_t port = uint16_t(1024 + id);
        const auto delivery = ReadAppDelivery(logsDir + "/study_app_rx_node_1_port_" + std::to_string(port) + ".csv", id);
        const int64_t startNs = (id == 0 ? flowStart : competitorStart).GetNanoSeconds();
        const double goodput = double(delivery.bytes) * 8 * 1000 / (endTime.GetNanoSeconds() - startNs);
        flowSummary << id << ",0,1," << port << ',' << (id == 0 ? candidateType : "ns3::TcpCubic") << ','
                    << startNs << ',' << endTime.GetNanoSeconds() << ',' << acked[id] << ','
                    << delivery.bytes << ',' << goodput << ',' << delivery.lastNs << ',' << completed[id] << '\n';
    }
    return 0;
}
