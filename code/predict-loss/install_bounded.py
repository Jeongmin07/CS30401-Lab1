#!/usr/bin/env python3
"""Add opt-in bounded restoration to an exact canonical v6 study tree.

Run inside a fresh official container after applying code/kim-study/ns3.patch.
The exported patch contains both canonical v6 instrumentation and this variant.
No simulation is launched. Existing patch artifacts are never overwritten.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


APP_CC = 'contrib/basic-sim/model/apps/tcp-flow-send-application.cc'
APP_H = 'contrib/basic-sim/model/apps/tcp-flow-send-application.h'
SOCKET_CC = 'src/internet/model/tcp-socket-base.cc'
SOCKET_H = 'src/internet/model/tcp-socket-base.h'
BUFFER_CC = 'src/internet/model/tcp-tx-buffer.cc'
BUFFER_H = 'src/internet/model/tcp-tx-buffer.h'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one source anchor: ' + repr(old[:100]))
    return text.replace(old, new)


def transformed(root):
    result = {}
    text = (root / APP_CC).read_text()
    text = replace_once(text,
        'study_restore_limit_ns=N. Empty parameters retain baseline threshold 3.',
        'study_restore_limit_ns=N;study_bounded_restore=0|1. Empty parameters retain baseline threshold 3.')
    text = replace_once(text,
        'key != "study_restore_limit_ns" && key != "study_short_flow_cutoff_pkts")',
        'key != "study_restore_limit_ns" && key != "study_short_flow_cutoff_pkts" &&\n'
        '                key != "study_bounded_restore")')
    text = replace_once(text,
        '            } else if (key == "study_restore_limit_ns") {',
        '            } else if (key == "study_bounded_restore") {\n'
        '                NS_ABORT_MSG_IF(value != "0" && value != "1",\n'
        '                                "study_bounded_restore must be 0 or 1");\n'
        '                m_studyBoundedRestore = value == "1";\n'
        '            } else if (key == "study_restore_limit_ns") {')
    text = replace_once(text,
        '    const char* enabled = std::getenv("CS30401_STUDY_TRACE");',
        '    NS_ABORT_MSG_IF(m_studyBoundedRestore && m_studyWindows.empty(),\n'
        '                    "Bounded restoration requires timed study windows");\n'
        '    const char* enabled = std::getenv("CS30401_STUDY_TRACE");')
    text = replace_once(text,
        '    ++m_studyActiveWindows;\n    m_studyRestorePending = false;',
        '    if (m_studyBoundedRestore &&\n'
        '        (m_studyEffectiveThreshold <= 3 ||\n'
        '         !m_socket->GetObject<TcpSocketBase>()->CanForecastGuardStart())) {\n'
        '        InsertStudyEvent("FORECAST_GUARD_SKIP", m_studyCurrentThreshold,\n'
        '                         m_studyEffectiveThreshold);\n'
        '        return;\n'
        '    }\n'
        '    ++m_studyActiveWindows;\n    m_studyRestorePending = false;')
    text = replace_once(text,
        '    m_studyRestorePending = true;\n    if (m_studyCongState',
        '    if (m_studyBoundedRestore) {\n'
        '        m_studyRestorePending = false;\n'
        '        m_studyRestoreDeadlineEvent.Cancel();\n'
        '        if (m_studyCurrentThreshold <= 3) return;\n'
        '        SetStudyThreshold(3, "THRESHOLD_RESTORE");\n'
        '        const bool entered = m_socket->GetObject<TcpSocketBase>()\n'
        '            ->ReevaluateLossAfterThresholdRestore();\n'
        '        InsertStudyEvent("BOUNDED_EXPIRY_REEVALUATE", 0, entered ? 1 : 0);\n'
        '        return;\n'
        '    }\n'
        '    m_studyRestorePending = true;\n    if (m_studyCongState')
    text = replace_once(text,
        'void TcpFlowSendApplication::TryRestoreStudyThreshold() {',
        'void TcpFlowSendApplication::ReleaseBoundedGuardAfterRto() {\n'
        '    if (!m_socket || !m_studyBoundedRestore || m_studyActiveWindows == 0 ||\n'
        '        m_studyCurrentThreshold <= 3) return;\n'
        '    // This runs after the original RTO handler; it does not enter recovery.\n'
        '    SetStudyThreshold(3, "THRESHOLD_RTO_RELEASE");\n'
        '    m_studyRestorePending = false;\n'
        '}\n\n'
        'void TcpFlowSendApplication::TryRestoreStudyThreshold() {')
    text = replace_once(text,
        '    InsertStudyEvent("CONG", static_cast<unsigned>(oldState), static_cast<unsigned>(newState));\n'
        '    if (m_studyRestorePending) {',
        '    InsertStudyEvent("CONG", static_cast<unsigned>(oldState), static_cast<unsigned>(newState));\n'
        '    if (m_studyBoundedRestore && newState == TcpSocketState::CA_LOSS &&\n'
        '        m_studyActiveWindows != 0 && m_studyCurrentThreshold > 3) {\n'
        '        m_studyRestoreDeadlineEvent.Cancel();\n'
        '        m_studyRestoreDeadlineEvent = Simulator::ScheduleNow(\n'
        '            &TcpFlowSendApplication::ReleaseBoundedGuardAfterRto, this);\n'
        '    }\n'
        '    if (m_studyRestorePending) {')
    result[APP_CC] = text
    text = (root / APP_H).read_text()
    text = replace_once(text, '  void StudyRestoreDeadline();',
                        '  void StudyRestoreDeadline();\n  void ReleaseBoundedGuardAfterRto();')
    text = replace_once(text, '  bool m_studyRestorePending = false;',
                        '  bool m_studyRestorePending = false;\n  bool m_studyBoundedRestore = false;')
    result[APP_H] = text
    text = (root / SOCKET_H).read_text()
    result[SOCKET_H] = replace_once(text, '    void SetRetxThresh(uint32_t retxThresh);',
        '    void SetRetxThresh(uint32_t retxThresh);\n'
        '    // Narrow helpers for the opt-in forecast-window study.\n'
        '    bool CanForecastGuardStart() const;\n'
        '    bool ReevaluateLossAfterThresholdRestore();')
    text = (root / SOCKET_CC).read_text()
    result[SOCKET_CC] = replace_once(text,
        'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)',
        'bool\nTcpSocketBase::CanForecastGuardStart() const\n'
        '{\n'
        '    return m_sackEnabled && !m_fackEnabled &&\n'
        '           m_tcb->m_congState == TcpSocketState::CA_OPEN &&\n'
        '           m_dupAckCount == 0 && m_txBuffer->GetLost() == 0;\n'
        '}\n\n'
        'bool\nTcpSocketBase::ReevaluateLossAfterThresholdRestore()\n'
        '{\n'
        '    NS_ABORT_MSG_IF(m_retxThresh != 3 || !m_sackEnabled || m_fackEnabled,\n'
        '                    "Bounded restoration requires baseline K3, SACK and no FACK");\n'
        '    // Do not duplicate ECN/RTO/ongoing recovery or manufacture an ACK.\n'
        '    if (m_tcb->m_congState != TcpSocketState::CA_DISORDER) return false;\n'
        '    m_txBuffer->ReevaluateLoss();\n'
        '    const bool dupackLoss = m_dupAckCount >= m_retxThresh &&\n'
        '        (m_highRxAckMark >= m_recover || !m_recoverActive);\n'
        '    if (!dupackLoss && !m_txBuffer->IsLost(m_highRxAckMark)) return false;\n'
        '    // A timer delivers no new bytes: currentDelivered is zero, not a total.\n'
        '    EnterRecovery(0);\n'
        '    SendPendingData(m_connected);\n'
        '    return true;\n'
        '}\n\n'
        'void\nTcpSocketBase::SetRetxThresh(uint32_t retxThresh)')
    text = (root / BUFFER_H).read_text()
    result[BUFFER_H] = replace_once(text, '    void SetDupAckThresh(uint32_t dupAckThresh);',
        '    void SetDupAckThresh(uint32_t dupAckThresh);\n'
        '    // Reuse existing SACK evidence after the study threshold is restored.\n'
        '    void ReevaluateLoss();')
    text = (root / BUFFER_CC).read_text()
    result[BUFFER_CC] = replace_once(text,
        'void\nTcpTxBuffer::UpdateLostCount()',
        'void\nTcpTxBuffer::ReevaluateLoss()\n'
        '{\n'
        '    // Preserve every existing loss/SACK flag and all retransmission state.\n'
        '    if (!m_sentList.empty() && m_highestSack.first != m_sentList.end())\n'
        '    {\n'
        '        UpdateLostCount();\n'
        '    }\n'
        '}\n\n'
        'void\nTcpTxBuffer::UpdateLostCount()')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ns3-root', type=Path, default=Path('/home/ubuntu/ns-3.48'))
    parser.add_argument('--baseline-patch', type=Path, default=Path('/work/code/kim-study/ns3.patch'))
    parser.add_argument('--patch', type=Path, required=True)
    args = parser.parse_args()
    root, baseline, output = args.ns3_root.resolve(), args.baseline_patch.resolve(), args.patch.resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite exported patch: ' + str(output))
    base_bytes = baseline.read_bytes()
    base_paths = re.findall(rb'^diff --git a/[^\n]+ b/([^\n]+)$', base_bytes, re.M)
    base_paths = [p.decode('utf-8') for p in base_paths]
    if not base_paths:
        raise ValueError('Baseline patch has no source members')
    for relative in base_paths:
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Invalid baseline source member: ' + relative)
    git = ['git', '-c', 'core.autocrlf=false']
    subprocess.run(git + ['apply', '--reverse', '--check', str(baseline)], cwd=root, check=True)
    # Intent-to-add is required for canonical new scratch sources in a full diff.
    new_paths = [p for p in base_paths if subprocess.run(
        git + ['ls-files', '--error-unmatch', p], cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0]
    if new_paths:
        subprocess.run(git + ['add', '-N', '--', *new_paths], cwd=root, check=True)
    actual_base = subprocess.check_output(git + ['diff', '--binary'], cwd=root)
    if actual_base != base_bytes:
        raise ValueError('Current ns-3 source is not byte-exact canonical v6 diff')
    outputs = transformed(root)  # Check every anchor before changing any source.
    before = {p: sha(root / p) for p in outputs}
    for relative, content in outputs.items():
        (root / relative).write_text(content, newline='\n')
    subprocess.run(git + ['diff', '--check'], cwd=root, check=True)
    patch = subprocess.check_output(git + ['diff', '--binary'], cwd=root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)
    subprocess.run(git + ['apply', '--reverse', '--check', str(output)], cwd=root, check=True)
    print(json.dumps({'patch': str(output), 'patch_sha256': sha(output),
        'baseline_patch_sha256': sha(baseline), 'baseline_diff_byte_exact': True,
        'ns3_head': subprocess.check_output(git + ['rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'helper_sha256': sha(Path(__file__)), 'changed_sources': sorted(outputs),
        'before_sources': before, 'after_sources': {p: sha(root / p) for p in outputs},
        'canonical_new_sources_included': new_paths,
        'simulations_run': False}, indent=2))


if __name__ == '__main__':
    main()
