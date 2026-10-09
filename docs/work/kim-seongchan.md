# 작업 인수인계: kim-seongchan

- 담당 조원: kim-seongchan
- 갱신 날짜: 2026-10-09 (KST)
- 담당 Issue: <https://github.com/Jeongmin07/CS30401-Lab1/issues/1>
- 작업 브랜치: `docs/team-ai-workflow`
- PR: <https://github.com/Jeongmin07/CS30401-Lab1/pull/2>
- 현재 상태: 문서와 양식 검증 완료, 조원 검토 요청

## 이번 작업과 수정 범위

조원 3명이 별도 노트북에서 각자 AI를 사용한다는 맥락과 GitHub를 통한 공유 방법을 정리한다. README, AGENTS.md, 협업 안내, 새 AI용 프롬프트, 작업/실험 기록 템플릿, GitHub Issue/PR 양식, 생성 결과물 제외 규칙을 추가한다.

## 다른 조원 작업에서 확인한 내용

작업 시작 시 공유 저장소의 `main`은 `20fad971ec537709b1fb28a415503acc8f0f4c59`였고 README와 Python `.gitignore`만 있었다. 열린 PR과 기존 Issue는 없었다. 이후 다른 조원이 push한 내용과 로컬 작업은 별도 확인이 필요하다.

기존 `kim-seongchan/cs30401-2026f-lab1-team05`에는 초기 Docker 실행/테스트 파일이 있지만, 이 PR에서 이 저장소로 옮기지는 않는다. 공통 실행 파일 통합은 별도 작업 후보로 남겼다.

## 완료한 일과 근거

- `AGENTS.md`: 다른 조원들의 Issue, Draft PR, 브랜치 파일을 먼저 확인하는 지침.
- `docs/START_HERE.md`: 다른 조원의 새 AI 채팅에 붙여 넣을 맥락과 작업 프롬프트.
- `docs/TEAM_WORKFLOW.md`: 중간 작업/코드/실험 공유, 브랜치 소유 범위, 관측과 가설 구분, Docker patch 공유.
- `docs/PLAN.md`: 합의된 환경과 아직 정하지 않은 담당/연구 조건을 구분.
- `.github/`: Issue와 PR 작성 양식.
- `docs/templates/`: 작업과 실험 기록 양식.

## 관측 / 가설 / 검증 / 미확인

관측: GitHub CLI로 공유 저장소의 읽기/쓰기 접근을 확인했다. 이 작업에서 시뮬레이션을 실행하거나 TCP 코드를 변경한 것은 없다.

검증:

- Python으로 Markdown 내부 링크 6개의 파일 존재를 확인했다.
- PyYAML로 Issue 양식과 설정 파일을 파싱했다. 필드 6개의 ID 중복, 입력 타입, 필수 입력값 타입을 확인했다.
- `git check-ignore --no-index`로 생성 결과 경로 7개가 제외되고 문서/작은 그래프/patch/의존성 파일 경로 6개는 공유 가능함을 확인했다.
- `git diff main...HEAD --check`로 공백 오류가 없음을 확인했다.

미확인: 다른 조원들의 로컬 작업, 각 노트북 환경, 실제 담당 작업과 최종 연구 가설은 아직 확인/합의하지 않았다.

## 다음 작업과 다른 조원에게 필요한 정보

1. 이 PR의 문서가 실제 팀의 작업 방식에 맞는지 검토한다.
2. 각 조원이 `docs/START_HERE.md` 프롬프트를 자기 AI에 전달하고 담당 Issue/수정 범위를 지정한다.
3. 기존 실행 파일 통합과 공통 분석 도구 작성 중 먼저 맡을 작업을 조원끼리 정한다.
