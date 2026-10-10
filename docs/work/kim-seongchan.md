# 작업 인수인계: kim-seongchan

## 완료 — Vegas beta 여유 보존 v2, PR14

- 같은 브랜치에서 v1을 보존하고 후속10 matched+2 compatibility 조건을 검증했다. [별도 결정/근거](../experiments/20261010-vegas-budget-renewal.md), [v2 코드/재현](../../code/vegas-study/v2/README.md), [기본/v1/v2 비교](../../code/vegas-study/v2/evidence/comparison/compare.csv).
- **v2를 v1의 대체 개선안으로 채택하지 않는다.** LEO 41.5113 -> 53.7309 Mbps(+29.44%)지만 v1의 69.3432보다 낮고, step+CUBIC 공통80–200초 실제 평균 큐 대기가 v1의 4.4340 -> v2의 5.7721ms로 늘었다. 내부 beta 여유/갱신 횟수 감소가 실제 큐 감소를 보장하지 않는다. v2를 보고서의 주된 개선안에 묶도록 제안하지 않는다.
- Launch `ac133157c5faa3dac56534ab105cd2ed804fd12c`,10/10 양 분석기 통과,12 primary 상태26,223행/갱신61개 독립 감사0오류, 호환131/131 measurement CSV 일치, fresh patch 대표2조건37/37 measurement+source/binary/libs 일치. 같은 입력 결정적 검증이며 무작위 반복 표본이 아니다.
- 원본은 [별도 release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-budget-20261010)에389파일 stream hash 검증 후 공유한다. v1 원본 release와 기존 코드/결과는 그대로다. 초기 fresh clone 권한 오류2회 로그도 보존했다; sim 재시도/결과 후 policy 조정은 없다.
- 공통 PLAN/팀 최종 주제/보고서/병합을 확정하지 않았다. 조원은 세 방식의 같은 구간 처리량/양 흐름/큐/TcDrop을 보고 해석을 검토하면 된다. 별도 AI 프롬프트/역할을 강제하지 않는다.

## 최신 Vegas 후속 실험 — PR14, 2026-10-10 (KST)

- [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14), `experiment/vegas-rtt-renewal`: PR13에서 찾은 오래된 Vegas RTT 기준값 문제를 opt-in 갱신으로 검증했다. [실험 기록](../experiments/20261010-vegas-rtt-renewal.md), [실행/분석/patch](../../code/vegas-study/README.md), [결과표](../../code/vegas-study/evidence/results.csv)를 먼저 읽는다.
- 고정 경로/지연 증가/실제 CUBIC 경쟁/제공된 LEO의 off/on 10개 조건이 완료됐다. 시뮬레이션 launch commit은 `82ad34a975d4b15f8a536527f8ea4f0cf6e41624`; 후속 분석·문서 commit과 구별한다.
- 제공된 200초 LEO 수신 goodput은 41.5113 -> 69.3432 Mbps (+67.0465%). 초기 CA 갱신 효과도 포함하므로 모든 이득을 후반 경로 변경에만 귀속하지 않는다. 단독 고정 조건은 off/on 기록이 같다.
- 혼잡 구별은 아직 해결하지 못했다. 고정 propagation RTT에서도 CUBIC이 만든 실제 큐 지연을 reference에 흡수한다. 경쟁 공통 80–200초에서 Vegas 몫/공정성은 좋아지지만 aggregate 증가는 작고 큐 지연·TcDrop 비용이 존재한다. QueueDrop=0은 TcDrop=0이 아니다.
- 원본과 두 분석기의 app 합산/bin, actual socket/delay/queue/state 기록을 교차 확인했다. 새 공식 volume에서 대표 3조건을 재실행해 measurement CSV 48개가 byte-exact로 일치했다. 기본 동작 보존도 이전 측정 CSV 27개로 확인했다. 내부 AI 감사는 다른 조원의 실제 검토를 대신하지 않는다.
- 변경 범위는 새 `code/vegas-study/`, 이 실험 문서와 본인 인수인계다. PR10–13/이전 CUBIC 코드·원본은 보존했다. 공통 PLAN, 팀 최종 주제, 보고서나 병합을 확정하지 않았다.
- 다음 판단은 이 prototype을 측정된 효과·비용 경계의 연구로 사용할지, 큐 지연 흡수를 줄일 추가 정보/탐색을 구현할지다. 그 경우 필요한 정보와 비용도 측정해야 한다. 조원 3명은 별도 노트북/AI를 사용하며, PR의 근거를 읽고 현재 해석을 비판적으로 검토하면 된다; 별도 프롬프트/역할을 강제하지 않는다.

