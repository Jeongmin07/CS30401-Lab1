# Vegas 연구 범위와 논문에 근거한 추가 후보

담당: kim-seongchan, 2026-10-10. 사용자 요청에 따라 첫 Vegas 수정의 효과와 한계를 중심으로 범위를 좁히고, 다른 개선안은 원문에서 문제·변경 지점·비용을 확인하여 선별했다. 이 문서는 **새 시뮬레이션 결과나 팀 최종 합의가 아니다**. 현재 구현·결과는 [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14), 앞선 넓은 문헌 조사는 [PR11의 고정된 문서](https://github.com/Jeongmin07/CS30401-Lab1/blob/503508d75371611144b348c74cd2a21bd9744e7b/docs/research/20261010-leo-tcp-literature.md)에 있다.

## 지금 주된 연구 질문

**위성 경로의 지연이 늘어날 때, Vegas의 오래된 지연 기준이 전송을 얼마나 억제하며, 기준을 갱신하면 얼마나 회복되는가? 같은 방법이 실제 혼잡에서는 어떤 비용을 만드는가?**

현재 관측 범위에서 주장할 수 있는 내용은 다음과 같다.

- 원래 Vegas와 첫 수정(v1)을 같은 200초 LEO 조건에서 비교하면 수신 애플리케이션 처리량은 **41.5113 → 69.3432 Mbps, +67.0465%**다. 정해진 입력의 재현과 내부 상태 변화까지 확인했다.
- 경로 지연만 90→96ms로 올린 단독 대조에서는 변경 전 전달량이 같고 변경 후 격차가 발생한다. 고정 지연 단독에서는 기존 기록과 수정 기록이 같다. 이는 오래된 기준과 CA 결정의 연결을 설명하는 대조다.
- 고정 경로+CUBIC에서도 28회 갱신되므로 **경로 변화와 혼잡을 구별하는 데 성공했다고 주장할 수 없다**. 경쟁 중 실제 큐 대기, 상대 흐름, 전체 처리량을 함께 표시한다.
- LEO의 67% 전부가 121.6/187.4초 두 이벤트 때문이라는 주장은 제외한다. 2.2958초의 초기 CA 갱신도 있으며, 총 추가 수신 바이트의 **18.27%가 121.6초 이전에 전달**된다. 시간 구간별 차이는 인과적 기여율이 아니다.
- LEO 공식 재전송 행은 41→71, recovery 진입은 2→4다. 전달량도 달라지는 raw count이며, 모든 재전송이 불필요했거나 바이트당 손실률이 악화됐다는 뜻은 아니다. 재전송 감소를 이 개선안의 성과로 쓰지 않는다. LEO의 직접 큐 대기는 계측하지 않았으므로 SRTT 차이를 큐 대기로 바꾸어 표시하지 않는다.

보고서 주된 구현은 **v1**이다. 낮은 효과의 이전 CUBIC/SACK 개선이나 채택하지 않은 v2를 주된 개선안으로 묶지 않는다. v2는 기존 기록을 보존하여 중복 작업을 막는다. 이를 보고서에 넣더라도 선택적 한계 논의이며 핵심 성과를 대체하지 않는다.

## 논문을 읽고 무엇이 구체적으로 달라졌나

### 1. v1의 기본 원리는 이미 연구되어 있다

La, Walrand, Anantharam의 **Issues in TCP Vegas**, UCB/ERL M99/3 (1999), §3–4는 경로 지연 상승과 지속 혼잡을 다룬다. 최근 **N packet** 블록의 최소 RTT 상승을 L번 확인한 뒤 기준과 cwnd를 보정한다. 지속 혼잡도 같은 상승을 만들 수 있으며 혼잡 논의에 RED가 포함된다. [Berkeley 원문](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/ERL-99-3.pdf)

따라서 v1을 새 원리의 발명으로 쓰지 않는다. 우리 변형은 **20개의 유효 CA cycle, socket SRTT, 1ms 상승 조건, 원래 cwnd ±1MSS 결정 유지**다. 원문의 packet block, K bootstrap, L회 판정, cwnd 비율 보정과 다르다. 값이 우연히 20이라고 해서 같은 표본이나 원문 파라미터 재현은 아니다. 해당 원문과 Hypatia의 지연 기반 TCP 관찰을 인용하고, 과제 환경에 적용하여 이득·혼잡 오인·범위를 검증한 부분을 설명한다.

### 2. 다음 작은 구현 후보: Vegas-A의 임계값 적응

Srijith, Jacob, Ananda, **TCP Vegas-A: Improving the Performance of TCP Vegas**, Computer Communications 28(4), 429–440 (2005), DOI 10.1016/j.comcom.2004.08.016. **§3의 결정 규칙, §4.1 지연 증가 대조, §5.3 LEO와 경쟁 결과**, 저자의 Code3 및 버전 설명을 읽었다. [저자 PDF](https://srijith.net/publications/journals/TCP_Vegas-A_COMCOM05.pdf), [고정된 Code3](https://github.com/skn/vegas-a/blob/a379c93fe70d5d7b16e620d0e046a69e26a1ee0e/codes/tcp-vegas.cc.code3#L239), [코드 버전 설명](https://github.com/skn/vegas-a/blob/a379c93fe70d5d7b16e620d0e046a69e26a1ee0e/Vegas_A_Code_Versions.pdf)

수정 지점은 **Vegas의 congestion avoidance 결정과 이전 cycle의 전송률 추정 상태**다. Code3의 α≤diff≤β 구간에서는 전송률 추정이 증가하면 cwnd 증가를 설정하고 α·β를 1씩 올린다. 감소하거나 같으면 이 구간에서는 cwnd 증가를 멈추고 α·β는 유지한다. diff>β일 때, 또는 diff<α이고 α가 원문 하한 1보다 큰 상태에서 전송률이 감소하면 cwnd와 α·β를 줄인다. 원본은 ACK에서 증가를 적용하며 ns-3의 cycle당 ±1MSS와 동일한 구현이 아니다. 여기서 전송률은 flight/RTT 기반 **추정치**이며 수신 앱에서 직접 측정한 처리량은 아니다.

우리 후보는 현재 입력과 초기 α=2/β=4를 유지하는 **Vegas-A-inspired ns-3 CA 변형**으로 한정한다. 구현한다면 임계값 감소 하한도 초기 2/4로 명시해 원문 하한 1과 구분한다. 논문의 초기 1/3, NS-2 구현, raw RTT를 그대로 재현했다고 쓰지 않는다. 정보 가정은 endpoint의 기존 TCP 상태뿐이다. 경로 알림·라우터 변경·학습 모델이 필요 없다. 원문의 버퍼 점유/손실 비용 때문에 더 안전하거나 무손실인 대안으로 예고하지 않는다. **아직 구현·실행하지 않았다.**

### 3. 전송을 줄여 지연을 다시 측정하는 접근

확인한 **LEDBAT++ Internet-Draft -06**, §3.3/4.4/4.5는 오래된 지연 값의 aging만으로 자기 큐 지연을 기준값에 흡수하는 문제를 설명하고, 2 packet·2 RTT slowdown과 새 지연 표본을 사용한다. 최종 RFC로 표시하지 않는다. [확인한 문서](https://datatracker.ietf.org/doc/html/draft-irtf-iccrg-ledbat-plus-plus-06#section-4.4)

직관은 분명하지만 현재 Vegas에는 SRTT가 전달되며 표본 부족 시 Reno 증가로 돌아가는 경로도 있다. cwnd만 잠깐 줄이는 변경은 같은 측정을 재현하지 못한다. 별도 탐색 상태·fresh RTT·기존 in-flight·recovery 중단 처리가 필요해서 Vegas-A 뒤로 보류한다. CUBIC이 큐를 다시 채우면 빈 큐를 얻는 것도 보장하지 못한다.

**The persistent congestion problem of FAST-TCP: analysis and solutions**, 공개본 §5–7은 경쟁 흐름의 재충전 때문에 송신 감소가 실패할 수 있음을 보여준다. 제시된 추정식은 안정된 FAST 경쟁 흐름 모델에 의존하므로 우리 CUBIC 혼합에 그대로 적용하지 않는다. [공개 원문](https://arxiv.org/pdf/1405.5364)

## LEO 전용 알고리즘을 바로 포팅하지 않는 이유

공식 과제 모델은 instant route switch이며 기본 handover outage와 가변 용량이 없다. 같은 위성망 이름만 보고 다른 모델의 해결책을 가져오지 않는다.

| 실제로 읽은 원문 | 해결하는 문제/필요 정보 | 현재 판단 |
|---|---|---|
| [SaTCP, INFOCOM 2023](https://xyzhang.ucsd.edu/papers/Xuyang.Cao_INFOCOM23_SaTCP.pdf), §IV–VI | 150Mbps/1,000 packet LeoEM에서 실제 단절과 보고를 이용해 CUBIC 반응 완화 | 기본 모델에 대상 단절이 없어 보류 |
| [SatPipe, INFOCOM 2025](https://xyzhang.ucsd.edu/papers/Ding.Zhao_INFOCOM25_SatPipe.pdf), §IV-C/F·V-A | 실제 Starlink의 단절 일정/ACK 간격을 활용한 BBR queue 유지·ProbeRTT | RTT 재측정 원리는 참고, 전체 포팅은 모델/정보 가정이 다름 |
| [StarTCP, APNet 2024](https://www.cuiyong.net/lunwen/2024/StarTCP_Handover-aware_Transport_Protocol_for_Starlink.pdf), §2–3 | 15초 주기/100ms 단절 예비 조건, RL과 probe로 미리 중단/복구 | 단절 없는 모델과 안 맞고 구현 범위 큼 |
| [OrbCC, arXiv v2](https://arxiv.org/html/2508.19067v2), §II–III | 100ms 경로 갱신 모델, per-hop queue/capacity/flow/path telemetry | 문제는 가깝지만 TCP·수신자·스위치까지 포팅하는 것은 범위 큼 |
| [LeoCC 공식 설명/구현](https://github.com/SpaceNetLab/LeoCC) | endpoint reconfiguration detection, BBR 기반 추정/송신 제어, Netlink helper | 전체 논문 PDF를 확보하지 못함. 읽은 원문 후보로 세지 않으며 지금 포팅하지 않음 |

기존 BBR 탐색 평균 93.4Mbps는 참고만 한다. 상세 로그/원본 코드 정보가 덜 완비되어 현재 Vegas 실험의 새 비교군으로 재사용하거나, BBR에는 문제가 없다는 증거로 쓰지 않는다.

## 추가 실험의 선택 기준과 최소 범위

먼저 [v1 영어 연구 정리](../../code/vegas-study/report/RESEARCH_BRIEF.md)와 [기존 결과 그림·재생성](../../code/vegas-study/report/README.md)을 검토한다. 이번 변경은 기존 원본의 후처리이며 TCP 정책이나 원본 측정을 바꾸지 않았다.

추가 구현을 시작한다면 한 후보(Vegas-A-inspired CA)만 분리한다. v1 갱신과 동시에 켜지 않아 각각의 원인을 섞지 않는다. 실행 전 다음 항목을 기록한다.

1. 논문/Code3와의 결정 규칙 매핑, ns-3 입력과 초기 2/4 유지, startup/recovery 원칙, 새 정책 off의 기본 동작 확인.
2. **제공 LEO 단독**에서 앱 goodput·시간 구간·재전송을 확인하고, **고정 경로+CUBIC**에서 양 흐름·aggregate·실제 큐·TcDrop을 확인한다. 기본/v1 기존 설정을 그대로 유지하며 새 바이너리의 기본 동작이 동일함을 먼저 확인한다.
3. CA 임계값 변화와 전송률 추정의 관계가 실제 기록에서 나타나는지 확인한다. LEO 개선이 없거나, 성능 차이가 원치 않은 startup/recovery/기본 파라미터 변화에서 생기면 확대하지 않는다. 큐 비용은 효과와 함께 판단하며 보편적 우월성을 통과 조건으로 만들지 않는다.
4. 두 핵심 조건에서 설명할 수 있는 결과가 생긴 경우에만 단독 RTT step 대조로 원인을 확인한다. 그 뒤 제출할 후보만 재현 검증한다. 큰 알고리즘 목록, 전면 parameter grid, 동일 deterministic 입력의 통계적 반복은 만들지 않는다.

20 cycle/1ms는 최적으로 증명된 값이 아니라 미리 선언한 탐색 설정이다. 현재 좁은 결론에 새 sweep이 필수는 아니다. 민감도를 추가한다면 한 번에 한 값만 바꾼 작은 이웃 조건을 선언하고, 개선된 값만 골라 보고하지 않는다.

남은 제출 작업은 영어 IEEE 보고서, 실제 조원 이름/팀 범위 확인, 명령→그림/표 매핑, `.git` 없는 제출 ZIP에서 실행 가능한 재현 흐름 검증이다. 현재 PR은 연구 자료이며 최종 제출물이나 조원 검토 완료를 뜻하지 않는다. 공통 PLAN은 팀 합의 뒤 별도로 갱신한다.
