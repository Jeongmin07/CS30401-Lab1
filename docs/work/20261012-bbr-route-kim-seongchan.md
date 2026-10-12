# 현대 TCP 진단과 예측 정보 활용 후보 — 2026-10-12

- 담당: kim-seongchan의 이번 채팅. 조원 3명이 각자 사용하는 AI는 GitHub에 공유된 정보를 읽으며 자동 메시지 시스템을 가정하지 않는다.
- 브랜치 / PR: `research/bbr-route-transition`, [Draft PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16).
- 기준: `main` `b60e8e019053c7d33b853510ec06c3d94ee78faf`.
- 범위: 연구 방향 재검토·PR 공유·비용 제한 진단. 다른 조원의 코드/결과/PR을 수정하거나 최종 팀 주제·역할·병합을 확정하지 않았다.

## 현재 판단

**가용 대역폭 감소만으로 LEO 특유의 문제를 주장하던 합류 주가설은 중단했다.** 동일한 서비스/ACK/손실 이력을 주는 지상 경쟁 진입과 TCP 수준에서 구별되지 않기 때문이다. 초기 계획은 [현대 TCP 방향 기록](../research/20261012-modern-tcp-direction.md)에 역사적 판단으로 남긴다.

현재는 Handout 4쪽과 Guide 14쪽이 허용한 위치·미래 경로 정보를 이용하는 방향을 검토한다. 1순위 후보는 **경로 단축을 미리 알고 새 데이터 송신을 조절해 재정렬을 줄이는 것**이다. [후보 비교 문서](../research/20261012-predictable-leo-tcp.md)는 궤도 기반 BDP/RTT 추정, 앙각 제어, 선행연구와 정보 오차·비용·중단 기준을 함께 설명한다. **새 정책은 구현하지 않았고 성능 개선도 입증하지 않았다.**

## 실제로 끝낸 작업

| 작업 | 결과와 한계 |
| --- | --- |
| 공식 환경 보존 | 새 container `lab1-bbr-route-20261012`, 새 volume `cs30401-bbr-route-ns3-20261012`, CPU 4개/메모리 6GiB. 원본 build와 모든 library를 patch 전에 복사했다. 이전 실험 volume은 덮어쓰지 않았다. |
| 제공 state 추적 | 1,584개 위성·Seoul/London 두 지상국. fstate delta를 누적했다. 2,000파일 중 182개 비어 있지 않음, 7,614행, forwarding 내용 133,900B; metadata 포함 383,343B, 0.0931초. 역방향은 같은 방향의 egress를 공유하지 않고 동일 방향 두 flow는 항상 같은 경로다. |
| 제한된 기하 후보 확인 | 두 도시 조합·각 8시점, sparse SSSP만 계산. retained 실행 5.8389+5.0254=10.8643초, 개발 중 첫 계산까지 합계 16.5351초. 하나는 모든 표본에서 공유, 다른 하나는 모두 분리였다. 표본 사이를 전수 확인한 결론은 아니다. 새 state나 TCP 실행은 생성하지 않았다. |
| 수동 관측 patch | opt-in BBR 추정 상태, 실제 앱 수신 바이트, 장치 큐 방문/잔여 패킷, 계층별 drop hooks. TCP 정책·wire header는 변경하지 않았다. 첫 UID 식별 오류는 실제 queued packet 객체 추적으로 수정했다. |
| 원본/off/on 대조 | 단독 40초 원본·patch-off·수정 patch-on 완료. 기존 cwnd/RTT/progress/flow CSV 4개 모두 byte-identical. 이 조건의 동등성이다. |
| 완료 실행 분석 | 앱 전달량·flow/port 연결·해시·queue enqueue/dequeue/pending 보존 검사를 통과했다. 실제 앱 goodput은 전체 90.4615Mbit/s, `[10,40)` 93.3465Mbit/s. drop hook events와 고유 손실/재전송 수를 구별한다. |
| 실패/미완료 보존 | 첫 reference 준비는 Git ownership 확인에서 실행 전 중단. 최초 관측 실행은 계측 오류로 실패. 2-flow join10은 180초 wall timeout, together는 미실행. 불완전 결과는 성능 분석에서 제외했다. |
| 대안의 소스 선별 | 제공 전파 RTT 최대/최소 약 1.127, BBR ProbeBW cwnd gain 2. 순수 기하 증가만으로 옛 2BDP 한도가 부족해질 근거가 약하다. HyStart delay 분기도 작은 기하 상승만으로 발동하기 어렵다. ACK-train·복구/큐 효과는 미검증이다. 새 TCP 성능 실험이 아니다. |

