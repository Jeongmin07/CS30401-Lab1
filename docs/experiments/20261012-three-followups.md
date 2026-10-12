# 세 가지 예측 제어 후보의 제한된 후속 검증

2026-10-12, kim-seongchan. 사용자가 [고찰](../research/20261012-progress-retrospective.md)의 세 후보를 진행하도록 승인했다. CUBIC 확대와 축소는 문제의 전제를 빠르게 확인하고 근거가 없으면 중단한다. 선택적 손실 대기는 구현과 실제 손실 비용까지 검증한다. 팀 최종 주제와 다른 조원의 역할을 확정하는 기록은 아니다.

| 담당 | 후보 | 소유 범위 | 첫 확인과 중단 기준 |
| --- | --- | --- | --- |
| 내부 audit_research_handoff | 경로 연장 시 CUBIC 선제 확대 | code/orbit-cubic-up 및 독립 실험 기록 | 기존10Mbps와 자연100Mbps/q100/200초에서121.6·187.4초의 cwnd 제한과 병목 유휴를 연결. 윈도우가 충분하거나 다른 원인이면 정책 없이 중단 |
| 내부 review_cubic_study | 경로 단축 시 CUBIC 선제 축소 또는 pacing | code/orbit-cubic-down 및 독립 실험 기록 | 기존자료와 위100Mbps 관측 원본을 공유해26.2·75초의 forward queue surge/drop을 확인. 재정렬만 있고 큐 원인이 없으면 정책 없이 중단 |
| 내부 review_baselines_and_handoff | 선택적 손실 대기와 짧은 타이머 | code/orbit-loss 및 독립 실험 기록 | K3/SACK/PRR을 유지하며 전환 영향 후보와 손실 의심 시각에 연결한 유한 대기. 기존 보호 대비 실제 손실 추가 지연까지 비교 |
| 이 채팅 root | 방향별 기하와 결과 통합 감사 | code/orbit-geometry 및 이 공통 기록 | 기존 state delta와 두 endpoint 경로만 사용. forward/reverse를 분리하고 전체 위성 쌍의 새 토폴로지를 생성하지 않음 |

첫100Mbps passive CUBIC 원본은 확대 담당의 별도 공식 volume에서 한 번 실행하고 축소 담당과 공유한다. 정책·source·runtime은 실행 도중 바꾸지 않는다. 후보별 별도 source volume, CPU2·메모리4GiB·build1job, 실행별240초 wall cap을 출발 예산으로 사용한다. 최초 simulation 전에 이 선언과 각 소유 범위의 계획을 GitHub에 공유한다.

확대·축소의 gate가 통과할 경우만 각각 같은 조건의 정책ON 최대1회와 필요 실제손실micro1회를 추가한다. 조건을 성공할 때까지 탐색하거나 RTT를 인위적으로두배 늘리지는 않는다. observer-off와 baseline 동등성, 실제 정책 작동, 설정/source/runtime/input/output 해시와 실제 수신량을 보존한다.

손실 대기의 출발 규칙은 전환 epoch 동안 이미 송신한 미확인 패킷 중 재전송·기존 loss가 아닌 같은 old-flight cohort 후보들을 보호하는 것이다. loss marking과 socket의 복구 진입을 일관되게 다루고, 첫 손실 의심 증거에서 기하 기반의 짧은 timer를 시작한다. 여러 후보 hole은 하나의 episode deadline을 공유하며 head가 이동해도 기한을 연장하지 않는다. 정방향 지연 감소가 1ms 이상인 전환만 선택하며 대기시간은 `clamp(2×정방향 전파 지연 감소, 1ms, 20ms)`를 사전 후보값으로 사용한다. 패킷 허용량은 명목 흐름률과 정방향 감소의 곱에서 구한 예산이며 정확한 최대 추월 상한이라고 부르지 않는다. epoch의 폭과 episode 대기시간은 구분한다. 기본 RTO와 SACK/PRR 정보는 유지하며 cohort 밖의 실제 손실·기존 복구가 시작되면 보호를 중단한다.

처음 선언의 head-only 최소 구현은 첫 실행 전 소스 검토에서 수정했다. 기존 26.2초 SACK는 세 old-flight hole을 동시에 표시하며, TxBuffer가 뒤쪽 hole들을 먼저 loss로 표시하므로 head만 보호하면 확인된 문제에 개입할 수 없다. 새 성능 결과를 보고 범위를 확대한 것이 아니라 이미 공유된 packet 증거로 이 구조적 문제를 확인한 수정이다.

손실 후보의 최초 출발 집합은 같은 LEO10 원본·기존 bounded K20·새 정책3회, stable20MSS 실제 첫 손실 원본·새 정책의 잘못된 positive hint2회, 실제 경로 단축 시점에 명시적으로 주입한 old-flight 실제 손실 원본·새 정책2회까지 최대7회다. 실제 손실 선택 규칙은 시각·전송 조건으로 미리 정하고 미래 실행에서 유리한 sequence를 고르지 않는다. 구현 검토에서 안전한 소스 경로나 입력 가정이 바뀌면 첫 실행 전 수정 사유를 기록한다.

전체 및 고정 전환창의 앱 수신 goodput, 재정렬·재전송·복구, 장치 큐·drop, 실제 손실 복구 시각과 유한 흐름 완료 시간을 후보에 맞춰 평가한다. drop hook과 고유 손실, SRTT와 직접 queue wait를 구별한다. 읽기 진단·미구현 중단·실제 작동·실행 실패를 구분하고 실패·timeout 부분 결과는 성능 분석에서 제외한다.

완료 결과와 원본 위치는 다음에 추가한다. 이 시작 선언에는 새 성능 수치가 없다.
