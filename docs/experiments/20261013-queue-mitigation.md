# 처리량을 유지하면서 큐 적체와 드롭 줄이기

2026-10-13, kim-seongchan. **고정 10Mbps·200초 대용량 흐름에서는 용량을 반영한 페이싱으로 처리량을 유지하면서 75초 큐 적체와 실제 드롭을 줄였다.** 자연 조건의 goodput은 9.5465→9.5663Mbps, 75–75.5초 source 평균 큐는 87.23→0패킷, 전체 실제 데이터 손실은 486→0이다. 다만 짧은 파일에서는 기본 페이싱 자체의 속도 계산 때문에 완료 시간이 83.28% 늘었다. 이 옵션을 모든 흐름의 기본값으로 권하지 않는다.

사용자가 요청한 비교 11조건을 모두 완료했다. 아래 앞부분은 새 시뮬레이션 전에 정한 범위이며 실제 결과·비용은 후반부에 있다. [이전 큐 원인 검사](20261013-tail-and-queue.md)의 source·원본·결론은 보존한다. 같은 Draft PR16의 후속이며 다른 조원의 작업이나 최종 팀 주제를 바꾸지 않는다. [페이싱 상세·재현](20261013-queue-pacing.md), [FIFO/CoDel 상세·재현](20261013-queue-backpressure.md)을 연결한다.

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

선정 조건의 source 전체 평균 대기는 41.724668→0.000456345ms로 낮아졌고, 75초 이후 대기 0은 실제 송신된 436개 packet visit에서 확인했다. 전체 200초에는 초기 무페이싱 burst로 source 큐 최대 10패킷이 남는다. 다른 장치의 큐도 남아서 네트워크 전체 평균은 3.164266패킷이다. 따라서 특정 구간의 source 큐 0을 전체 위성망의 모든 큐 0이라고 해석하면 안 된다. [개별 전송·앱 전달·전체 평균 대기 감사](assets/20261013-queue-pacing/final/posthoc.json)를 연결한다.

첫 6조건의 유일한 통과 후보인 **용량 상한 페이싱**을 선정해, 사전에 정한 추가 5조건만 완료했다. 실제 첫 원본 손실의 200초 current/selected 대조와 20MSS 짧은 파일의 original/current/selected 대조다. 자연 bulk에서는 마지막 한 패킷 보완이 0회였으므로 이 결과로 finite 완료 시간까지 안전하다고 주장하지 않는다. 추가 속도 조절이나 CoDel 파라미터 탐색은 하지 않았다.

## 실제 손실과 짧은 파일에서의 비용

[최종 8조건 비교와 정확한 대조 검증](assets/20261013-queue-mitigation/final-pacing.json)에 최초 3조건과 선정 후 5조건을 함께 보존한다. 200초 전송은 100GB를 끝내지 못했으므로 파일 완료 시간은 없다. 작은 파일은 끝냈으므로 아래 실제 완료 시간을 비교한다. 작은 파일의 수신 바이트를 고정 4초로 나눈 goodput은 세 조건 모두 같아 완료 지연을 숨기므로 평가 지표로 쓰지 않는다.

| 대조 | 기존 selective+tail | 용량 상한 페이싱 추가 | 해석 |
| --- | ---: | ---: | --- |
| 실제 첫 원본 손실, 200초 goodput | 9.3421584Mbps | 9.332664Mbps | −0.1016%, 선언한 0.5% 동등 범위 안이나 작은 비용은 남음 |
| 같은 조건의 고유 데이터 손실 | 192 | 1 | 선정 조건의 1회는 주입한 실제 손실 |
| 같은 조건의 RETX / recovery | 215 / 37 | 3 / 2 | 원본 손실과 큐 손실을 구분해 계측 |
| 주입한 물리 손실→첫 재전송 | 53.228969ms | 53.228969ms | 두 실제 전송/손실 ID·시각도 이 대조에서는 동일 |
| 27.6KB 실제 첫 손실+잘못된 힌트, FCT | 0.257223678초 | 0.471434773초 | **83.28% 악화**; 원본 TCP는 0.251509920초 |
| 같은 파일의 추가 마지막 패킷 허용 | 1회 | 0회 | 단순히 pacing timer guard가 막았다고 해석하면 틀림 |

첫 원본 손실은 두 조건 모두 flow0 seq1/1380B, tx_id3, 송신 0.099500204초→수신 물리 drop 0.161402717초, 첫 재전송 0.214631686초였다. 이 대조는 초기 손실을 검사한 것으로, 경로 전환 보호가 실제 활성화된 도중의 진짜 손실 안전성 검증을 대신하지 않는다.

짧은 파일에서는 최대 속도 상한을 96.234309Mbps로 두어도 실제 native 계산 속도가 **2.208Mbps**여서 패킷 간격이 5ms가 됐다. 복구 진입 전 새 데이터 두 패킷 중 하나는 실제 selective 대기 시작 직전 0.200248초, 다른 하나는 대기 중 0.205248초에 송신됐다. 실제 대기는 0.200477440초부터 시작했다. 마지막 한 패킷 조건을 검사할 때마다 아직 12,420B가 남아 `MORE_THAN_ONE_MSS`로 7회 거절됐다. 첫 재전송 기한 0.207108958초는 그대로지만 마지막 새 패킷은 0.421320053초에야 송신됐다. 따라서 tail hook을 타이머 만료 때 다시 부르는 것만으로 이 비용을 해결한다고 주장하거나 기존 1MSS 제한을 풀지 않았다. 현재 결론은 알려진 용량의 대용량 흐름에 대한 선택적 옵션이다.

