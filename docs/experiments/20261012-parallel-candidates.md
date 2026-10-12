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

현재 문서는 실행 시작의 기록이다. 결과는 각각의 실험 문서와 아래 후속 공유 기록에 추가한다.
