# 선택적인 짧은 SACK 손실 대기

2026-10-12, kim-seongchan. 이 문서는 실행 전 선언이다. 아직 결과가 없다. 사용자가 승인한 세 후보 중 세 번째이며, 별도 공식 ns-3 volume에서 개발·실행한다. 기본 CUBIC/SACK/PRR의 손실 문턱 K3와 RTO를 유지한다.

## 질문과 최소 구현

확인된 26.2초 허위 복구를 줄이되, 기존 bounded K20보다 실제 손실의 추가 대기를 줄일 수 있는가? 경로 전환 T에 송신자가 아직 확인받지 못한 sequence 범위를 등록한다. 등록 당시 송신된 원본이고 lastSent≤T인 범위만 잠재적인 old-flight 대상으로 취급한다. 이는 실제 패킷의 남은 경로를 안다는 뜻이 아니다.

첫 소스 검토에서 head만 보호하려 했으나, 기존 26.2초 증거의 SACK가 head를 포함한 세 old-flight hole을 함께 손실로 표시함을 확인했다. 뒤에서 head로 순회하는 구현에서 나머지 두 hole을 먼저 표시하면 head 보호는 시작할 수 없다. **첫 시뮬레이션 전 이 구조를 수정해, 동일 old-flight cohort의 eligible holes를 하나의 episode deadline으로 보호한다.** 기본 SACK 정보·delivered accounting은 계속 갱신하고 손실 표시 직전에 처음 의심된 eligible hole부터 짧은 deadline을 부여한다. 다른 eligible head로 이동하거나 후속 SACK가 와도 deadline을 연장하지 않는다. cohort 밖 패킷의 기본 K3 손실 표시나 ECN/기존 recovery/RTO가 발생하면 보호를 해제하고 기본 복구로 돌아간다. 이미 표시된 loss를 지우거나 PRR의 pipe 값을 가짜로 줄이지 않는다. 등록과 대기는 소켓별로 독립적이다.

등록 유효기간은 기존 비교와 동일한 T~T+2×max(old,new propagation RTT)다. 실제 대기는 첫 손실 의심 시각부터 `τ=clamp(2×forward propagation decrease,1ms,20ms)`이며 등록 종료를 넘기지 않는다. 대상 수신을 확인하는 ACK/SACK 또는 deadline에서 보호를 해제하고 기존 증거를 재평가한다. 추가 ACK 없이 stock recovery에 진입할 수 있도록 기존 bounded 복원의 원칙을 재사용한다.

## 예측 입력과 고정 규칙

입력은 [방향별 기하](../../code/orbit-geometry/forward-hints.csv)다. old/new 경로를 같은 T에서 계산하고, forward가 바뀌며 편도 전파 지연이 **1ms 이상 감소한 두 전환(26.2/75초)**만 선택한다. 미래 패킷 trace나 FCT를 입력으로 쓰지 않는다. 운영자가 정확한 routing·전환 시각을 알려 주는 oracle 조건이고 메시지 전달·시각 오차는 구현하지 않는다.

SACK 규모 예산은 `3+ceil(Rbit/s×forward_drop_s/(8×MSSbytes))`다. R은 해당 조건에 미리 선언한 링크 속도이며 실제 순간 송신률이나 정확한 추월 상한으로 부르지 않는다. 이 예산을 넘으면 대기를 끝내고 기본 K3 표시/복구를 허용한다. CUBIC은 현재 pacing이 꺼져 있고 큐·burst·역방향 ACK 전달은 이 기하 예산만으로 예측되지 않는다.

## 사전 실행 집합과 중단

최종 성능 표는 동일 V2 source/runtime의7조건이며 각240초 wall cap이다. 아래 peer review 보수 전에 이미 완료한 V1 micro2는 예비 자료로 보존하며 최종 표와 합산하지 않는다. 전체9attempt(예비2+최종7) 범위다. 짧은 micro를 먼저 검증한다. 기본 문턱 유지, 실제 타이머·SACK/dupACK invariant·pipe accounting과 종료 시 복구를 확인하지 못하면 긴 실행을 시작하지 않는다.

