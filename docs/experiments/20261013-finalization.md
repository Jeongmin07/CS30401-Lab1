# 보고서와 독립 재현 패키지 준비

2026-10-13, Seongchan Kim. 사용자가 추가 알고리즘 개발을 마치고 최종 구현 고정, IEEE 영문 보고서, 독립 재현과 제출 패키지를 준비하도록 지시했다. 기존 PR16의 후속이며 다른 조원의 원본과 과거 연구 기록은 보존한다. 보고서 저자는 사용자가 확인한 Seongchan Kim, Jeongmin Kim, Jaehwan Kang, Team 5다. 마감은 10월13일 23:59 KST이며 피드백의 일주일 일정은 적용하지 않는다.

## 고정할 주장과 실행 설정

주 연구는 예측한 경로 단축에서 이미 보낸 원본 중 일부의 손실 판정을 한 기한 안에서 선택적으로 기다리는 방법과, 그 대기 중 마지막 원본 segment 하나를 제한적으로 허용하는 보완이다. 실행 profile은 selective+tail ON, native pacing OFF로 명시하며 C++의 전역 기본값을 바꾸지 않는다. 원본 대조는 두 기능 OFF다. 페이싱은 기존 큐 진단·적용 한계 대조로만 ON을 실행한다.

재전송3→0회와 복구 진입1→0회를 구분한다. 전체 goodput +0.02256%는 작다. 짧은 파일의0.257224초는 원본0.251510초보다 빠른 성과가 아니라 이전 대기0.350482초의 비용을 완화한 결과다. 실제 old-flight 손실의 추가5.735961ms와 잘못된 예측·21MSS 경계·bulk tail 무작동을 남긴다. 큐 포화의 직접 메커니즘과 경로 변경 지연 대조를 기술하고, 모든 원인의 확정·모든 LEO 환경·현대 Linux TCP의 결함으로 일반화하지 않는다.

보고서는 과제의 필수 순서 Introduction, Problem Statement, Proposed Ideas, Experiment Setup, Evaluation, Conclusion을 따른다. IEEE conference class의 두 단·10pt 본문과 기본 여백을 유지한다. Sections1–6은 최대6쪽이며 참고문헌·부록은 별도다. 네 과거 후보의 상세 수치·서로 다른 패치 버전은 이 제출 보고서 범위에서 제외하고 기존 GitHub 기록에 보존한다. 본문에 남기는 모든 표·그림·수치는 독립 패키지에서 생성할 수 있어야 한다.

## 병렬 소유 범위

| 내부 담당 | 새 소유 범위 | 작업 |
| --- | --- | --- |
| review_baselines_and_handoff | code/lab1-final의 report/ 제외, 독립 재현 문서/assets | standalone 실행·분석·공식 patch export·깨끗한 runtime 재현 |
| review_cubic_study | code/lab1-final/report/ | 영문 LaTeX·벡터 그림·표·수치 연결 |
| audit_research_handoff | 새 report-facts 문서/assets | 원본 과제 PDF·실험 주장·수치·경계 조건 감사 |
| 이 채팅 root | 본 공통 기록, Git/PR, PDF compile/render, 제출 ZIP·공유 검증 | 참고문헌 확인·소스 checkpoint·최종 공유 |

이는 이 채팅 안의 분담이며 다른 조원이 사용하는 외부 AI에게 역할을 배정하는 작업이 아니다.

## 재현 전에 정한 고정 범위

새 ns-3 정책이나 새 topology/APSP를 만들지 않는다. 기존 frozen standalone patch 두 개를 별도 깨끗한 공식 volume에 적용한다. 주 runtime은 queue-pacing SHA `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808`, 큐 비교 runtime은 queue-backpressure SHA `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f`다. CUBIC 정책은 원래 tail/선택적 대기 버전 그대로이며 새 package adapter는 경로·Git 없는 실행·staged diff 확인 등 재현 절차만 바꾼다.

보고서 실행 매핑은22개이며 실제 동일 명령 alias3개를 제외한 **19개의 고정 실행**을 재현한다. 주 runtime16개는 core10, native/capacity pacing2, selected finite1, startup genuine-loss pair2, T75→T78 routing counterfactual1이다. 별도 큐 runtime3개는 current/FIFO/CoDel이다. pace OFF는 core 자연 tail, safety micro-original/current는 core micro-base/micro-tail과 같은 명령·설정·입력임을 먼저 검증한 뒤 alias한다. selective/tail을 결과가 같다는 이유로 합치거나 다른 runtime의 BP control을 alias하지 않는다.

공식 이미지 digest는 `3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`, 원본 ns-3 HEAD는 `99bc6f733274475b7a6e804128651e17ee2a2536`다. 제공 cached state를 사용하며 CPU2·4GiB·build1job·조건별600초 상한을 둔다. source/runtime/build receipt와 실행 source checkpoint를 먼저 공유하고, 실행 중 바꾸지 않는다. 공식 `make_patch.sh`는 source를 stage하므로 staged+unstaged를 모두 확인한다. 공식 export가 기존 patch와 byte-identical인지 검사한다. 새 build SHA와 이전 build SHA의 일치를 가정하지 않고 source·입력·정책과 실제 출력의 동일성을 별도 확인한다.

대용량 원본은 package와 Git에서 제외하고 별도 원본 보관으로 연결한다. 제출 ZIP은 report.pdf, README.md, code/이며 상태·시뮬레이션 로그·전체 ns-3 source·build를 포함하지 않는다. 표/그림 생성에 외부 Python 패키지를 사용하면 uv의 pyproject.toml/uv.lock을 제공한다. 새 환경에서 ZIP의 코드만으로 실행해 보고서 수치·표·그림 입력을 확인한다.

## 현재 상태

과제 PDF와 원본 수치 검토, source packaging, 영문 원고를 병렬 준비 중이다. 새 runtime build·시뮬레이션 전에 최종 source checkpoint를 남긴다. 보고서 시각 검사·실제 재현·제출 파일 검증 전에는 최종 완료를 주장하지 않는다. KLMS 업로드, 개인 Contribution Survey 제출, 팀 PR 병합은 이 준비 작업에 포함하지 않는다.
