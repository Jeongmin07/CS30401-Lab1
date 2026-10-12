# 처리량을 유지하면서 큐 적체와 드롭 줄이기

2026-10-13, kim-seongchan. 사용자가75초 큐 문제의 해결안을 찾고 실제 비교한 뒤 PR에 공유하도록 요청했다. 아래는 새 시뮬레이션 전에 정한 범위다. [이전 큐 원인 검사](20261013-tail-and-queue.md)의 source·원본·결론은 보존한다. 같은 Draft PR16의 후속이며 다른 조원의 작업이나 최종 팀 주제를 바꾸지 않는다.

## 확인한 문제와 접근

현재 선택적 손실 대기+마지막 패킷 보완의 자연10Mbps/q100/200초 흐름은9.5465088Mbps를 전달한다.75초 이전부터 송신 큐가 크고, 가득 찬100패킷 큐가 장치 송신을 멈추면 root qdisc가 없어 TrafficControl이 새 패킷을 버린다.75초 경로 전환을78초로 늦춰도 드롭11개가 남았다. 따라서75초라는 시각에만 예외를 만들거나 순수 기하 BDP로 창을 갑자기 줄이는 방법을 먼저 적용하지 않는다.

두 검증을 병렬 진행한다. TCP의 기본 페이싱과 운영자가 아는 링크 용량을 반영한 송신 속도 상한을 비교하고, 장치가 멈췄을 때 상위 큐에서 보관하는 FIFO 및 기존 CoDel을 비교한다. 페이싱/CoDel은 기존 방법이며 이번 팀이 새로 발명한 TCP 알고리즘이라고 부르지 않는다. 과제의 예측 기반 손실 오판 완화와 함께 사용할 때의 효과·비용을 확인하는 후속이다.

| 내부 담당 | 새 소유 경로 | 최초 고정200초 비교 |
| --- | --- | --- |
| review_baselines_and_handoff | code/queue-pacing, 세부 기록/새 assets | 현재 정책·페이싱OFF / 기본 페이싱ON / 같은 페이싱+용량 상한 |
| review_cubic_study | code/queue-backpressure, 세부 기록/새 assets | 현재 source device100p / source FIFO96p+device4p / source CoDel96p+device4p |
| audit_research_handoff | 읽기 검토 | source·실제 전체 큐 계산·손실/복구·입력 비교 검토 |
| 이 채팅 root | 공통 문서·Git·PR·원본 공유 | 사전 선언, source checkpoint, 선정/후속 검증, 통합 공유 |

이들은 이 채팅 안의 병렬 분담이며, 조원3명 각자의 외부 AI에게 작업을 배정하는 구조가 아니다.

## 고정 설정과 정보 가정

모든 최초 조건은 제공 Seoul1584→London1585의 동일한200초 state, flow0·100GB·0초 시작·seed123456789, CUBIC/SACK/PRR 및 현재 selective+tail을 사용한다. tail의 guarded combined patch SHA256은 `5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29`다. 새 standalone source는 이를 기반으로 수동 큐/장치 관측을 합친다. 기존 디렉터리나 ns-3 volume을 수정하지 않는다. opt-in 정책이 꺼진 baseline의 기존 측정 CSV가 이전 결과와 같은지 확인한다.

페이싱ON은 native 기본 slow-start ratio200%, congestion-avoidance ratio120%, 초기 창 페이싱false를 유지한다. 기본 최대 속도는4Gbps다. 용량 상한 조건은 `floor(10,000,000 × 1380 / 1434) = 9,623,430bps`를 사용한다. native pacing timer가 payload bytes를 기준으로 하고 실제 full data wire packet은1434B이므로54B 헤더 비용을 반영했다. 이는 운영자가 고정10Mbps 용량을 안다는 단일-flow 조건이다. 경쟁 트래픽의 남은 몫을 정확히 추정하거나 실제 위성망 용량을 알 수 있다는 주장이 아니다. 기존 직접 재전송 및 초기 burst가 있어 엄밀한 wire shaper라고 부르지 않는다.