1. stable micro 100Mbps·q2000·편도50→50ms·4초·20MSS(27,600B)의 첫 segment 실제 손실: baseline/새 selective 두 조건. 정책에는 일부러 0.15~0.35초의 잘못된 positive hint와 26.2초와 같은 forward 감소 예산을 준다. Δ=0을 알아 보호를 생략하는 방식으로 안전 비용을 숨기지 않는다.
2. 제공 LEO 10Mbps·q100·200초 단일100GB: baseline/기존 bounded K20/새 selective 세 조건. 전체와 `[25.7,28.2)`, `[74.5,77.0)`의 앱 고유 수신량·재전송/복구/실제 drop과 정책 이벤트를 비교한다.
3. 같은 LEO 경로 단축 중 원본 old-flight의 실제 tagged drop을 정확히 하나 주는 baseline/selective 두 조건. 대상 선택은 T·원본 송신 시각·flow/sequence 조건으로 실행 전에 고정하며 미래 실행 결과로 좋은 패킷을 고르지 않는다. 주입 규칙과 실제 선택된 tag를 모두 기록한다.

cohort 밖 hole의 기본 손실 표시가 보호를 해제할 수 있다. 그런 경우 작동하지 않은 범위와 실제 효과를 그대로 보고하며 결과에 맞춰 hole 범위·τ·예산을 확대하지 않는다. 실패/timeout/소스 불일치는 보존하고 성능 표에서 제외한다. 큰 처리량 이득이나 모든 실제 손실의 추가 대기0을 가정하지 않는다.

## 실행·재현 계획

새 container `lab1-orbit-loss-20261012`, 새 volume `cs30401-orbit-loss-ns3-20261012`, CPU2·4GiB, build1job. 공식 이미지 digest는 `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`다. 다른 후보나 기존 predict-loss volume은 수정하지 않는다. combined patch·실행 commit/dirty flag·runtime/input/output SHA·상태·명령과 실제 app delivery/FCT/정책 대기·복구 비용을 남긴다. 대용량 원본은 별도 압축과 member hash를 보존하고 작은 evidence만 Git에 둔다. 통계적 반복이나 현대 Linux RACK 구현의 성과로 일반화하지 않는다.

### 긴 실행 전 peer review 보수

V1 micro 두 조건은 `e8cea96`의 source에서 완전히 수신·한 실제 drop·한 재전송을 확인했다. shared wait는 정확6.631518ms였으나 FCT는0.251509920→0.350482400초였다. 짧은 재전송 지연도 PRR/ACK 시점을 바꾸어 남은 새 데이터의 전송을 다음 RTT까지 늦출 수 있다. 이 결과를 본 뒤 τ·packet budget을 튜닝하지 않았다.

별도 소스 검토에서 cumulative ACK 뒤 상태가 OPEN으로 돌아간 경우 deadline의 loss flag 재평가만 하고 송신을 깨우지 않을 가능성을 발견했다. 이는 관측된 실행 실패가 아니라 정확성 경계다. V2는 deadline과 registration End가 공통 재평가를 사용한다. OPEN에서는 **실제 저장된 head loss flag**가 있을 때만 DISORDER를 거쳐 기본 `EnterRecovery(0)`/`SendPendingData`로 진행한다. 가짜 ACK·dupACK count·cwnd 값을 만들지 않는다. DISORDER의 기본 증거 재평가와 RTO는 유지한다. registration End가 같은 시각의 deadline timer보다 먼저 실행돼도 대기를 넘기지 않는다.

V1 patch/readiness/micro 원본·예비 요약을 보존하고, 별도 V2 patch/readiness/source checkpoint에서 최종7조건을 실행한다. 이 보수는 새 성능에 맞춘 규칙 변경이 아니다. 해당 OPEN 분기가 실제 실행에서 나타나지 않으면 실행 검증된 경계라고 부르지 않는다. 공식 build의 `NS3_ASSERT=OFF`도 기록하며 단순 실행 성공을 디버그 assertion 검증으로 쓰지 않는다.
