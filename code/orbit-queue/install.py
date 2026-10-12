"""Compose final loss V2 with observation-only queue and flow-control hooks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
BASE_SHA='531bf802984af821afd928fb3932912aca383fcdec5771f30f78d75a806d5591'


def once(text,old,new):
    if text.count(old)!=1: raise ValueError('Ambiguous anchor: '+old[:100])
    return text.replace(old,new)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/home/ubuntu/ns-3.48'))
    p.add_argument('--out',type=Path,default=HERE/'ns3.patch')
    a=p.parse_args();r=a.root
    git=['git','-c','core.autocrlf=false']
    if a.out.exists():raise ValueError('Output exists')
    base=REPO/'code/orbit-loss/ns3.patch'
    if hashlib.sha256(base.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Base artifact changed')
    scratch=['scratch/main_satnet/study_drop_trace.h','scratch/main_satnet/old_flight_drop.h','scratch/study_micro/study_micro.cc']
    if subprocess.check_output(git+['diff','--binary'],cwd=r)!=base.read_bytes():
        if subprocess.check_output(git+['status','--porcelain'],cwd=r).strip():raise ValueError('Expected clean official source or exact base')
        subprocess.run(git+['apply','--check',str(base)],cwd=r,check=True)
        subprocess.run(git+['apply',str(base)],cwd=r,check=True)
        subprocess.run(git+['add','-N',*scratch],cwd=r,check=True)
    if subprocess.check_output(git+['diff','--binary'],cwd=r)!=base.read_bytes():raise ValueError('Base diff mismatch')
    qh=r/'src/network/utils/net-device-queue-interface.h';s=qh.read_text()
    s=once(s,'    virtual bool IsStopped() const;', '''    virtual bool IsStopped() const;
    // Opt-in read-only instrumentation. The original state decisions remain unchanged.
    void SetOrbitObserver(Callback<void,std::string,bool,bool,bool,bool,bool> cb) { m_orbitObserver=cb; }
    bool IsOrbitStoppedByDevice() const { return m_stoppedByDevice; }
    bool IsOrbitStoppedByLimits() const { return m_stoppedByQueueLimits; }
    void ObserveOrbit(const char* reason,bool oldDevice,bool oldLimits,bool wake) {
        if(!m_orbitObserver.IsNull() &&
           (oldDevice!=m_stoppedByDevice || oldLimits!=m_stoppedByQueueLimits))
            m_orbitObserver(std::string(reason),oldDevice,oldLimits,m_stoppedByDevice,m_stoppedByQueueLimits,wake);
    }''')
    s=once(s,'    bool m_stoppedByDevice;', '    Callback<void,std::string,bool,bool,bool,bool,bool> m_orbitObserver;\n    bool m_stoppedByDevice;')
    qh.write_text(s,newline='\n')
    qc=r/'src/network/utils/net-device-queue-interface.cc';s=qc.read_text()
    s=once(s,'    m_stoppedByDevice = true;', '    const bool oldDevice=m_stoppedByDevice;\n    m_stoppedByDevice = true;\n    ObserveOrbit("DEVICE_STOP",oldDevice,m_stoppedByQueueLimits,false);')
    s=once(s,'    NS_LOG_FUNCTION(this);\n    m_stoppedByDevice = false;', '    NS_LOG_FUNCTION(this);\n    const bool oldDevice=m_stoppedByDevice;\n    m_stoppedByDevice = false;\n    ObserveOrbit("DEVICE_START",oldDevice,m_stoppedByQueueLimits,false);')
    s=once(s,'    bool wasStoppedByDevice = m_stoppedByDevice;\n    m_stoppedByDevice = false;', '    bool wasStoppedByDevice = m_stoppedByDevice;\n    m_stoppedByDevice = false;\n    ObserveOrbit("DEVICE_WAKE",wasStoppedByDevice,m_stoppedByQueueLimits,\n                 wasStoppedByDevice && !m_wakeCallback.IsNull());')
    s=once(s,'    m_stoppedByQueueLimits = true;', '    const bool oldLimits=m_stoppedByQueueLimits;\n    m_stoppedByQueueLimits = true;\n    ObserveOrbit("BQL_STOP",m_stoppedByDevice,oldLimits,false);')
    s=once(s,'    m_stoppedByQueueLimits = false;\n    // Request', '    m_stoppedByQueueLimits = false;\n    ObserveOrbit("BQL_WAKE",m_stoppedByDevice,wasStoppedByQueueLimits,\n                 wasStoppedByQueueLimits && !m_wakeCallback.IsNull());\n    // Request')
    qc.write_text(s,newline='\n')
    th=r/'src/traffic-control/model/traffic-control-layer.h';s=th.read_text()
    s=once(s,'    static TypeId GetTypeId();', '''    static TypeId GetTypeId();
    void SetOrbitDropObserver(Callback<void,Ptr<NetDevice>,uint32_t,Ptr<const Packet>,bool,bool> cb)
    { m_orbitDropObserver=cb; }''')
    s=once(s,'    TracedCallback<Ptr<const Packet>> m_dropped;', '    Callback<void,Ptr<NetDevice>,uint32_t,Ptr<const Packet>,bool,bool> m_orbitDropObserver;\n    TracedCallback<Ptr<const Packet>> m_dropped;')
    th.write_text(s,newline='\n')
    tc=r/'src/traffic-control/model/traffic-control-layer.cc';s=tc.read_text()
    s=once(s,'            m_dropped(item->GetPacket());', '''            if(!m_orbitDropObserver.IsNull()) {
                auto q=devQueueIface->GetTxQueue(txq);
                m_orbitDropObserver(device,uint32_t(txq),item->GetPacket(),
                                    q->IsOrbitStoppedByDevice(),q->IsOrbitStoppedByLimits());
            }
            m_dropped(item->GetPacket());''')
    tc.write_text(s,newline='\n')
    main=r/'scratch/main_satnet/main_satnet.cc';s=main.read_text()
    s=once(s,'#include "old_flight_drop.h"','#include "old_flight_drop.h"\n#include "queue_observer.h"\n#include "service_observer.h"\n#include "flow_observer.h"')
    s=once(s,'    InstallOrbitOldFlightDrop(topology->GetNodes());','    InstallOrbitOldFlightDrop(topology->GetNodes());\n    orbitqueue::Install(topology->GetNodes());\n    orbitqueueservice::Install(topology->GetNodes());\n    orbitqueueflow::Install(topology->GetNodes());')
    main.write_text(s,newline='\n')
    for name in ['queue_observer.h','service_observer.h','flow_observer.h']:
        target=r/'scratch/main_satnet'/name
        target.write_text((HERE/name).read_text(),newline='\n')
        subprocess.run(git+['add','-N',str(target.relative_to(r))],cwd=r,check=True)
    subprocess.run(git+['diff','--check'],cwd=r,check=True)
    data=subprocess.check_output(git+['diff','--binary'],cwd=r)
    a.out.write_bytes(data)
    subprocess.run(git+['apply','--reverse','--check',str(a.out)],cwd=r,check=True)
    print(json.dumps({'base_sha256':BASE_SHA,'patch_sha256':hashlib.sha256(data).hexdigest(),'ns3_head':subprocess.check_output(git+['rev-parse','HEAD'],cwd=r).decode().strip()}))


if __name__=='__main__':main()