## 기존 예측 보호와의 관계, 남은 문제

새 설정은 75초에 특별한 예외를 넣거나 cwnd를 강제로 줄이지 않는다. CUBIC의 창·SACK·복구는 유지하고, 기존 native 페이싱의 송신 간격에 고정 링크 용량의 payload 상한을 더한다. 용량을 아는 단일 흐름에서 큐를 계속 채우려는 송신을 줄인 결과다. 위성 경로 예측만으로 큐 문제가 해결됐다고 설명하지 않는다.

기존 예측 기반 selective 정책은 선정 조건에서도 26.308522212→26.314194176초 동안 5.671964ms 작동해 기존 경로의 세 sequence 손실 판정을 유예했다. 25.7–28.2초 goodput은 기존과 같은 9.622464Mbps이며 재전송·복구·데이터 손실은 0이다. 75초에는 실제 selective 대기가 발생하지 않았다. 요약의 오래된 `guard_starts=0` 필드는 이전 K20형 집계와 호환하기 위한 것으로, 새 selective 정책의 무작동을 뜻하지 않는다. `selective_policy.episodes`와 실제 trace를 기준으로 읽는다.

선정 자연 조건에 남은 재전송 2회는 121.668378284/121.669463406초에 발생했다. 각각의 원본은 121.623684545/121.624831750초에 이미 수신되어 앱에 전달됐음을 별도 내부 읽기 감사로 연결했다. 따라서 이 2회는 불필요한 재전송이지만, 예측 기반 보호와 페이싱으로 모든 재정렬 문제가 해결된 것은 아니다. 121.6초 기하 이벤트는 경로 연장이므로 별도 원인 대조 없이 경로 단축 때문이라고 설명하지 않는다.

이번에는 stock TCP+용량 상한만의 별도 대조, 경쟁 흐름, 가변 용량, 예측 오차 범위, 현대 Linux/RACK, 무작위 반복을 실행하지 않았다. 기존 selective+tail에 페이싱을 더한 효과를 분리한 고정 입력 실험이며, 둘의 독립 효과와 모든 LEO 환경의 개선을 일반화하지 않는다. 초기 burst·직접 재전송 때문에 이 상한이 엄밀한 wire shaper도 아니다. 고정 용량은 다른 흐름과 경쟁할 때 자신의 가용 몫을 알려주지 않는다.

## 결과 공유

첫 실행용 구현은 두 별도 빌드와 읽기 검토를 통과했다. 페이싱은 `35f0306`의 source와 `3e456b7`의 원본 로그 속성 보존 checkpoint, 큐 제어는 `b6112ce` checkpoint를 사용한다. 최종 combined patch는 각각 `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808`, `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f`다. 초기 개발 빌드에는 시뮬레이션이 없으며, 최종 빌드 전에 실제 root qdisc 손실 관측과 선택적 평가용 손실 모델의 기존 설정 덮어쓰기 방지를 보수했다. 초기 3+3조건 뒤 `a3cb6c5`에서 최초 결과·단 하나의 통과 후보와 후속 5조건을 공유했다. 조건별 실제 launch ref/dirty 상태는 각 원본 manifest를 따른다.

총 11조건은 모두 성공했고 실패·timeout·성능 제외 시도는 0이다. 이는 조건별 한 번의 고정 입력 진단이며 통계적 반복이 아니다. 기존 baseline 동등성은 각 큐 track의 12CSV와 pacing micro-original/current의 9/11CSV를 별도 확인했다. [독립 내부 읽기 검토](assets/20261013-queue-mitigation/independent-review.json)는 실제 area·전체 손실·물리 drop·앱 전달·수신/재전송 시각과 두 runtime의 각 17파일을 확인했다. source 계측 준비 과정의 두 simulation-free 개발 빌드와 보수는 결과 실행에 합산하지 않는다.

구현·정확한 CLI/config·actual launch commit/dirty·patch/runtime/input/output SHA·분석 전용 helper phase·작은 결과·inventory를 Git에 남겼다. 원본은 [새 prerelease](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/queue-mitigation-20261013)의 archive 2개, 합계 **119,650,296B·334 regular-file members**로 공유한다. [페이싱 inventory](assets/20261013-queue-pacing/archive-inventory.json), [큐 제어 inventory](assets/20261013-queue-backpressure/raw-inventory.json), [원본 member 및 GitHub digest/size 검증](assets/20261013-queue-mitigation/release.json), [문서·구문·수정 범위 검사](assets/20261013-queue-mitigation/verification.json)를 연결한다. member의 별도 streamed 검증과 remote metadata 비교이며 새 volume에서 전체 11조건 재실행 또는 download roundtrip을 주장하지 않는다.

새 토폴로지/APSP·100Mbps 장기 재시도·속도/CoDel sweep·추가 정책 구현은 없었다. 예측 보호와 별개로 기존 페이싱/CoDel을 활용한 적용 범위·비용 비교다. 기존 과제 source의 전역 기본 설정을 바꾸거나 팀의 최종 연구 주제를 확정하지 않았다. PR16과 본인 인수인계는 이 결과로 갱신한다.
