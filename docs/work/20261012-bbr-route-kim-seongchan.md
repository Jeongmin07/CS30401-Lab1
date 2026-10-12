# BBR 동적 경로 대응 진단 — 2026-10-12

- 담당: kim-seongchan의 이번 채팅. 조원 3명이 각자 사용하는 AI의 별도 작업과 자동 메시지 시스템을 가정하지 않는다.
- 브랜치: `research/bbr-route-transition`.
- 기준: `origin/main` `b60e8e019053c7d33b853510ec06c3d94ee78faf`.
- 승인 범위: 현대 TCP 중심으로 연구 방향 대폭 수정, PR 공유, 비용을 제한한 경로 탐색과 BBR 진단. 병합은 별도 검토 대상.
- 수정 범위: README/PLAN의 현재 방향, 신규 연구/작업/실험 문서, `code/bbr-route/`의 경로 탐색·관측·실행/분석 도구. 다른 조원의 실험 코드와 기존 결과는 수정하지 않는다.

## 현재 질문

서로 다른 LEO 경로가 공유 병목에 합류할 때 BBR의 이전 대역폭 추정/탐색이 큐·손실·분배 피해를 만드는가? 아직 가설이며, 해당 경로 구조와 피해를 먼저 확인한다. 과제 요건·논문·대안은 [연구 방향 문서](../research/20261012-modern-tcp-direction.md)를 읽는다.

## 시작 시점의 실제 확인

- 열린 PR #10–#15와 기준 commit을 확인했다. PR #15는 `4c3d86f9175cbaf32d4b2b929d2abcbc657898b3`에서 Vegas 후속 실험을 기록 중이다. 그 사용자의 요청을 이번 PR이 대신하지 않는다.
- 공식 이미지 digest: `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`.
- 새 컨테이너 `lab1-bbr-route-20261012`, 새 volume `cs30401-bbr-route-ns3-20261012`, CPU 최대 4개·메모리 최대 6GiB. 이전 실험의 volume을 덮어쓰지 않았다.
- 설치 직후 ns-3 source의 `git status --short`는 비어 있었다. 관측 코드 적용 전의 build는 컨테이너 `/tmp/bbr-route-reference/build`에 보관했다.
- 제공 state는 1,584개 위성 + 지상국 Seoul(1584), London(1585) 둘뿐이다. 첫 forwarding 파일은 55,792 bytes이며 이후 파일에는 delta 갱신/빈 파일이 있다. 중간 파일만 따로 읽어 현재 경로라고 해석할 수 없다.
- 같은 Seoul→London 두 bulk flow를 합류·분리 경로라고 부를 수 없다. 자연 독립 경로 후보는 별도의 제한된 조사 또는 근거 있는 state 생성이 필요하다.

## 진행 중

- 누적 delta를 반영하면서 소수 목적지/시점만 추적하는 예산 제한 경로 탐색 도구.
- BBR 동작을 바꾸지 않고 추정치·송신·수신·큐/drop을 기록하는 opt-in 관측 patch.
- 제공 경로의 단독/공유 병목 진단과 관측 on/off 비교를 실행 전에 선언할 예정.

## 아직 하지 않은 일

- 자연 독립 경로의 합류를 확인하거나 새 state를 생성하지 않았다.
- BBR 진단 실험 결과, 개선 구현, 개선 효과는 아직 없다.
- CUBIC HyStart나 BBR RTprop 대안은 아직 실행하지 않았다.

다른 AI는 이 PR의 가설·버전 제한·중단 기준을 검토하고, 담당 조원의 승인 범위에서 대안 진단을 맡으면 된다. PR 검토는 다른 조원이 자기 AI에 PR URL을 읽으라고 요청하는 방식으로 전달할 수 있다.
