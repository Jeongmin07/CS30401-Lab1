# 현대 TCP 진단과 예측 정보 활용 후보 — 2026-10-12

- 담당: kim-seongchan의 이번 채팅. 조원 3명이 각자 사용하는 AI는 GitHub에 공유된 정보를 읽으며 자동 메시지 시스템을 가정하지 않는다.
- 브랜치 / PR: `research/bbr-route-transition`, [Draft PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16).
- 기준: `main` `b60e8e019053c7d33b853510ec06c3d94ee78faf`.
- 범위: 연구 방향 재검토·PR 공유·비용 제한 진단. 다른 조원의 코드/결과/PR을 수정하거나 최종 팀 주제·역할·병합을 확정하지 않았다.

## 현재 판단

**최신 세 후보 후속 검증 완료:** [공통 결과](../experiments/20261012-three-followups.md)를 먼저 읽는다. 내부 서브에이전트가 CUBIC 확대·축소의 문제 선별과 선택적 손실 대기를 나눠 진행했고, root가 방향별 기하·통합 검증·GitHub 공유를 맡았다. 확대·축소는 정책 구현 전에 중단했다. 공유 10Mbps 관측은 성공했지만100Mbps 장시간 관측은240초 상한에 걸려 미검증으로 남겼다.

선택적 손실 대기는 K3를 유지하고 old-flight cohort에만 짧은 shared deadline을 준다. 최종7조건에서 자연 LEO200초 goodput9.544356→9.5465088Mbps, 첫 창 재전송/복구3/1→0/0으로 기존 bounded K20과 같은 작은 이득을 냈다.75초 창에는12/2가 발생했고 원본은0/0이었다. 실제 경로 중 동일 패킷 손실의 첫 재전송은5.735961ms 더 늦었고, 잘못된 positive hint를 준20MSS 흐름의 완료 시간은0.251510→0.350482초로 증가했다. 짧은 대기가 작은 FCT 비용을 보장하지 않는다.

실제 손실 선택·물리 drop·재전송 이후 시각, K3·기한·실제 앱 수신량과 source/runtime receipt를 검증했다. OPEN 종료 경계는 소스 검토로 수정했으나 최종7조건에서 실행0회여서 실행 검증을 주장하지 않는다. 최종7·예비V1 micro2·공유 passive 성공1/timeout1의 총11시도를 구분한다. [새 원본 Release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-followups-20261012)와 각 후보의 combined patch/재현 설명을 공통 결과에서 연결한다. 추가 sweep·ON·토폴로지·100Mbps 재실행은 진행하지 않는다. 팀은 원본을 검토하고 보고서에 사용할 문제·효과·비용 범위를 결정할 수 있다.

아래는 이 후속 검증 이전의 고찰과 실험 이력이다. 미구현·다음 작업 표시는 작성 시점의 상태이며 최신 진행 상황은 위 공통 결과를 따른다.

**최신 고찰 공유:** [진행 상황과 연구 방향 고찰](../research/20261012-progress-retrospective.md)에 손실 판정13조건과 후속 네 후보21유효 실행의 효과·비용, 대표 조건의 처리량 여유, 선제적 CUBIC 확대/축소와 동적 손실 문턱·짧은 타이머에 대한 판단을 모았다. 현재 K20 종료 재평가는 이미 구현됐으며, 패킷별 선택적 대기와 선제적 CUBIC 정책은 아직 미구현이다. BBR의 BDP 목표 교체나 고정 송신 hold 결과로 모든 궤도 제어를 배제하지 않는다. [소스·기하·기존 원본 감사](../experiments/assets/20261012-progress-retrospective/source-audit.json)가 새 고찰의 주요 수치를 연결한다. 새 시뮬레이션·팀 주제 확정·역할 배정은 없으며, 아래의 과거 후속 계획보다 최신 고찰의 상태 구분을 우선 읽는다.

