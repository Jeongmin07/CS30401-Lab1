# 나머지 TCP 후보의 동시 실행

2026-10-12, kim-seongchan. 사용자의 지시에 따라 아래 네 후보를 **각각 별도 ns-3 volume에서 실제 구현/대조 실행**한다. 소스 검토만으로 모두 종료하지 않는다. 앙각 제어와 BBR 경로 합류는 이번 실행에서 제외한다. 이전 손실 오판 실험의13조건과 새 후보 결과를 섞지 않는다.

| 담당 | 후보 | 수정/기록 범위 | 격리 실행 |
| --- | --- | --- | --- |
| subagent audit_research_handoff | 궤도 기반 BDP·RTT | code/orbit-bdp, 20261012-orbit-bdp 실험/asset | lab1-orbit-bdp-20261012 |
| subagent review_baselines_and_handoff | BBR RTT 재측정 시점 | code/orbit-probe, 20261012-orbit-probe 실험/asset | lab1-orbit-probe-20261012 |
| subagent review_cubic_study | CUBIC HyStart | code/orbit-hystart, 20261012-orbit-hystart 실험/asset | lab1-orbit-hystart-20261012 |
| root | 송신 간격/짧은 hold로 재정렬 예방 | code/orbit-order, 20261012-orbit-order 실험/asset | lab1-orbit-order-20261012 |

내부 서브에이전트는 이 작업을 위한 병렬 실행 담당이다. 조원3명의 외부 AI나 사람의 역할을 재배정한 것이 아니다. 공통 Git 브랜치는 research/bbr-route-transition이며 각 후보는 서로의 소스/patch를 겹쳐 적용하지 않는다. root가 완료 자료를 확인하고 PR을 공유한다.

각 조건은 실행 전에 선언하고 동일 환경의 원본/정책을 비교한다. 제공 state와 기존 기하 기록만 사용하며 새로운 토폴로지/APSP를 생성하지 않는다. 운영자의 미래 경로 힌트 조건과 실제 endpoint 지식은 구별한다. TCP의 실제 수신량·전체와 고정 전환 창·지연/큐/실제 손실 비용을 후보에 맞게 확인한다. 실패/timeout은 성능 결과에서 제외하고 보존한다.

Docker 가용 RAM은 약8.17GB이므로 각 container CPU2·메모리4GiB cap, 빌드는 각1job으로 진행한다. 네 작업은 동시에 진행하되 실제 메모리를 확인한다. 각 실행의 wall cap은240초, 후보별 최대6조건을 출발 예산으로 둔다. 비용이나 실제 문제에 따라 종료 범위를 명시하며, 성공 수치가 나올 때까지 임의의 도시·큐·규칙을 탐색하지 않는다.

앞부분은 실행 시작의 선언이다. 아래는 실제 실행 뒤 추가한 완료 결과다.

## 실제 완료: 유효21회, 성능 제외1회

별도 source·volume 네 곳에서 모든 후보를 실제 구현·실행·분석했다. BDP4회, BBR 재측정 V1 4회+V2 유효2회, HyStart6회, 새 데이터 hold5회다. BBR V2 최초OFF 한 회는 build 완료 전 옛 runtime에서 시작돼 성능 비교에서 제외하고 원본과 audit 기록을 보존했다. root가 그 오류 복구1회만 추가 허용해 총22attempt/유효21회로 마쳤다. 별도의 독립 seed 반복이나 네 후보의 합성 정책 실험은 아니다.

