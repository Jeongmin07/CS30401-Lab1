# 공유 손실 대기 중 마지막 새 데이터 한 개의 추가 송신

2026-10-13, kim-seongchan. **실행 전 선언**이다. 기존 [selective V2](20261012-orbit-loss.md)의 source·원본·결과는 수정하지 않는다. 이 실험은 ns-3 CUBIC/SACK/PRR의 제한된 추가 송신 허용량이며 RFC8985 TLP 구현이나 개선 보장이 아니다.

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
