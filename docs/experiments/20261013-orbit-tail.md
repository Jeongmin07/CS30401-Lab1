# 공유 손실 대기 중 마지막 새 데이터 한 개의 추가 송신

2026-10-13, kim-seongchan. 아래 질문·규칙·집합은 **실행 전 선언**이며, 완료 결과는 뒤에 별도로 추가한다. 기존 [selective V2](20261012-orbit-loss.md)의 source·원본·결과는 수정하지 않는다. 이 실험은 ns-3 CUBIC/SACK/PRR의 제한된 추가 송신 허용량이며 RFC8985 TLP 구현이나 개선 보장이 아니다.

## 질문과 고정 정책

기존 실제 손실 micro에서 대기 중13–19번 새 segment는 이미 송신됐다. 지연된 것은 마지막20번 한 개였다. initial cwnd10MSS의 pipe를 미확인 head1개와 새 데이터9개가 사용했고, deadline에서는 기본 head RETX가 확보된 한 슬롯을 사용했다. 따라서 이전 SACK credit를 다시 부여하는 방식으로 접근하지 않는다.

새 opt-in `ns3::TcpSocketBase::OrbitTailAdmission`은 기본 false다. ACK 처리 끝에 **ordinary `SendPendingData`가 정상 허용량으로 송신한 뒤** 아래 조건을 모두 확인한다.

- selective의 공유 wait가 현재 활성이고 deadline·등록 종료 전이며, congestion state가 DISORDER다.
- 이번 ACK가 scoreboard의 unique new SACK bytes를 추가했고 episode에서 추가 송신한 적이 없다.
- application Close-on-empty 또는 send shutdown으로 이후 payload가 없음을 확인하며, 실제 TX buffer의 아직 보내지 않은 payload가1..MSS이다. 특정 packet 번호나20MSS 크기를 하드코딩하지 않는다.
- 정상 `AvailableWindow`가 남은 tail보다 작아 extra allowance가 실제로 필요한 경우에만 허용한다. 정상 여유가 있는데 Nagle/SWS/NextSeg 등의 이유로 송신하지 못한 경우는 우회하지 않는다. 현재 highTx/nextTx가 정상 새 데이터 경계를 가리킨다. receiver window는 `seq+payload <= highRxAck+rWnd`로 확인한다.
- 실제 `pipe+payload <= cwnd+MSS`다. 현재 cwnd·PRR/delivered counter·SACK 정보는 변경하지 않는다. episode당 추가 original segment는 최대1개다.

기존 `SendDataPacket`으로 original data를 보내 FIN·RTO·SentBytes·NotifyDataSent·송신 trace를 그대로 사용하고 nextTx를 정상 진행시킨다. pacing 중 timer가 남아 있으면 우회하지 않는다. loss deadline을 연장하거나 PRR를 지속적으로 우회하지 않는다. 추가 허용량은 직접 pipe/cwnd 한계를 확장하는 실험적인 결정이며 혼잡·실제 손실 비용이 없다고 가정하지 않는다. 100GB LEO bulk는 종료되지 않아 이 tail 조건이 작동하지 않을 가능성이 높고, 무작동이면 그대로 보고한다.

## 사전 실행 집합: 동일한 최종 binary의10조건

1. stable false positive hint·실제 첫 segment 손실·100Mbps/q2000·편도50→50ms·4초·20MSS(27,600B): baseline/selective/selective+tail3조건.
2. 제공 LEO10Mbps/q100/200초 단일100GB: baseline/selective/selective+tail3조건. 전체와 `[25.7,28.2)`, `[74.5,77.0)`의 실제 앱 수신·RETX/recovery/drop을 비교한다.
3. 같은 LEO에서 기존과 동일한 original old-flight drop 규칙: baseline/selective+tail2조건. drop packet의 flow/tx_id/TXtime/seq/payload와 실제 receiver drop 시각이 같은지 검증한다.
4. 위 micro와 같은 조건의21MSS(28,980B): selective/selective+tail2조건. ordinary credit로 송신한 뒤2MSS가 남았을 때 추가 송신하지 않는 경계 조건이다. sweep이나 성과를 본 뒤 고른 크기가 아니다.

각 실행의 wall cap은600초다. 별도 공식 container/volume, CPU2·4GiB, build1job을 사용하며 새 topology/state 생성은 없다. 시작 전에 parent가 공유 source checkpoint를 commit한다. 이후 최종 source/runtime를 변경하지 않고 실행한다. 소스 오류나 실패는 원본으로 보존하고 새 코드의 결과로 바꾸지 않는다. 첫 development build 완료 후 peer review의 ordinary-window guard를 추가해 다시 build하며, 그 전 patch/readiness/build log는 별도로 보존한다. development build에서 실행한 simulation은0이다.

## 검증과 해석 범위

기존 V2 patch SHA256 `531bf802984af821afd928fb3932912aca383fcdec5771f30f78d75a806d5591`을 정확히 기반으로 새 standalone combined patch를 만든다. OFF baseline과 selective의 기존 measurement hash 동등성을 확인한다. 새 CSV는 admission 및 skip의 seq/bytes·unique SACK bytes·unsent bytes·pipe/cwnd·receiver-window endpoint·episode/deadline·used 상태를 기록한다. admission 후 실제 original TX를 별도로 join하고 최대1회·payload≤MSS·pipe 상한·receiver window·deadline 비연장을 검증한다.

