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

아직 실행 결과 없음. BBR의 경로 합류 가설·개선 효과·RTprop 제한·HyStart 조기 종료는 이 선언만으로 확인되지 않는다.