## 최신 독립 실험 — 2026-10-10 (KST)

- 사용자 요청에 따라 다른 조원 결과를 입력으로 사용하지 않고 Docker에서 23개 조건을 직접 실행했다. 일정표 없이 원인 검증, 최소 변경, 대조군 및 부작용 평가를 진행했다.
- [실험 요약](../experiments/kim-seongchan-20261010-study.md), [영문 결과 문서](../../code/kim-study/EXPERIMENT_NOTE.md), [재현 명령과 코드](../../code/kim-study/README.md)를 공유한다.
- 경로 변경 후 불필요한 CUBIC/SACK 복구 사례를 패킷과 ACK 순서로 검증했다. 구간 goodput 약 +1.44%, 전체 약 +0.023%이며 작은 큐·실제 짧은 흐름 손실에서는 악화되는 조건도 확인했다.
- 논문에 이미 존재하는 재정렬 보호를 새 발명으로 주장하지 않는다. 선택적 활성화의 효과·비용·정보 요구와 적용 범위를 연구 대상으로 삼는다. Vegas·BBR 후보는 아직 원인 검증이 끝나지 않았다.
- PDF는 복수 문제와 아이디어를 허용한다. 본문 6쪽, IEEE 영어 보고서, 원본 로그/상태를 제외한 재현 가능한 제출물이 필요하다. 이 폴더는 최종 보고서나 제출 ZIP이 아니다.
- 변경 범위는 `code/kim-study/`, 본인의 실험 문서와 이 인수인계 기록이다. 팀의 연구 주제나 역할 배분을 합의된 것으로 바꾸지 않았다. 사용자의 지시에 따라 PR 없이 `main`에 직접 push한다.
- 별도 초기화한 볼륨에 공유용 최종 patch를 적용해 23개 조건 모두 재실행했다. 원본 추적 파일 184개와 전체 분석 JSON 23개의 해시가 전부 일치했고 그래프 5개도 잠근 의존성으로 재생성했다. 이는 동일 입력의 결정적 재현 검증이며 통계적 반복 표본이 아니다.

## 이전 협업 문서 작업 기록

아래는 2026-10-09의 문서 작업 이력이다. 당시 읽었던 공유 결과는 이번 독립 실험의 입력이나 근거로 사용하지 않았다.

- 담당 조원: kim-seongchan
- 갱신 날짜: 2026-10-09 (KST)
- 담당 Issue: <https://github.com/Jeongmin07/CS30401-Lab1/issues/1>
- 작업 브랜치: `docs/team-ai-workflow`
- PR: <https://github.com/Jeongmin07/CS30401-Lab1/pull/2>
- 현재 상태: 문서와 양식 검증 완료, 조원 검토 요청

## 이번 작업과 수정 범위

조원 3명이 별도 노트북에서 각자 AI를 사용한다는 맥락과 GitHub를 통한 공유 방법을 정리한다. README, AGENTS.md, 팀 맥락 안내, 작업/실험 기록 템플릿, GitHub Issue/PR 양식, 생성 결과물 제외 규칙을 추가한다. 고정 시작 프롬프트는 사용하지 않고, 기록 양식도 참고용으로 둔다.

## 다른 조원 작업에서 확인한 내용