| 후보 | 실제 수정과 대조 | 관측 결과 | 현재 판단 |
|---|---|---|---|
| [궤도 기반 BDP·RTT](20261012-orbit-bdp.md) | BBR 정상 ProbeBW의 BDP 목표에서 RTT 항만 미래 기하 전파 RTT로 교체.100/10Mbps·q100·40초의 OFF/ON4회. |100Mbps 수신량·큐·drop은 같았고 내부 cwnd는 달랐다.10Mbps 전체 수신량1MSS 감소, 평균 queue visit wait 증가·일부 최대 대기 감소. |이 특정 목표 교체는 처리량 이득이 없거나 혼합 비용. 확대하지 않음. 모든 orbit-aware 제어의 반증은 아님.|
| [BBR RTT 재측정 시점](20261012-orbit-probe.md) | 미래 경로 변경 후 기본 ProbeRTT를 앞당김. V1 4회는 freshness gate가 모두 skip. 이를 완료된 정상 ProbeRTT 기준으로 고친 V2 유효OFF/ON2회. |V2는 두 번째 재측정을9.862초 앞당겼다. 활성35초 goodput89.264393→89.338203Mbps(+0.0827%). 변경 직후5초93.806880→87.242496(−6.9978%), 나중5초85.875744→94.409664(+9.9375%). TcDrop6696→6832. |처리량 dip의 시점 이동과 작은 전체 차이. 명확한 큰 이득으로 주장하지 않음. 조기 재측정 비용과 bias를 남김.|
| [CUBIC HyStart](20261012-orbit-hystart.md) |121.6초 RTT 상승을 지나는8MiB on/off, 이전 시작시각 on/off, 관측OFF, 예측창 ACK-train 종료유예까지6회. |변경 근처 on/off FCT1.342253/1.421404초, drop·재전송200/1245. 이전 시작도 on이 빨랐다. 예측창 정책은 실제 종료가 창 밖이라 defer0회·원본과 동일. |이 조건에서 HyStart를 끄거나 선언한 짧은 창에 개입할 근거가 없음. 물리적 RTT 증가의 조기 종료 피해를 입증하지 못함.|
| [재정렬 예방 새 데이터 hold](20261012-orbit-order.md) |단축 전후 기하 RTT 감소에 비례한 두 짧은 hold.10Mbps·q100·200초3회와 실제 첫 손실20MSS 대조2회. |hold 구간 새 TX0B를 확인했지만 LEO 전체9.544356Mbps·첫 창 재전송3/복구1이 같다. 실제 손실 FCT0.251510→0.362097초(+43.97%). |이 두 규칙은 LEO 효과가 없고 실제 손실 완료 비용. 확대하지 않음.|

**표의 행끼리는 TCP 우열이나 동일 조건의 승자 순위가 아니다.** TCP·큐·링크 속도·기간·유한 크기가 다르므로 각 행 안의 matched pair로만 해석한다. BBR queue wait는 served device visit 기준이며 종단간 지연이 아니다. root hold의 SRTT를 직접 queue wait로 쓰지 않는다. TcDrop hook 기록과 고유 물리 손실, packet trace 행과 재정렬 episode도 구별한다.

## 다른 AI가 판단할 수 있게 남긴 맥락

현재 질문은 “예측 가능한 위성 경로 기하가 기존 TCP의 어느 판단에 실질적으로 도움이 되는가?”다. 입력은 운영자가 정확한 미래 경로를 알려 주는 조건이며 TLE만으로 routing·큐·실제 패킷 도착을 모두 안다는 주장이 아니다. 기본 모델은 고정 링크 용량이며 앙각에 따른 감쇄·가변 속도·무작위 무선 손실을 새로 넣지 않았다.

이전 소스 선별의 “BDP 여유가 커서 문제 전제가 약하다”, “HyStart DELAY 분기의 문턱이 높다”는 주장만으로 후속 작업을 끝내지 않고 이번에는 실제 대조를 했다. 다만 실패 가설을 버리는 것과 코드가 실행되지 않은 것을 구별한다. BDP·hold·ProbeRTT V2의 실제 작동은 관측했다. ProbeRTT V1은 gate skip, HyStart 예측 정책은 활성창 표본은 있으나 종료유예0회였으며 이를 작동한 개선안으로 쓰지 않는다.

처음 ProbeRTT freshness gate는 route 이후 ACK 처리 시각을 새 경로 RTT 측정으로 해석하는 약점이 있었다. 수정판은 정상 ProbeRTT 완료 기록을 보고 기본 drain·4MSS·200ms·round 완료 과정으로 재측정한다. 첫 invalidation에 채택된100ms는 큐 bias가 있을 수 있고 drain 뒤91ms와 구별된다. 기하 값을 실제 RTprop 측정치로 덮어쓰거나 기본 재측정을 제거하지 않았다.

기존 [손실 판정·제한 복원13조건](20261012-forecast-loss.md)은 별도 자료다. 그 작은 전체 이득과 실제 손실 비용을 이번 새 네 후보의 결과로 재사용하지 않는다. 팀의 최종 주제를 손실 판정으로 자동 되돌리거나 네 후보를 모두 보고서에 넣기로 확정하지 않았다. 최신 근거를 먼저 공유하고, 이미 관측된 문제·작은 구현·전체 효과와 비용·정보 가정이 가장 명확한 범위를 조원이 검토할 수 있게 했다.

