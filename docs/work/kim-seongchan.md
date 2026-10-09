# 작업 인수인계: kim-seongchan

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