앱 완료량과 FCT는 ordered receiver delivery로 계산한다. CA_LOSS는 별도 timer 증거 없이 RTO라고 부르지 않으며 모든 RETX 차이를 허위 재전송으로 분류하지 않는다. 자연 bulk의 무작동·21MSS 경계·실제 손실 대조도 함께 공개한다. 미래 ACK를 credit로 쓰거나 이미 사용한 SACK를 다시 세지 않는다. 통계 반복·경쟁 flow·예측 오차·운영 배포 안전성·현대 Linux TCP로의 일반화는 이번 범위 밖이다.

## 완료한 micro5 결과

최종 guarded source checkpoint `46d881046f76b93e5ae33f60bf638acc26ee5ff1`, combined patch SHA256 `5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29`의 동일 runtime에서5조건 모두 성공했다. 자연 LEO5조건은 이 micro 검증 후 별도로 진행한다.

| 조건 | receiver 완료 bytes | FCT(s) | 실제 추가 admission | 실제 drop / RETX / recovery |
|---|---:|---:|---:|---:|
| 20MSS baseline | 27600 | 0.251509920 | 0 | 1 / 1 / 1 |
| 20MSS selective | 27600 | 0.350482400 | 0 | 1 / 1 / 1 |
| 20MSS selective+tail | 27600 | 0.257223678 | 1 (1380B) | 1 / 1 / 1 |
| 21MSS selective | 28980 | 0.350597120 | 0 | 1 / 1 / 1 |
| 21MSS selective+tail | 28980 | 0.350597120 | 0 | 1 / 1 / 1 |

20MSS에서 FCT는 selective 대비 **−26.608675%**, baseline 대비 **+2.271782%**다. admission은0.201165760초의 original seq26221·1380B·tx_id22이며 FIN+ACK를 기존 송신 함수가 정상 처리했다. 같은 ACK에서 ordinary sender가19번 segment를 먼저 보내고 남은 정상 window가0인 상태에서20번을 추가 허용했다. 실제 pipe는13800→15180B, admission 당시 cwnd는13800B 그대로여서 정확히1MSS 추가 한도다. receiver right edge33554433과 close-on-empty1을 확인했다. 추가 tail의 후속 재전송은 없었다.

여기서 cwnd 불변은 **추가 송신 함수가 실행되는 순간**의 검증이다. 추가 flight 때문에 이후 기본 recovery 입력도 달라진다. tail의 deadline 시각에는 stock recovery가 cwnd15180B를 설정하며, 전체 cwnd 궤적이 selective와 동일하다는 뜻이 아니다. 정책은 cwnd 값을 직접 늘리지 않고1MSS의 추가 flight를 허용했으며, 그 뒤의 congestion/recovery accounting은 기존 함수가 수행했다.

head 첫 RETX는 selective와 tail 모두0.207108958초이고 같은6.631518ms deadline을 지켰다. 대기는 첫 손실 의심 이후 연장되지 않았다. 마지막 새 데이터가 receiver에 이미 도착한 상태에서 head 재전송이 도착해 앱27600B가0.257223678초에 전달됐다. 이는 잘못된 positive hint의 실제 손실 대기 비용을 완전히 없앤 결과는 아니다.

21MSS에서는 wait 중7개의 체크 모두 `MORE_THAN_ONE_MSS`로 생략됐으며 완료 시간도 같았다. 이것은 해당 경계의 관측 결과다. 실제 수신 창이 막힌 경우·추가 tail 자체의 손실·ECN/RTO 개입은 이5조건에서 검증하지 않았다. receiver window guard는 기본 송신 함수처럼 payload의 right edge를 검사하며, FIN의 추가 sequence 공간 경계도 별도 검증하지 않았다.

[micro 작은 요약](assets/20261013-orbit-tail/micro/results.csv)과 [직접 감사](assets/20261013-orbit-tail/micro-audit.json)에 실제 admission/TX/pipe/deadline 및 기존 V2 OFF measurement hash 동등성을 남겼다. 다섯 조건은 통계적 반복이 아니며 추가 실행이나 성과를 본 뒤 바꾼 parameter는 없다.

## 완료한 LEO5 결과와 전체10조건 검증

LEO5조건도 모두 성공했다. 100GB app가200초 동안 계속 보내므로 자연 tail에서는 `APPLICATION_OPEN`으로3회, 주입 손실 tail에서는5회 생략했고 **추가 admission은 모두0**이다. tail는 이번 bulk 결과에서 추가 이득을 만들지 않았다. 아래 selective+tail는 기존 selective 동작을 포함한다.

| 자연 LEO 조건 | ordered receiver bytes / 200초 | Mbps | RETX / recovery | distinct drops | 추가 tail |
|---|---:|---:|---:|---:|---:|
| baseline | 238608900 | 9.5443560 | 523 / 41 | 499 | 0 |
| selective | 238662720 | 9.5465088 | 507 / 40 | 486 | 0 |
| selective+tail | 238662720 | 9.5465088 | 507 / 40 | 486 | 0 |

