# 예측 경로 구간의 손실 판정과 제한된 복원

2026-10-12, kim-seongchan, [PR16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16). **실행 전 선언이며 결과는 후속 commit에 추가한다.** 송신 pause/pacing 후보를 우선 제외하고, 기존 K8/K20 정책을 재사용하면서 예측 구간 계산과 종료 시 손실 재평가를 검증한다. 큰 처리량 개선을 가정하지 않는다.

## 질문과 구현 범위

제공 CUBIC/SACK/PRR에서 경로 단축을 예고받아 일시적으로 손실 판정 문턱을 높이면 불필요한 복구를 줄일 수 있는가? 기존 정책의 복원 지연을 없애는 작은 변경으로 실제 손실의 긴 기다림을 줄일 수 있는가?

기존 K8/K20도 이미 전환 주변의 notified window 방식이었다. 이번에 새로 검증할 것은 **기하에서 선택한 전환/구간 + 구간 종료 시 threshold 복원과 기존 SACK/dupACK 증거 재평가**다. 송신 속도·CUBIC 성장식을 바꾸지 않으며, 알림의 정확성·진짜 손실·현재 복구 구현의 한계를 명시한다. 현대 Linux RACK 구현이나 동작 비교는 추가하지 않는다.

canonical v6 관측/benchmark를 새 공식 volume에 적용하고 추가 patch를 합쳐 하나의 `code/predict-loss/ns3.patch`로 내보낸다. opt-in `study_bounded_restore=1`일 때만 새 종료 처리를 사용하고 기본 off는 기존 v6 동작을 유지한다. CA_OPEN·dupACK 0·알려진 loss 없음·SACK on/FACK off에서만 보호 시작을 허용한다. RTO를 정지하지 않으며 종료 때 기존 손실 증거를 버리거나 가짜 ACK를 만들지 않는다. 구간이 끝났다고 단순히 K를 3으로 내리면 남은 dupACK 수로 assertion/손실 복구 누락이 생길 수 있어 core 재평가가 필요하다.

## 예측 정보와 미리 정한 규칙

- 입력은 기존 `code/kim-study/path_truth_200s.csv`의 공급 state 기하 정보다. 실행 결과의 패킷 시각을 정책 입력으로 쓰지 않는다. 공개 궤도만으로 실제 경로를 안다는 주장이 아니라, routing을 계획하는 운영자의 정확한 미래 힌트 조건이다.
- path_changed이고 전파 RTT가 감소하는 전환만 선택한다. 보호 시작은 전환 T, 기간 H는 `2×max(이전, 이후 전파 RTT)`로 정한다. 26.2초에서는 195.396ms다. 이는 큐를 포함한 최대 도착시간 보장이 아닌 **선언한 후보 규칙**이다.
- 문턱 20은 피드백과 기존 연구를 이어 보는 고정 진단값이다. 100Mbps에서는 기존 문턱64를 추가 대조로 미리 선언한다. 큰 문턱이 최적이거나 혼잡 반응을 보존한다는 가정은 하지 않는다.
- 정확한 시각과 300ms 늦은 알림을 비교한다. 운영자 메시지 전달 프로토콜은 구현하지 않는다. 구간 종료 후 안전하게 K3 복원이 실행됐는지 실제 이벤트로 확인한다.

## 선언한 실행 집합과 예산

1. stable micro: 100Mbps·q2000·편도50ms·4초·20MSS(27,600B). 첫 segment 실제 손실은 baseline/기존 window/new bounded를 비교하고, 중간 segment 실제 손실은 baseline/bounded를 비교한다. false hint 구간은 0.15–0.35초다. 총5개로 종료 재평가가 추가 ACK 없이 동작하는지, finite FCT/RTO 비용을 확인한다.
2. LEO: 10Mbps·q100·200초, 단일100GB CUBIC. baseline/정확한 forecast20/300ms late 세 개. 기존 고정 평가창 `[25.7,28.2)`, `[74.5,77.0)`과 전체 goodput·실제 수신량·복구/재전송·drop을 함께 본다. 새 baseline raw는 기존 v6 기록과 대조한다.
3. 위 두 검증이 정상 완료되면 100Mbps·q1000·40초 baseline/forecast20/forecast64 세 개만 확인한다. full 200초 결과로 부르지 않는다. 큐와 용량은 Guide 예제와 기존 high-rate study를 따른 출발점이며 실측 Starlink 값이 아니다.

실행은 하나씩, 각180초 wall cap이다. timeout/오류이면 batch를 중단하고 부분 결과는 성능 표에서 제외한다. 새로운 토폴로지나 대규모 sweep을 생성하지 않는다. 새 container `lab1-predict-loss-20261012`, volume `cs30401-predict-loss-ns3-20261012`, CPU4/6GiB. 이미지 digest는 이전 진단과 같은 공식 `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`다.

## 평가와 중단

앱의 유일한 순서대로 전달된 바이트를 goodput으로 쓰고 sender ACK progress와 섞지 않는다. 재전송 감소 자체를 큰 처리량 개선으로 바꾸어 쓰지 않는다. finite flow는 전체27,600B 수신 후 FCT를 계산한다. 실제 손실 복구 지연·경계 종료·skip·RTO를 함께 확인한다.

Guide의 cwnd/SRTT 그래프는 PDF9쪽이며 10쪽 globe에도 Figure3 번호가 중복된다. 5.4초 그래프 모양만으로 경로 단축·재정렬·허위 복구를 입증할 수 없다. 확인된 26.2초 패킷 증거를 출발점으로 쓰며 가설을 만족하도록 전환·큐를 크게 바꾸지 않는다.

효과가 작으면 그 크기를 그대로 보고한다. epoch가 끝나도 high threshold가 남거나 실제 손실이 RTO까지 부당하게 지연되면 구현을 수정하고 검증 전 성과로 공유하지 않는다. 결과 원본·실행 commit·patch/runtime/input/output hash와 명령은 기록 후 PR에 공유한다.