FIFO/CoDel은 송신 지상국의 장치1에만 설치한다. 나머지 큐와 링크·routing·용량은 그대로다. CoDel은 native Target5ms/Interval100ms/MinBytes1500/ECNfalse/L4sfalse를 유지하고 MaxSize만96p다. 두 buffered 조건은96+4의 동일한 명목 queue 크기를 쓴다. qdisc의 requeued item 및 장치의 직렬화 중 packet은 일반 queue 크기에 포함되지 않으므로 실제 총량에서 별도로 세며, 엄밀한100패킷 전체 상한이라고 주장하지 않는다.

기본 페이싱은 [ns-3 TCP 모델](https://www.nsnam.org/docs/models/html/tcp.html), CoDel은 [RFC8289](https://www.rfc-editor.org/rfc/rfc8289.html)에 근거한다. 실제 속성·byte 계산·queue wake 동작은 과제 이미지의 source에서 확인한다. SYN RTT/SRTT를 무부하 full data RTT라고 보고 blind flight cap을 적용하는 후보는 먼저 제외했다. 이전 관측의 SYN 약99ms와 첫 실제 data RTT111.619ms가 다르고, 일반 AvailableWindow cap은 손실 복구까지 막을 위험이 있기 때문이다.

## 완료 기준과 계측

최초 비교는 두 독립 runtime의3+3, 총6조건이다. 첫 실행 전 source/runtime checkpoint와 실제 설정을 게시한다. 각 조건은 CPU2·4GiB·build1job·wall cap600초이며 source/runtime를 실행 중 바꾸지 않는다. 새 토폴로지/APSP·parameter sweep·75초만 골라 성과를 만들기는 하지 않는다.

주 목표는 전달 속도를 떨어뜨리지 않으면서 큐와 드롭을 줄이는 것이다. 미리 정한 처리량 동등 범위는 현재9.5465088Mbps의99.5% 이상(9.498776256Mbps)이며, 작은 감소도 실제 값과 비용으로 공개한다. 후보 선별에는 `[75,75.5)`의 **실제 source 전체 큐 점유/서비스 대기를 최소50% 낮추고**, `[74.5,77.5)`의 모든 계층을 합친 고유 dropped transmission을11→5 이하로 줄이는 기준을 사용한다. 전체200초 평균 큐/드롭도 나빠지지 않아야 하며, 같은 현상을 다른 시각이나 큐로 옮겼다면 해결로 부르지 않는다. 전체와 첫26초 창 `[25.7,28.2)`도 함께 보고한다.

장치별 full200초 packet-time/byte-time 면적을 실제 상태 변경과 정확한100ms 구간으로 적분한다. 뒤늦은 flush snapshot으로 과거 점유를 대신하지 않는다. qdisc와 device를 함께 가진 후보는 실제 TC/qdisc ingress→device PhyTxBegin의 개별 packet residence를 계산해 requeue 시간을 포함한다. 서로 다른 packet 수로 계산한 두 평균을 더하지 않는다. dropped/pending/in-service packet과 queue 보존, actual flow/tx_id/TXtime/seq/payload를 남기고 CoDel intentional drop도 전체 실제 손실에 포함한다.

## 후보 선정 뒤 제한된 실제 손실 검증

처음6조건에서 기준을 통과하는 후보가 있을 때만, 감소된 전체 대기/드롭을 우선으로 하고 goodput 감소가 더 작은 후보를 선정한다. 동률이면 단순한 native 설정을 우선한다. 이후 같은 실제 손실 입력을 주는 current/selected2조건을 확인한다.0초부터 방법이 작동하면26초 original TX identity는 달라질 수 있으므로 이전과 동일 packet/time을 잃었다고 가정하지 않는다. 가능하면 receiver에서 flow0의 첫 original seq1/1380B를 한 번 잃게 하는 고정 규칙을 사용하며 실제 각 TX/물리 drop/복구 시각을 개별 확인한다. 이 규칙은 평가 입력이며 controller에 미래 손실 정보를 주지 않는다.

페이싱 후보가 선정되면 추가로 stable100Mbps/q2000/50ms 편도/20MSS/실제 첫 손실/잘못된 예측 힌트의 finite 대조를 수행한다. original TCP·현재selective+tail·선정된paced 정책3조건이며 용량 상한은 같은 공식으로100Mbps에 맞춰96,234,309bps다. tail의 pacing-timer guard 때문에 기존 짧은 파일의 비용이 되살아나는지 확인한다. 자연 bulk의 tail0회로 finite FCT 안전성을 주장하지 않는다. 이 최초 범위는 최대11조건(6+2+3)이다. 결과에 맞춘 상한 sweep이나 자동 추가 조건은 없다. 정확성 보수나 명백한 정책 결함 수정이 필요하면 원래 시도/버전을 보존하고 별도 재검증 범위를 먼저 기록한다.

## 최초 6조건 결과와 후속 선정

두 새 대조군의 기존 측정 CSV 12개가 각각 이전 selective+tail 결과와 size/SHA 기준으로 일치했다. 입력·실제 root 큐 관측·전체 큐 보존·손실 전송 ID 연결을 통과한 [페이싱 비교](assets/20261013-queue-mitigation/initial-pacing.json)와 [큐 제어 비교](assets/20261013-queue-mitigation/initial-backpressure.json)를 보존한다.

| 설정 | 전체 goodput (Mbps) | 75–75.5초 source 전체 평균 큐 (패킷) | 같은 구간 실제 source 대기 (ms) | 74.5–77.5초 고유 데이터 드롭 | 전체 고유 데이터 드롭 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 현재 정책, 페이싱 OFF | 9.5465088 | 87.2324 | 96.1995 | 11 | 486 |
| native 기본 페이싱 ON | 9.0571056 | 26.5016 | 30.1014 | 0 | 460 |
| ON + 고정 링크 용량 상한 | **9.5662704** | **0** | **0** | **0** | **0** |
| FIFO96p + device4p | 9.5465088 | 87.2324 | 96.1995 | 11 | 486 |
| CoDel96p + device4p | 8.9403576 | 8.1897 | 9.3366 | 1 | 171 |

기본 페이싱은 처리량이 5.128% 낮아졌고, CoDel은 큐를 많이 줄였지만 처리량이 6.349% 낮아졌다. FIFO는 source 대기와 전체 결과가 그대로이며 드롭 계층을 TC에서 qdisc로 옮겼으므로 해결로 채택하지 않는다. 용량 상한 조건만 모든 사전 기준을 통과했다. 이 조건은 goodput +0.2070%, 전체 장치 큐 packet-time −91.947%, 재전송 507→2, 복구 진입 40→1이다. 드롭 0은 태그와 payload를 가진 실제 데이터 전송의 모든 계층 고유 손실 기준이며, 재전송 2회도 자동으로 허위 재전송이라고 단정하지 않는다.

첫 6조건의 유일한 통과 후보인 **용량 상한 페이싱**을 선정해, 사전에 정한 추가 5조건만 진행한다. 실제 첫 원본 손실의 200초 current/selected 대조와 20MSS 짧은 파일의 original/current/selected 대조다. 자연 bulk에서는 마지막 한 패킷 보완이 0회였으므로 이 결과로 finite 완료 시간까지 안전하다고 주장하지 않는다. 추가 속도 조절이나 CoDel 파라미터 탐색은 하지 않는다.

## 결과 공유

첫 실행용 구현은 두 별도 빌드와 읽기 검토를 통과했다. 페이싱은 `35f0306`의 source와 `3e456b7`의 원본 로그 속성 보존 checkpoint, 큐 제어는 `b6112ce` checkpoint를 사용한다. 최종 combined patch는 각각 `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808`, `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f`다. 초기 개발 빌드에는 시뮬레이션이 없으며, 최종 빌드 전에 실제 root qdisc 손실 관측과 선택적 평가용 손실 모델의 기존 설정 덮어쓰기 방지를 보수했다. 초기 3+3조건만 실행 승인했다. 조건별 실제 launch ref/dirty 상태는 각 원본 manifest를 따른다.

완료 뒤 구현·actual launch commit/dirty·patch/runtime/input/output SHA·정확한 config/CLI·실제 앱 전달량·큐 및 손실 비교·비작동/비용을 기록한다. 큰 원본은 새 Release, 작은 결과와 inventory는 Git에 공유한다. 후보가 기준을 만족하지 않으면 trade-off를 그대로 보고하고 완전한 해결이라고 쓰지 않는다. PR16의 최종 본문과 root 인수인계를 최신 결과로 갱신한다.
