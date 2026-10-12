# 마지막 패킷 추가 송신과 75초 큐 원인 검증

2026-10-13, kim-seongchan. 사용자가 마지막 새 패킷 한 개의 추가 송신을 구현·실험하고75초 큐 원인을 병렬 확인한 뒤 PR에 공유하도록 승인했다. 아래는 새 실행 전 선언이다. 기존 selective V2의 source와 결과는 [이전 기록](20261012-orbit-loss.md)에 보존한다.

기존 실제 손실 대조에서는 대기 중 새 데이터13–19번이 이미 송신됐다. 늦어진 것은20번 한 개였으며, SACK로 확보한 송신 여유가 이미 사용된 상태에서 추가 송신이 가능할지 확인한다. 자연75초에서는 새 방식의 직전 창과 송신자 drop이 더 컸지만 직접적인 장치 큐·flow-control 원인 비교가 없었다. 두 문제를 별도 source volume에서 병렬 진행한다.

| 담당 | 소유 범위 | 고정된 최초 실행 범위 |
| --- | --- | --- |
| 내부 review_baselines_and_handoff | code/orbit-tail, 독립 실험·assets | 같은 최종 binary의10조건:20MSS 실제 손실 micro3·자연 LEO3·같은 실제 old-flight 손실 LEO2·21MSS 경계2 |
| 내부 review_cubic_study | code/orbit-queue, 독립 실험·assets | 원본/selective 자연 LEO10Mbps·q100·200초의 수동 관측2조건. 제공delta와 유효 경로 검사로 안전한 경우만75초 routing 전환을78초로 미루는 대조 최대1조건 |
| 내부 audit_research_handoff | 읽기 검토 | 추가 송신의 FIN·sequence·receiver window·송신량 계산과 큐 계측의 상태변경·대조 범위를 실행 전에 검토 |
| 이 채팅 root | 공통 기록·Git·PR·원본 공유 | 사전 선언/source checkpoint 게시, 결과·한계 통합, byte/hash·원격 게시 확인 |

외부 조원3명의 작업을 다시 배정하거나 시작 프롬프트를 강제하는 구조가 아니다. [Draft PR16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16)과 브랜치 문서를 통해 각자의 AI가 진행 상황을 읽는다.

## 추가 송신의 제약과 비교

[상세 정책과10조건](20261013-orbit-tail.md)에 따라 기본 문턱K3·기존 손실 대기·RTO·일반 송신을 유지한다. 일반 ACK/SACK 처리와 `SendPendingData`가 보통의 여유를 사용한 뒤, 같은 ACK의 새로운 고유 SACK 정보·현재 활성 대기·애플리케이션 종료 의사·남은 payload1..MSS·receiver window·pipe≤cwnd+MSS를 확인한다. episode당 추가 원본 segment는 최대1개다. 이전 SACK를 다시 delivery로 넣거나 cwnd를 늘리지 않으며 기존 `SendDataPacket`의 FIN·송신 callback·rate/재전송 accounting을 사용한다.

이것은 명시적으로 최대1MSS의 추가 송신을 허용하는 실험이다. RFC8985 TLP를 그대로 구현했다고 부르지 않는다. 100GB 자연 흐름에서는 마지막 packet 조건이 없어서 무작동일 수 있다. 21MSS는 두 packet이 아직 남았을 때 우회하지 않는 경계이며 성과를 본 뒤 선택한 크기가 아니다. 실제 허용 seq/bytes·고유 SACK·unsent·pipe/cwnd·receiver window·기한과 실제 원본 TX를 연결한다. 완료 시간뿐 아니라 실제 손실·재전송·전체/고정창 전달량의 비용도 비교한다.

## 큐 원인과 전환 대조

두 자연 조건은0초부터 기존 정책/흐름 이력을 유지한다. 장치별 실제 enqueue/dequeue/occupancy/served wait/serialization busy와 TX queue stop·wake·TrafficControl drop의 장치·사유를 관측한다. 순수 관측이 기존 수신·패킷·cwnd·RTT·drop CSV를 바꾸지 않았는지 확인하고 큐 방문·잔여·drop 보존을 검증한다. SRTT를 장치 queue wait로 대신하지 않는다.

세 번째 대조는 제공 sparse forwarding delta의75초 전환을78초로 지연할 수 있을 때만 실행한다. 정방향/역방향의 모든 영향을 받은100ms frame에서 누적 경로의 누락·loop·후속 override를 확인한다. 기존 static 입력·기하 이동·앞선26.2초 개입을 유지하며 새 topology/APSP를 계산하지 않는다. 변경한delta·그 해시·양방향 실제 경로를 보존한다. 양방향 routing과 링크 선택을 함께 바꾸는 대조면 그 범위를 명시하고 순수 전파 지연 하나의 인과로 부르지 않는다. 안전한 입력 대조를 구성할 수 없으면 실행 전에 중단하고 직접 확인된 큐/stop/drop 원인까지 보고한다.

## 실행 예산과 공유

최초 범위는 tail10조건과 queue2조건, 안전성이 확인된 queue 대조 최대1조건으로 **최대13조건**이다. 별도 공식 이미지/container/volume, CPU2·4GiB·build1job을 사용한다. 각 실행의 실제 시간 상한은600초다. 앞선240초 상한은 이 관측에 짧았던 실행 예산이었으며 과제나 TCP의 시간 제한이 아니다. 새 source/runtime checkpoint를 공유한 후 첫 실행을 시작하고 실행 도중 빌드나 source를 바꾸지 않는다. 실패·timeout·정확성 보수에 따른 재검증은 실제 시도 수와 버전을 분리하며 예산을 자동 확대하지 않는다.

source·runner·runtime·입력·출력·실제 launch commit/dirty 상태를 보존한다. 이전20MSS baseline/selective와 자연 V2 대조의 동일성, 추가 packet의 직접 작동/무작동, 실제 물리 drop 식별자와 그 이후 복구를 검증한다. 큰 원본은 Release에 별도로 압축하고 작은 설정·요약·그림·inventory만 Git에 둔다. parameter sweep·BDP cap 정책·100Mbps 장시간 재시도는 이번 요청의 두 검증 범위에 포함하지 않는다. 팀 최종 주제·main 병합은 이 실험 결과와 구분한다.

완료 결과는 아래에 이어 기록한다.