## 완료 검토와 해석 범위

내부 서브에이전트가 root hold와 BBR ProbeRTT V2를 읽기 교차 검토했다. hold의 실제 K3 유지·재전송 시각·새 TX0·이벤트 수신량·8개 과거 CSV 동일성과 V2의 실제 source/runtime/input 동일성·원본 출력 hash·기본 ProbeRTT lifecycle을 별도로 확인했다. hold 비교 helper에는 검토 후 config·CLI·flow endpoints/size/start 일치 검사를 보강하고 기존 출력에 다시 적용했다. 시뮬레이션 정책을 바꾸거나 새 성능 실행을 한 것은 아니다.

검토에서 남긴 한계는 그대로 따른다. sender high-water sequence 감사는 이번 seq1 시작·32bit wrap 없는 조건에 한정한다. gate에 막힌 송신 시도 수를 직접 세지 않았으며 이미 전송된 packet은 회수하지 못한다. ProbeRTT의 stock drain은 TCP pipe 기준으로 모든 실제 network queue가 비었다는 증명이 아니다. RTT 수용10개 event는 캐시된 TCP lastRtt를 받아들인 기록이며 독립적인 새 측정10개라고 부르지 않는다. 내부 검토는 조원 검토·팀 주제 합의·독립 전체 재현을 대신하지 않는다.

## 코드·재현·원본

각 track의 README/실험 문서가 한 complete patch·공식 image digest·실행 command·source/runner/binary/library/input/output SHA와 실측 범위를 연결한다. 네 patch를 같은 source에 겹쳐 적용하지 않는다. 실행 commit 당시 일부 다른 track 파일이 작성 중인 `repo_dirty=true`도 보존한다. 후처리 코드의 hash와 simulation 당시 runner/runtime의 hash를 구별한다.

원본은 [네 후보 raw prerelease](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-candidates-20261012)에 업로드했다. Git에는 작은 조건·summary·과학 그림·receipt만 둔다. [root의 Release asset 검증](assets/20261012-parallel-candidates/release.json)은 실제6개 asset의 size·GitHub SHA256 digest가 로컬 압축과 같음을 확인했다. 합계62,770,181B다. 새 download roundtrip을 수행한 것으로 쓰지 않는다. 각 archive의 모든 member size/SHA는 압축 안에서 검증했으며, source/build/state와 crash dump는 넣지 않았다. 총22attempt는 BBR invalid OFF1회를 포함하며 해당 원본은 별도 excluded archive다. Release source checkpoint는 `6eb7fcd`이고 실제 simulation launch commit은 각 manifest를 따른다.

| archive | 압축 bytes | SHA256 | member inventory |
|---|---:|---|---|
|orbit-bdp-20261012.tar.gz|7,743,962|7e284e9331b17a84c9df5d6206ba467626c7ac6778aebb45353bcbefb30b02db|[BDP](assets/20261012-orbit-bdp/evidence/raw-inventory.json)|
|orbit-probe-v1-20261012.tar.gz|11,991,776|8fdac40bf18052157c470a20673578f8f4ae400cdd22778b84b0a33435b6c460|[Probe V1](assets/20261012-orbit-probe/raw-inventory-v1.json)|
|orbit-probe-v2-20261012.tar.gz|5,617,613|22a3a6cc4a56f39f5674676eae761c22d59268c9629488931c1c0ba4aa028afd|[Probe V2](assets/20261012-orbit-probe/v2/raw-inventory.json)|
|orbit-probe-excluded-build-race-20261012.tar.gz|2,807,948|bc547863b0984c3c4f8bf6c0a0884edfef61b064810322e59948c80fa4c00352|[Excluded](assets/20261012-orbit-probe/v2/excluded-raw-inventory.json)|
|orbit-hystart-20261012.tar.gz|4,381,571|752be45fb1ee1807cda5060a98bffa19769fdaf8312266a8ea7cf183d1f7c273|[HyStart](assets/20261012-orbit-hystart/raw-archive.json)|
|orbit-order-20261012.tar.gz|30,227,311|1470111cdb6c062aee064e8d9d1d80002955e9419341058b29cbe0c9b15bffd2|[Hold](assets/20261012-orbit-order/raw-inventory.json)|

독립적인 두 번째 환경에서21조건 전체를 재생하거나 통계적 반복·경쟁·예측 오차를 평가한 결과는 아니다. 원본/관측 대조와 작은 실제 구현의 범위를 그대로 보고한다.