정확한 내용·비용은 [탐색 기록](../../code/bbr-route/NOTES.md), [실험 기록](../experiments/20261012-bbr-route-pilot.md), [도구와 재현 명령](../../code/bbr-route/README.md)에 있다. 같은 구간의 sender ACK progress를 실제 receiver goodput으로 대신 쓰지 않는다.

## 실행 소스와 재현 근거

- 이미지: `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`.
- 공식 ns-3 HEAD: `99bc6f733274475b7a6e804128651e17ee2a2536`, 적용 전 source clean.
- 보존 build: container `/tmp/bbr-route-reference/build`. runner는 해당 library를 `LD_LIBRARY_PATH`로 선택한다. 원본 binary만 복사하면 새 library를 읽을 수 있다.
- 최종 patch: `code/bbr-route/ns3-observe.patch`, SHA256 `ddcad50d06a8e3fc34a79fabb4942e2225d4788488d3db96e2b72a379262c445`.
- reference는 runner commit `2e805cf`, 초기 patch-off는 `5edda66`, 수정 observer-on은 `d520bd4`에서 실행했다. 각 원본 manifest가 실행 commit·소스 diff·binary/library·설정/스케줄·상태 입력·출력 hash·명령·wall time을 보존한다. 초기 reference manifest의 필드가 후속 runner보다 적다는 한계도 유지한다.
- [원본/off 비교](../experiments/assets/20261012-bbr-route/equivalence-original-off.json), [원본/on 비교](../experiments/assets/20261012-bbr-route/equivalence-original-on.json), [6개 거부 검사](../experiments/assets/20261012-bbr-route/observer-negative-checks.json), [완료 실행 분석](../experiments/assets/20261012-bbr-route/pilot-analysis/pilot-summary.json)을 공유한다. 상태 receipt를 연결한 비교가 동적 입력 파일 전체를 재감사한 것은 아니다.
- [GitHub diagnostic prerelease의 원본](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/bbr-route-diagnostics-20261012/bbr-route-diagnostics-20261012.tar.gz)은 10,002,124B, 70개 텍스트 파일이며 실패/timeout도 포함한다. SHA256 `db389f9a6af331701ad8c15656661a41b83fc1c1092971b62a7f34a5d01ea5a8`. 파일별 목록·해시는 [inventory](../experiments/assets/20261012-bbr-route/raw-inventory.json)에 있다. 모든 member hash와 GitHub asset digest/size를 확인했다. build/state/core dump는 포함하지 않는다.

## 다음 작업과 검토할 점

1. 제공 모델의 예측 정보를 사용하는 범위와 현실적인 운영자 힌트 가정을 팀이 검토한다. TLE만으로 실제 routing·큐·패킷 도착 시각을 아는 것은 아니다.
2. 기존 26.2초 CUBIC 재정렬 증거를 출발점으로 쓰되, 선택한 TCP에서 불필요한 복구와 실질적 서비스 비용부터 확인한다. BBR의 같은 피해를 가정하지 않는다. 과제 복구 스택의 결론을 현대 Linux RACK-TLP 전체에 일반화하지 않는다.
3. 의미 있는 비용이 확인되면 새 데이터 송신 한 곳의 짧은 pacing/hold만 구현한다. 정확한 힌트·고정 경로/잘못된 시각 대조·예측 오차·실제 손실·짧은 flow FCT로 비용을 함께 평가한다.
4. 기존 국소 이득은 전체 이득의 증거가 아니며, 새로운 후보의 효과도 아니다. 전체 이득이 작거나 hold/손실 복구 비용이 크면 후보를 중단한다. 합류 탐색과 timeout 실행은 다시 확대하지 않는다.

다른 조원은 자기 AI에 PR16의 최신 본문과 `docs/research/20261012-predictable-leo-tcp.md`를 읽고 **과제 적합성·선행연구와의 차이·정보 가정·검증 순서**를 검토하도록 요청할 수 있다. 공유 문서는 다른 조원의 작업 지시나 강제 프롬프트가 아니다.