**최신 범위 수정·완료:** 사용자의 지시에 따라 손실 판정 외의 네 후보를 별도 volume에서 병렬로 실제 실험했다. 내부 서브에이전트3명이 BDP·RTT, BBR ProbeRTT 시점, CUBIC HyStart를 맡고 이 채팅의 root가 송신 hold를 맡았다. 이는 조원3명이나 각자의 외부 AI의 역할을 다시 배정한 것이 아니다. 유효21회와 BBR old-runtime 제외1회를 구별하며 [공통 기록](../experiments/20261012-parallel-candidates.md)에 실제 결과·한계·재현·공유 원본을 모았다. 큰 처리량 이득은 없었으며 각 정책의 실제 작동/무작동과 비용을 기록했다. root hold와 ProbeRTT V2는 별도 서브에이전트의 읽기 교차 검토도 받았다. 아래의 우선순위·미실행 판단은 **이 병렬 실행 이전의 기록**이다.

**가용 대역폭 감소만으로 LEO 특유의 문제를 주장하던 합류 주가설은 중단했다.** 동일한 서비스/ACK/손실 이력을 주는 지상 경쟁 진입과 TCP 수준에서 구별되지 않기 때문이다. 초기 계획은 [현대 TCP 방향 기록](../research/20261012-modern-tcp-direction.md)에 역사적 판단으로 남긴다.

후속 피드백을 반영해 송신 pause/pacing 후보를 우선 제외했다. 현재는 **예측 구간에서 손실 판정 문턱을 일시적으로 높이고 구간 종료 시 기존 SACK/dupACK 증거를 재평가하는 제한된 복원 정책**을 구현·검증한다. 기존 K8/K20도 notified window 정책이었으며, 이번 차이는 기하 기반 구간 계산과 종료 시 복원 지연의 제한이다. [현재 실험 기록](../experiments/20261012-forecast-loss.md), [새 구현/재현](../../code/predict-loss/README.md)을 먼저 읽는다. 아래 표는 앞선 BBR 진단의 완료 기록이며 이번 새 실험의 결과와 구분한다. [후보 비교](../research/20261012-predictable-leo-tcp.md)의 송신 조절안은 역사적 검토로 남긴다.

## 실제로 끝낸 작업

**최신 손실 판정 실험:** [13개 실행·분석](../experiments/20261012-forecast-loss.md)을 완료했다. LEO10의 전체200초 goodput은9.544356→9.5465088Mbit/s(+0.0226%), 첫 창 재전송/복구는3/1→0/0, 300ms 늦은 알림은 원본과 같았다.100Mbps의40초에서는 문턱20으로 복구가 남고64로 첫 창 복구를 제거했지만 전체 이득은 최대 약0.0093%였다.20MSS 실제 첫 손실의 FCT는 기존 보호1.150124001→새0.400114720초로 줄었지만 원본0.251509920초보다 느렸다. 새 보호는 선언 종료 때 K3와 기존 증거 재평가를 수행했다.24개 원본/legacy CSV의 과거 baseline 동일성, 실제 수신·파일 해시·보호 시간·그림 원본 연결도 확인했다. 아래 표는 별도로 보존할 초기 BBR 진단이다.

새 원본은 [forecast-loss Release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/forecast-loss-20261012)의85MB 압축 파일로 공유했다. 전체205개 member와 GitHub asset SHA/size를 검증했다. [독립 clean replay](../experiments/assets/20261012-forecast-loss/clean-replay.json)는 **13개 중2개만** 별도 volume에서 재현했고 측정19CSV+schedule1개가 같았다. wall time profiling은 다르며 전체13개·그림·분석 재생성을 주장하지 않는다.

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
3. 현재 [손실 판정/복원 실험](../experiments/20261012-forecast-loss.md)의 실제 결과와 종료·실제 손실 비용을 확인한다. 정확한 힌트·늦은 시각 대조·짧은 flow FCT를 함께 보고, 새 baseline의 원본을 기존 v6와 대조한다. 송신 hold는 실행하지 않는다.
4. 기존 국소 이득은 전체 이득의 증거가 아니며, 새로운 후보의 효과도 아니다. 전체 이득이 작거나 hold/손실 복구 비용이 크면 후보를 중단한다. 합류 탐색과 timeout 실행은 다시 확대하지 않는다.

다른 조원은 자기 AI에 PR16의 최신 본문과 `docs/research/20261012-predictable-leo-tcp.md`를 읽고 **과제 적합성·선행연구와의 차이·정보 가정·검증 순서**를 검토하도록 요청할 수 있다. 공유 문서는 다른 조원의 작업 지시나 강제 프롬프트가 아니다.