baseline 대비 **+0.022556%**는 기존 selective의 작은 이득이다. selective와 tail의11개 legacy CSV(별도 tail observer·wall profiling 제외)가 byte-identical했다. 첫2.5초 창 `[25.7,28.2)`은9.485568→9.622464Mbps, RETX/recovery3/1→0/0이다. 뒤2.5초 창 `[74.5,77.0)`은9.626880→9.618048Mbps, 0/0→12/2로 나빴고 그 창의 selective wait는0회다. 전체 RETX 감소를 모두 독립적으로 확인한 허위 재전송으로 분류하지 않는다. 이 bulk는 미완료이므로 FCT가 없다.

실제 original old-flight loss의 baseline/tail pair는 flow0·tx_id21820·seq29681041·payload1380B·TX26.152017749초·receiver node1585/device1의 PhyRxDrop26.235726816초로 동일하다. drop 전 해당 seq의 RETX는 두 조건 모두 없었다. drop 뒤 첫 RETX까지49.468699→55.204660ms로 **추가5.735961ms**이고, tail admission0이므로 이전 selective 손실 대기 비용을 그대로 재현했다. 이는 한 matched drop의 추가 간격이며 모든 실제 손실의 보장 상한이나 전체 회복 시간은 아니다. 전체 수신량238604760→238606140B는1MSS 차이(+0.000578%)다. RETX522→521, recovery41→41, distinct drops500→500이며 이를 tail의 개선이라고 부르지 않는다.

[최종10조건 요약](assets/20261013-orbit-tail/final/results.csv), case별 summary/manifest/config/schedule/정책 trace는 [final/](assets/20261013-orbit-tail/final/)에 있다. [비교 영수증](assets/20261013-orbit-tail/comparison.json)은 선언된 정확한10개 case set, native CLI, finite size, selective hints·forecast hash, contrast별 config·static/dynamic state·schedule, 동일 runner/source/dependencies/patch/runtime를 확인했다. 기존 V2 control의 measurement hash도 micro baseline9개/selective10개, 자연 baseline10개/selective11개, 실제 손실 baseline12개와 새 tail↔기존 실제 손실 selective13개에서 일치한다. 21MSS 무작동 pair의10개 legacy CSV도 byte-identical했다. wall profiling과 정책의 별도 tail-check observer는 이 동등성 범위에서 제외했다.

모든10조건의 policy·runner·실행 바이너리는 같다. 실행 manifest의 repo ref는 `46d881046f76b93e5ae33f60bf638acc26ee5ff1`와 `66b2409f722bc68e3a4973254ceb599c3d6b5892`를 그대로 보존했으며, 두 ref 사이에서도 해당 source/dependency/runner/patch/runtime hash는 모두 같음을 확인했다. 완료10조건의 simulation wall 합은305.808134초이며 build·input/output hashing·analysis·archive 시간은 제외한다. simulation 실패나 추가 조건은 없고, 결과가 없는 두 development build는 simulation attempt로 세지 않는다.

소스 freeze 이후 all-pair 비교에는 postprocessing만 보강해 zero-admission 원본 동등성과 이전 주입 selective control을 추가했다. 실행 당시 `compare-at-launch.py`와 이후 `compare.py`를 따로 보존하고 receipt의 phase/hash로 구분했다. 실행 source나 원본 manifest를 새 helper에서 나온 것처럼 고치지 않았다. [final build log](assets/20261013-orbit-tail/final-build-log.txt)와 [development log](assets/20261013-orbit-tail/development-before-ordinary-guard/build-log.txt)도 각 readiness의 hash와 일치한다.

## 원본 보관과 제한된 결론

원본10조건은 `output/tail-queue-raw/orbit-tail-20261013.tar.gz`로 준비했다. **50,758,951B**, SHA256 `61ee4e5848e793447d030ed1349dc5927e9e830141c8d1ca5164e77b5f14fbfe`,178개 member의 size/hash를 stream 재검증했다. [inventory](assets/20261013-orbit-tail/raw-inventory.json)가 기준이며 [공유 Release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-tail-queue-20261013) 게시·원격 검증은 parent가 맡는다. 재현 방법은 [도구 README](../../code/orbit-tail/README.md)에 있다.

한 finite-flow 조건에서는 마지막 데이터 한 개를 미리 보내 selective의 추가 완료 비용을 줄였다. baseline보다 빠르지는 않았고, 한 MSS보다 많이 남거나 계속 보내는 bulk에는 작동하지 않았다. 추가 tail의 실제 손실, receiver zero-window/FIN sequence-space 경계, ECN/RTO 개입, 경쟁 흐름, 예측 오차·반복 seed는 검증하지 않았다. cwnd 불변은 admission 순간에 한정되며 이후 native recovery 궤적은 달라진다. 이를 일반적인 LEO 처리량 개선이나 현대 Linux RACK/TLP의 대체로 제시하지 않는다.