현재 확인한 `main`은 `fa99ffa6772b1d4d6826b557ad49b74b5b28eb61`이다. [공유 결과](https://github.com/Jeongmin07/CS30401-Lab1/tree/fa99ffa6772b1d4d6826b557ad49b74b5b28eb61/shared-results)의 config, flow summary와 timing CSV를 읽었다. 이 PR에서 해당 실험을 재실행하거나 원본을 수정하지 않았다.

| 기존 run | 시뮬레이션 기간 | CSV 합계 (MB, 10^6 bytes) | `Run simulation` 실제 시간 |
| --- | --- | --- | --- |
| `cubic/q1000_200s` | 200초 | 42.10 | 1,614.73초 (26.91분) |
| `cubic/q100_200s` | 200초 | 35.45 | 1,173.58초 (19.56분) |
| `newreno/q1000_200s` | 200초 | 44.84 | 1,327.70초 (22.13분) |

세 run의 CSV 합계는 122.39MB다. 위 시간은 `timing_results.csv`의 ns 값을 초로 변환한 것이며, CPU 연산과 실행 중 로그 쓰기를 분리한 측정은 아니다. 설정에는 100 Mbit/s, seed 123456789, pacing off가 기록되어 있다. 실행 당시 코드/patch와 하드웨어는 이 결과 파일만으로 확인하지 못했다.

기존에 이 저장소는 README와 Python `.gitignore`만 있었지만, 이후 공유 결과가 추가된 상태를 반영했다. 현재 열린 PR은 이 협업 문서 PR #2이고, Issue #1에서 검토를 요청한다. 다른 조원의 아직 push하지 않은 작업은 보이지 않는다.

기존 `kim-seongchan/cs30401-2026f-lab1-team05`에는 초기 Docker 실행/테스트 파일이 있지만, 이 PR에서 이 저장소로 옮기지는 않는다. 공통 실행 파일 통합은 별도 작업 후보로 남겼다.

## 완료한 일과 근거

- `AGENTS.md`: 다른 조원들의 Issue, Draft PR, 브랜치 파일을 먼저 확인하는 지침.
- `docs/START_HERE.md`: 팀 맥락, 작업할 때 알아야 할 정보와 다른 조원의 결과를 찾는 위치. 정해진 프롬프트는 없음.
- `docs/TEAM_WORKFLOW.md`: 중간 작업/코드/실험 공유, 브랜치 소유 범위, 관측과 가설 구분, Docker patch 공유.
- `docs/PLAN.md`: 합의된 환경과 아직 정하지 않은 담당/연구 조건을 구분.
- `.github/`: Issue와 PR 작성 양식.
- `docs/templates/`: 작업과 실험 기록 참고 양식. 실험의 실제 실행 시간과 원본 보관 링크/해시 항목 포함.
- 대용량 로그 공유: 압축 원본의 공동 보관과 링크, Git에는 재현 정보/작은 요약/그래프 공유. 새 이벤트 로그의 ignore 규칙을 추가하되 기존 결과는 보존.

## 관측 / 가설 / 검증 / 미확인

관측: GitHub CLI로 공유 저장소의 읽기/쓰기 접근을 확인했다. 이 작업에서 시뮬레이션을 실행하거나 TCP 코드를 변경한 것은 없다.

검증:

- Python으로 Markdown 내부 링크 7개의 파일과 연결된 제목(anchor)의 존재를 확인했다.
- PyYAML로 Issue 양식과 설정 파일을 파싱했다. 필드 6개의 ID 중복, 입력 타입, 필수 입력값 타입을 확인했다.
- `git check-ignore --no-index`로 생성 결과 경로 10개가 제외되고 문서/작은 그래프/patch/의존성 파일/새 run의 설정·요약 경로 10개는 공유 가능함을 확인했다. 기존 추적 파일을 제거하는 작업은 하지 않았다.
- `git diff main...HEAD --check`로 공백 오류가 없음을 확인했다.

미확인: 다른 조원들의 로컬 작업, 각 노트북 환경, 실제 담당 작업과 최종 연구 가설은 아직 확인/합의하지 않았다.

## 다음 작업과 다른 조원에게 필요한 정보

1. 이 PR의 문서가 실제 팀의 작업 방식에 맞는지 검토한다.
2. 각 조원이 저장소와 `docs/START_HERE.md`의 팀 맥락을 자기 AI에 알려주고 담당 작업/수정 범위를 편한 말로 요청한다.
3. 기존 실행 파일 통합과 공통 분석 도구 작성 중 먼저 맡을 작업을 조원끼리 정한다.

## 2026-10-10 독립 TCP 연구 후속 실험

사용자 요청에 따라 친구의 결과 파일을 입력으로 쓰지 않고 Docker에서 직접 실험했다. 사용자가 PR 없이 main에 직접 push하도록 지시한 범위다. 아래는 이 조원의 독립 연구 결과이며 팀의 최종 주제 합의를 뜻하지 않는다.

현재 코드는 [독립 실험 번들](../../code/kim-study/README.md), [52개 후속 결과](../../code/kim-study/PHASE2_NOTE.md), [파라미터·배포 가정](../../code/kim-study/PARAMETER_AND_DEPLOYMENT_NOTE.md), [선행 연구](../../code/kim-study/RELATED_WORK_NOTE.md)에 있다. 이전 23개 사례에 후속 52개 사례를 추가했다. 총 75개 case ID에는 같은 조건의 회귀 대조군이 포함되므로 75개의 독립 조건이나 무작위 반복 표본으로 해석하지 않는다.

원인 검증: course ns-3.48 CUBIC/SACK/PRR에서 26.2초 경로 변경 뒤 이미 애플리케이션에 수신된 원본을 다시 전송하는 사례를 ACK/SACK·전송 ID로 연결했다. 기본 임계값 3을 일시적으로 높이면 첫 이벤트 처리량은 1.4432% 늘지만 200초 전체 증가는 0.02256%다. 작은 큐와 두 번째 이벤트에는 악화가 있어 일반적인 처리량 개선으로 주장하지 않는다.

수정과 한계: 알려진 전체 전송 크기가 21 nominal MSS 이하인 경우 연결 전부터 기본 임계값을 유지한다. 첫 패킷이 실제로 손실된 20-MSS 전송은 기존 보호 정책의 1.150124001초에서 기본 TCP와 같은 0.251509920초로 돌아왔다. 중간 손실도 기본 완료 시간을 복원했다. 21-MSS 경계는 포함되며 22-MSS 전송과 마지막 패킷 손실에는 한계가 남는다. 이는 남은 flight에 적응하는 알고리즘이 아니다. 별도의 80-MSS 무손실 지연 감소 대조에서는 같은 변경 채널에서 완료 시간이 0.6115272초에서 0.43094496초로 29.53% 감소했다. 이 수치를 LEO 전체 성능 개선으로 확대하지 않는다.

재현 검증: 새 official volume `cs30401-kim-repro-ns348-v6`에 canonical v6 patch를 적용·빌드하고 75개 사례를 재실행했다. 시뮬레이션 wall time은 3개 이하 동시 실행으로 377.093초이며 빌드·분석·해시·그림 생성 시간은 제외한다. 600개 원시/기존 추적 입력과 75개 전체 분석 파일이 원본과 바이트 단위로 일치했다. [재현 기록](../../code/kim-study/evidence/reproduction_v6.json)에 해시와 provenance가 있다. 공식 `make_patch.sh`로 새 source patch를 다시 내보내 canonical SHA-256 `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`와 동일함도 확인했다. 그림 9종을 새 환경에서 다시 생성했으며 이미지 바이트 동일성은 주장하지 않는다. 원시 로그는 현재 컴퓨터의 `cs30401-kim-study`와 `cs30401-kim-repro-v6` 컨테이너 안 `/tmp/cs30401-study`에 있다. ns-3 소스·빌드 volume과는 별도인 컨테이너 파일이며 Git에는 작은 요약과 재현 정보만 올린다. 다른 컴퓨터에서는 저장소의 README로 Docker 환경을 재구성하고 필요한 원시 로그를 재생성할 수 있다.

보고서: [영어 IEEE 초안](../../code/kim-study/report/kim-study-draft.pdf)과 [편집용 LaTeX](../../code/kim-study/report/kim-study-draft.tex)을 작성·컴파일하고 전체 페이지를 렌더링해 확인했다. 본문 5페이지와 참고문헌 1페이지이며 규정의 본문 6페이지 한도 안이다. Team 5의 세 조원 영문 이름은 아직 확인되지 않아 독립 연구 검토용 초안으로 표시했다. 현재 Linux/RACK 비교, 다른 경로·다중 흐름, 실제 알림 전달은 검증되지 않았다. 후자는 명세서의 고정 실험 횟수 요구가 아니라 결과 적용 범위의 한계다. 최종 제출에는 이름·팀 최종 범위 확정과 개인 설문·3인 발표 준비가 남는다.
