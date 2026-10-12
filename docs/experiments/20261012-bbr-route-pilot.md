# BBR 기본 동작 진단: 제공 경로의 공유 병목

- 담당: kim-seongchan, 2026-10-12 KST.
- 관련 PR: [#16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16).
- 실행 전 선언. 이 기록의 초기 commit에는 결과가 없으며 결과는 후속 commit에서 추가한다.
- 자연 합류 경로가 제공 state에 없으므로 **같은 Seoul→London 경로의 경쟁 진입 진단**부터 수행한다. 이것으로 위성 이동에 따른 독립 경로 합류나 LEO 고유 결함을 입증하지 않는다.

## 질문과 관측

원래 BBR은 이미 활성인 bulk flow의 경로에 두 번째 bulk flow가 시작될 때 최대 대역폭 추정·탐색·cwnd/inflight·송신 속도를 어떻게 바꾸는가? 실제 앱 전달량·큐·drop과 일관되게 연결되는가? 우선 관측 도구의 의미와 비용을 확인한다. 정책 변경은 없다.

## 선언한 작은 실행 집합

| case | 실행 파일 / 계측 | 흐름 시작(초) | 목적 |
| --- | --- | --- | --- |
| reference-solo | 공식 원본 build / 계측 없음 | 0 | 보존된 원본 실행 기준 |
| patched-off-solo | 관측 patch build / 계측 off | 0 | 정책 변경이 없는지 기준 trace와 대조 |
| observed-solo | 관측 patch build / 계측 on | 0 | 계측 on/off의 기존 trace 동등성, BBR 단독 모드 |
| observed-join10 | 관측 patch build / 계측 on | 0, 10 | 두 번째 통신 시작 후 공유 병목 반응 |
| observed-together | 관측 patch build / 계측 on | 0, 0 | 기동 순서 대조; 경로는 항상 같음 |

모든 실행은 공식 제공 200초 state의 첫 40초, 100ms 갱신, `TcpBbr`, pacing on, 모든 ISL/GSL 100 Mbit/s와 100-packet device queue, seed 123456789, 각 흐름 MaxBytes 100GB를 사용한다. 큐/용량은 이미 저장소에서 사용한 탐색 조건이며 Starlink 실측 보정값이 아니다. 40초는 기존 경로 전환 26초 부근과 경쟁 진입 뒤 30초를 포함하는 비용 제한 출발점이다. 혼합 CUBIC 경쟁이나 새 무선 손실·단절을 추가하지 않는다.

- 전체 창 `[0,40)`, 공통 활성 창 `[10,40)`, 경쟁 진입 창 `[10,15)`를 먼저 정한다. 필요하면 원인을 보기 위한 세부 시간 bin을 추가하되 다른 평가 창으로 성공 수치를 골라 바꾸지 않는다.
- 완료 기준: 원본/patch-off/on 기존 cwnd·RTT·progress·flow CSV의 일치와 새 계측의 흐름 연결 확인. 시간 파일은 wall time 차이가 나므로 byte-match 대상이 아니다.
- 중단: 동작 동등성이 깨지거나 관측 의미가 불명확하면 성능 결론으로 넘어가지 않는다. 큐/손실이나 서비스 피해가 없거나 정상적인 경쟁 분배로 설명되면 이 진단을 개선 대상의 입증으로 쓰지 않는다.
- 실행은 1개씩, 각 wall time 최대 180초로 제한한다. 실제 비용과 원본 파일 크기를 기록한다.

## 재현 준비와 명령

환경: `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`, 새 volume·컨테이너. 원본 build를 patch 전 `/tmp/bbr-route-reference/build`로 복사한다. 원본 binary의 RUNPATH가 새 build를 가리키므로 runner는 `LD_LIBRARY_PATH`를 보존 build로 바꿔 원본 라이브러리를 사용한다.

runner는 실행 commit·runner hash·설치 source diff hash·binary 및 library hash·설정/schedule·static state hash·명령·wall time·output hash를 각 run의 `manifest.json`에 기록하고 기존 run 디렉터리를 덮어쓰지 않는다. 계측 patch·정확한 적용/빌드 명령과 결과 공유 정보는 실제 실행 후 추가한다.

```powershell
docker exec lab1-bbr-route-20261012 python3 /work/code/bbr-route/run_pilot.py reference-solo
# 관측 patch 적용/빌드가 완료된 뒤:
docker exec lab1-bbr-route-20261012 python3 /work/code/bbr-route/run_pilot.py patched-off-solo observed-solo observed-join10 observed-together
```

## 결과 상태

### 완료 및 중단 상태

| 실행 | 실제 wall time | 상태와 범위 |
| --- | ---: | --- |
| reference-solo | 67.0054초 | 성공, 원본 build+라이브러리 |
| patched-off-solo | 75.1311초 | 성공, 초기 관측 patch를 끈 실행 |
| observed-solo 첫 시도 | 13.4637초 | 0.0986 simulated s에 UID 중복 계측 오류로 실패; 성능 결과에서 제외 |
| observed-solo 수정 후 | 79.5237초 | 성공, 실제 앱 수신·큐 집계 및 기존 trace 동등성 검증 |
| observed-join10 | 180.0258초 | wall timeout; 완성된 결과/성능 표에 포함하지 않음 |
| observed-together | — | 앞선 timeout 후 미실행; 이후 합류 주가설 중단으로 실행하지 않음 |

첫 reference 준비는 Git bind mount의 ownership 확인에서 시뮬레이션 실행 전에 중단했다. runner에 이번 `/work` 조회만 허용하는 scoped Git 설정을 넣고 새 run root로 실행했다. 기존 실패 폴더를 덮어쓰지 않았다. 소스/계측 오류와 연구 가설의 중단을 구분한다.

최종 관측 patch SHA256: `ddcad50d06a8e3fc34a79fabb4942e2225d4788488d3db96e2b72a379262c445`. Packet UID는 여러 TCP MSS 조각이 공유하므로 큐 pending 연결에 쓸 수 없다. 수정한 관측은 실제 queued packet 객체와 flow 정합성을 사용한다. 큐 flush 시각·종료 잔여 패킷과 실제 앱 전달량도 기록한다.

- [원본 대 관측 off](assets/20261012-bbr-route/equivalence-original-off.json), [원본 대 수정 관측 on](assets/20261012-bbr-route/equivalence-original-on.json): 동일 조건의 기존 cwnd/RTT/progress/flow CSV 4개 모두 byte-identical. 이 한 조건의 동등성이며 전 조건의 무영향 증명은 아니다.
- [잘못된 비교를 거부하는 검사](assets/20261012-bbr-route/observer-negative-checks.json): 같은 폴더, 실패 실행, 입력/출력 변조 등의 6개 조건을 거부했다. 이 검사는 새 TCP 시뮬레이션 결과가 아니다.
- [수신량·큐 분석](assets/20261012-bbr-route/pilot-analysis/pilot-summary.json), [선언 창 요약](assets/20261012-bbr-route/pilot-analysis/pilot-windows.csv): 실제 수신 총계·flow/port 연결·큐 enqueue/dequeue/pending 보존·원본 해시를 확인했다.

### 완성된 단독 조건의 실제 관측

실제 수신 앱 바이트는 452,307,420B이며 `[0,40)` goodput은 90.4615Mbit/s, `[10,40)`은 93.3465Mbit/s다. 같은 40초의 sender ACK progress 451,763,700B와 혼용하지 않는다. 전체 창에 TcDrop 7,528 **hook events**가 기록됐다. 이 수치와 BBR rate-sample loss-byte 누계를 고유 패킷 손실/재전송 수로 바꾸어 쓰지 않는다. served queue visit의 전체 평균은 0.08885ms, 최댓값 11.4720ms이며, ACK와 양방향 여러 장치 방문을 포함한 값이다. 종단 간 큐 지연이 아니다.

이 결과는 제공 BBR의 관측 기반을 확보한 것이며 새로운 개선을 시험하지 않았다. 평균 처리량이 높다는 사실이나 이 drop count만으로 LEO 경로 변화가 원인이라고 결론 내리지 않는다.

### 원본 공유 위치

[GitHub diagnostic prerelease](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/bbr-route-diagnostics-20261012)의 [압축 원본](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/bbr-route-diagnostics-20261012/bbr-route-diagnostics-20261012.tar.gz)을 받으면 된다. 크기는 10,002,124B, SHA256은 `db389f9a6af331701ad8c15656661a41b83fc1c1092971b62a7f34a5d01ea5a8`이다. [파일별 inventory](assets/20261012-bbr-route/raw-inventory.json)의 70개 텍스트 파일을 전부 대조했고 GitHub asset의 digest/size도 확인했다.

성공한 v2 reference/off, v3 observed-solo와 실패한 첫 관측/timeout 기록을 모두 포함한다. 후기 코드에서 과거 실행한 것으로 취급하지 않도록 각 manifest의 실행 commit을 유지했다. release target은 공유 자료를 묶는 commit이지 모든 실행의 commit이 아니다. 원본 build·generated state·core dump는 archive에 넣지 않았다.

### 후속 판단

가용 대역폭 감소만으로는 지상 경쟁 진입과 다른 TCP 문제를 입증하지 못해 **경로 합류 주가설을 중단**했다. 새 도시 state 생성이나 timeout run의 반복·확장은 진행하지 않는다. 기하 예측·재정렬 예방 후보는 [별도 방향 문서](../research/20261012-predictable-leo-tcp.md)를 읽는다.
