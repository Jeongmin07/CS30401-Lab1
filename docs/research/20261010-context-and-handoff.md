# 문헌 조사와 현재 연구의 인수인계

작성: kim-seongchan, AI 보조. 날짜: **2026-10-10**. 기준: [`main` b60e8e0](https://github.com/Jeongmin07/CS30401-Lab1/tree/b60e8e019053c7d33b853510ec06c3d94ee78faf), PR #9 병합 이후.

이 문서는 관련 연구 조사와 그에 따른 **제안**이다. 새 실험을 실행하지 않았으며, 팀 연구 주제·역할·공통 조건을 확정하지 않는다. 합의 상태는 [PLAN](../PLAN.md), 실제 문헌 근거는 [문헌 조사](20261010-leo-tcp-literature.md)에 있다. 이 기록 이후 올라온 PR과 작업 기록도 확인해야 한다.

## 다른 조원의 AI가 알아야 할 맥락

조원 3명이 서로 다른 노트북에서 각자 AI와 작업한다. 다른 채팅이나 실행 중인 실험을 직접 볼 수 없으므로 GitHub에 올라온 코드, 결과, PR, 작업 기록으로 이어 읽는다. 이 PR은 그 공유 자료 중 하나이며, 특정 프롬프트나 도구를 강제하거나 담당 사용자의 지시를 바꾸지 않는다. 사람끼리 합의한 역할을 기준으로 작업한다.

이번 변경은 문헌/인수인계 문서와 README 안내뿐이다. 시뮬레이터 코드, 패치, 기존 결과를 수정하지 않았다. 다른 조원의 기존 결과에 빠진 정보를 일괄 보충하는 작업도 요청 범위가 아니다.

## 과제가 요구하는 연구의 형태

[Handout](../CS30401_26F_Lab1_Handout.pdf)와 [환경 가이드](../CS30401_26F_Lab1_Environment_Guide.pdf)를 기준으로, 문제를 구체적인 조건에서 재현하고 원인·규모를 설명한 뒤 개선안을 같은 조건의 baseline과 비교해야 한다. 필요한 정보의 획득 방법, 가정, 비용, 정확도, 실패 조건을 설명하고 깨끗한 공식 환경에서 재현할 수 있어야 한다. 작은 이득이라도 분석이 명확하면 의미가 있다. 선행 아이디어·텍스트·그림·코드를 사용하면 출처와 우리 기여를 구분한다.

제출은 **10월 13일 23:59 KST**다. 영어 IEEE 형식 보고서는 본문 최대 6페이지(참고문헌/부록 제외)이며, 보고서·README·코드/patch를 제출 형식으로 묶어야 한다. 상세 조건과 발표/설문은 원문을 확인한다. 현재의 영어 보고서 초안은 팀 최종 제출물이 아니다.

공식 ns-3.48/Hypatia 모델은 위성 ISL 경로와 전파 지연이 바뀌지만, 기본적으로 handover outage·무작위 무선 오류·가변 링크 용량을 넣지 않는다. 실제 Starlink access 연구의 실측 손실률이나 재구성 시점의 단절/용량 변동을 그대로 추가하면 별도의 모델 확장과 근거가 필요하다. [모델 및 측정 주의점](../LAB_REFERENCE.md)

## 현재 코드와 결과를 읽는 순서

| 기록 | 확인된 내용 | 주의점 |
| --- | --- | --- |
| [README](../../README.md), [START_HERE](../START_HERE.md) | 위치와 협업 방법 | 최신 PR의 미병합 변경도 확인 |
| [독립 CUBIC 연구](../../code/kim-study/README.md) | 초기 23 + 후속 52 = 75개 case ID, v6 patch, 분석/그림/초안 | 팀이 승인한 최종 주제가 아님. 회귀용 중복도 있어 75개 독립 조건/seed 표본이 아님 |
| [v6 재현 기록](../../code/kim-study/evidence/reproduction_v6.json) | 공식 이미지의 fresh volume에서 전체 75-case replay 및 분석 hash 일치가 기록됨 | 이번 문헌 조사에서 재실행한 결과가 아님. 그림 파일의 byte 일치 주장도 아님 |
| [q75 기록](../experiments/20261010-cubic-q75.md) | 새 q75 네 조건과 q100 두 조건의 별도 replay | 해당 작업의 기존 patch를 변경하지 않음 |
| [shared-results](../../shared-results/) | BBR/CUBIC/NewReno/Vegas × q100/q1000, 200초·100 Mbit/s 탐색 | 주로 10 Mbit/s인 독립 연구와 같은 조건으로 합쳐 비교하면 안 됨 |
| [김성찬 작업 기록](../work/kim-seongchan.md), [정민 작업 기록](../work/Jeongmin07.md) | 각 작업의 진행·남은 일 | 오래된 항목 뒤에 갱신 기록이 있음. 기록만으로 지금 실행 중이라고 단정하지 않음 |

큰 raw trace는 다른 노트북에서 보이는 GitHub 파일이 아니다. 기존 [재현 명령](../../code/kim-study/README.md) 또는 [q75 재현 명령](../experiments/20261010-cubic-q75.md)으로 생성하거나, 접근 가능한 공유 아카이브를 따로 연결해야 한다. 로컬 container 경로만 제시하는 것은 공유 링크가 아니다.

## 구현을 정확히 설명하면

26.2초 부근 서울–런던 경로 변경에서 뒤의 data가 먼저 도착하고, course CUBIC/SACK/PRR의 packet-count 손실 판단이 회복을 시작하는 사건이 패킷 단위로 검증됐다. 현재 실험은 알려진 전환 시각 부근에서 **K=3→20 같은 손실 판단 임계값 변경**을 요청한다. CUBIC의 윈도 성장 공식을 바꾸는 패치가 아니다. [원인과 초기 비교](../../code/kim-study/EXPERIMENT_NOTE.md)

복구 상태에 따라 실제 K 복원 시각이 요청한 guard 끝보다 늦어질 수 있다. `SetRetxThresh` 호출 자체가 새 ACK 없이 손실 재평가나 재전송을 실행하는 것도 아니다. 크기 예외는 연결 전에 알려진 **총 전송량 ≤21 nominal MSS**인 경우 guard를 쓰지 않는다. 남은 flight/ACK 수에 따른 동적 제어가 아니고, 실제 마지막 packet 손실의 baseline timeout을 해결하지 않는다. [후속 실험](../../code/kim-study/PHASE2_NOTE.md), [기존 선행연구/구현 해석](../../code/kim-study/RELATED_WORK_NOTE.md)

이는 NCR/RACK/SaTCP 구현이 아니다. 알려진 시뮬레이션 시각을 쓰므로 현실의 알림 획득·전달은 아직 구현되지 않았다. 이미 수행한 offset 비교는 **guard 구간 양끝을 이동한 실험**이며, 네트워크 알림 메시지의 지연/누락을 모델링한 것이 아니다.

## 결과가 뒷받침하는 범위

| 관측 | 해석할 수 있는 범위 |
| --- | --- |
| 10 Mbit/s, q100: 첫 2.5초 event goodput **+1.4432%**, spurious retransmission 3→0, recovery 1→0 | 특정 사건의 불필요한 회복을 줄임. 200초 전체는 **+0.02256%**로 작음 |
| q50: 전체 goodput 약 **−0.366%**; q100에서는 continuous-high-K의 전체 goodput이 selective guard보다 조금 높음 | 모든 큐에서 이득, selective가 항상 우월하다는 주장 불가 |
| 20 MSS 첫 data 손실: baseline **0.251509920 s**, K20 **1.150124001 s**, K8 **0.350482400 s** | K8은 측정된 비용을 줄이지만 baseline보다 약 99 ms 느림. 크기 예외는 이 조건의 baseline을 보존 |
| 크기 예외 21/22 MSS 경계와 last-packet-loss controls 완료 | cutoff가 최적이라는 증거도, 모든 작은 flow가 개선된다는 증거도 아님 |
| q75: 첫 event **+3.0747%**, 전체 **−0.1997%**, receiver bytes **474,720 감소** | event 이득 뒤의 손해를 추적할 근거. first-only와 both의 **표시된 집계 값**은 같지만 raw trace 동일성을 뜻하지 않음 |

앞의 네 행은 [기존 독립 연구](../../code/kim-study/README.md), 마지막 행은 [별도 q75 기록](../experiments/20261010-cubic-q75.md)에서 가져왔다. 합쳐서 통계적 일반화나 실제 Starlink/Linux 개선을 주장하지 않는다. synthetic 80-MSS delay-step의 FCT 감소도 whole-run LEO throughput 증가와 별개의 결과다.

## 문헌을 더 읽어서 얻은 판단

관련 연구는 이미 풍부하다. **재정렬 자체를 처음 발견했다거나 임계값을 올리는 원리를 처음 제안했다는 설명은 피해야 한다.** 현재 코드에 맞는 잠정 주제는 다음과 같다.

> 제공된 LEO CUBIC/SACK/PRR 모델에서 경로 정보를 이용한 일시적 재정렬 허용이 언제 도움이 되며, 실제 손실·작은 전송·큐 조건에서는 어떤 복구 비용을 만드는가?

이는 제안이며 팀 승인 주제가 아니다. [Hypatia/재정렬 연구와 RFC](20261010-leo-tcp-literature.md#papers-read)는 원리를 설명하고, [SaTCP/SatPipe](20261010-leo-tcp-literature.md#p4-satcp)는 필요한 정보와 모델 차이를 드러낸다. [실측 및 simulator/emulator 비교](20261010-leo-tcp-literature.md#p6-tcp-congestion-control-performance-over-starlink)는 transient/전체 성능·경쟁·구현 버전을 함께 평가해야 할 이유를 제공한다.

논문의 평균 gain이나 조건을 살짝 바꾸는 것만으로는 질문이 뚜렷해지지 않는다. **다른 결과를 예측할 수 있는 가설과 이를 구별하는 control**을 먼저 정하는 편이 좋다. 새 프로토콜 전체를 급히 port하기보다 현재의 제한·반례를 설명하는 편이 제출일까지 검증 가능한 범위다.

## 다음 작업 후보: 이미 한 일과 겹치지 않게

아래는 선택 가능한 후속 작업이다. 새 역할 배정이나 모두 수행해야 하는 checklist가 아니다.

| 우선순위/질문 | 구체적으로 확인할 것 | 완료라고 볼 근거와 중복 주의 |
| --- | --- | --- |
| **1. q75 후반 손해의 원인** | 28.2초 이후 baseline/first-only의 누적 receiver-byte 차이를 먼저 좁히고 해당 packet/drop/ACK/recovery를 추적. 보호 요청/실제 복원 시각도 대조 | 어떤 사건이 deficit을 만들고 지속시키는지 재현 가능한 trace로 설명. [정민의 남은 일](../work/Jeongmin07.md)에 이미 있으므로 현재 진행 여부부터 확인하고 중복 배정하지 않음 |
| **2. 공유 병목에서 부작용** | 같은 병목을 실제로 통과하는 두 flow: default/default 대 guarded/default 비교. flow별 delivered bytes, RTT, 손실/회복, Jain fairness; 시작 순서도 기록 | 단일 flow 이득이 상대 flow에 비용을 전가하는지 확인. 두 flow를 만들기만 하고 경로가 다른 실험은 답이 되지 않음. 구현 난도가 크면 다음 후보 선택 |
| **3. 작은 추가 일반화 한 가지** | 두 번째 도시쌍/전환 또는 추가 finite-flow K8 조건 중 하나를 선택. 각 조건에 맞춘 baseline 및 필요한 genuine-loss/no-loss control 유지 | 한 경로 또는 20-MSS K8 한 점에 대한 의존을 확인. 기존 K8/K20/K32 bulk·3/4/8/20/21/22/80-MSS matrix·첫/중간/마지막 손실·delay-step·6개 nonzero offset은 이미 수행됐으므로 새 실험으로 다시 소개하지 않음 |
| **병행 가능: 제출물 정리** | 확정된 주제에 맞는 보고서 claim/그림/참고문헌, 팀 저자, canonical patch 하나, clean replay와 figure/table mapping 확인 | 사람이 연구 범위를 합의한 뒤 최종화. 이번 PR은 문헌 조사만 했으며 제출물 검증 완료를 뜻하지 않음 |

시간이 부족하면 1번과 제출물 정리에 집중해도 연구의 인과 설명은 강해진다. 2/3번 중 하나는 여유와 구현 가능성에 따라 고르면 된다. q75/q50 음수 결과를 숨기고 평균 이득을 크게 보이는 조건만 고르는 방식은 권하지 않는다.

팀이 CUBIC 방향을 선택하지 않는다면 [Vegas-A](20261010-leo-tcp-literature.md#p10-tcp-vegas-a)를 참고해 base RTT·전파 지연 변화와 큐 지연을 분리하는 대안이 있다. 기존 Vegas 평균만으로 원인을 확정하거나, 현재 최종 주제가 결정됐다고 간주하지 않는다.

## 이 PR을 각자의 AI에게 전달하는 방법

친구가 자기 AI에 **PR 링크와 원하는 검토 범위**를 주면 된다. 별도 에이전트 통신 시스템이나 고정 프롬프트는 필요 없다. PR 설명만 읽으면 본문 근거를 놓칠 수 있으므로 새 문서 두 개와 필요한 기존 실험 기록도 읽게 하는 것이 좋다.

검토할 내용은 현재 자기 작업과 겹치는 부분, 재사용 가능한 코드/결과, 틀린 해석이나 빠진 조건, 추가로 할 만한 검증이다. 의견을 팀에 공유할 때는 발견한 근거 파일/commit과 미확인 사항을 같이 남기면 된다. 읽으라는 요청이 자동으로 코드 수정·다른 브랜치 push·PR merge를 뜻하지 않는다. 새 관측은 자신의 작업 기록/PR에, 합의된 결정은 PLAN에 반영한다.
