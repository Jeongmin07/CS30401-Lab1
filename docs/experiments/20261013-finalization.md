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

독립 ZIP source checkpoint `9a5687b`를 공유한 뒤 새 공식 volume 두 개에서 build와 19개 고정 시뮬레이션을 모두 완료했다. 주 runtime의 원래 분석 16개는 원본 CSV 계약에 일치했다. 별도 BP의 세 시뮬레이션도 성공했지만 최초 엄격 분석은 `bp_outcomes.csv`에서 중단됐다. 원본 계약과 실패한 분석은 보존한다.

독립 검토 결과 BP 세 파일의 차이는 200초 종료 시 pending 행 순서뿐이다. 설치된 원본과 새 `backpressure.h`는 같으며 `std::map<const Packet*,Entry>`의 포인터 순서가 종료 기록으로 출력된다. 헤더·순서 있는 non-pending 원시 바이트·pending 전체 15개 필드와 중복 개수는 정확히 같다. 따라서 **342개 CSV의 바이트 일치와 3개 종료 pending 기록의 전체 필드 일치**로 구분하며, 345개 모두 바이트 일치라고 보고하지 않는다. 새 검증 계약은 결과를 만들지 않으며 이 종료 순서 외 차이는 거부한다.

`analyze.py`와 `merge.py`의 순수 분석 검증만 수정한다. 런타임 patch, controller, build·실험 dispatcher, 기존 원본 계약과 입력·설정은 그대로다. 이 수정은 실행을 다시 돌리는 원인이 아니며 별도 분석 source checkpoint와 새 분석 결과 폴더로 기록한다. 최종 표·그림·PDF·ZIP 검증과 공유는 계속 진행 중이다. KLMS 업로드, 개인 Contribution Survey 제출, 팀 PR 병합은 이 준비 작업에 포함하지 않는다.

## 완성된 보고서와 제출 패키지

[최종 PDF](../../code/lab1-final/report/report.pdf)는 실제 IEEEtran conference 1.8b, 기본 두 단·10pt Times 계열 본문·기본 여백으로 작성한 영문 5쪽이다. 두 번 컴파일한 뒤 다섯 쪽을 모두 렌더링해 표·그림·본문·저자·참고문헌·마지막 두 단 배치를 확인했다. [PDF 검수](assets/20261013-finalization/pdf-qa.json)는 source·실제 새 데이터·PDF hash와 검사 범위를 남긴다. 세 벡터 그림과 Table II는 [새 재현 데이터](../../code/lab1-final/report/report-data.json)에서 잠긴 Matplotlib 환경과 stdlib 표 생성기로 만들었으며, [도표 연결](../../code/lab1-final/report/README.md)에서 재생성한다.

`Lab1_5.zip`은 773,756 bytes, 54개 파일, SHA256 `695af4d2338576c6bfd84a6401521964368303bf735b46dd61005844f48e9595`다. 루트는 `report.pdf`, `README.md`, `code/`이며 로그·state·ns-3 트리·빌드·가상환경·초기 preview는 없다. [ZIP 생성·검수](assets/20261013-finalization/submission-package.json)는 실제 검증한 실행 파일과의 바이트 일치, 검토된 두 분석 파일 수정, 모든 archive member hash를 기록한다. 최종 ZIP을 별도 위치에 추출한 후 공식 이미지의 읽기 전용 단독 mount에서 코드 import·19개 조건·세 alias·두 patch hash·Git 없는 실행도 확인했다. 이는 추가 시뮬레이션이 아닌 최종 포장 검증이다.

보고서 PDF는 185,984 bytes, SHA256 `3cd0da9394f0db36f30810a333c759932518e02a115f32b397845fb6a63cc770`다. 수치와 패킷 증거·재현·시각 검사·포장 검증은 각각 별도 기록이며 어느 하나를 다른 검증으로 대체하지 않는다. Release 업로드와 원격 자산 확인은 아래 공유 기록에서 별도로 완료한다.

## 원격 공유 확인

[검토용 Release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/lab1-final-20261013)는 immutable target `385be59765a670a14e8379caab43e0b82d3e87af`에 연결됐다. `Lab1_5.zip`, `report.pdf`, 새 raw archive 두 개와 `SHA256SUMS.txt`를 게시했고, GitHub가 반환한 다섯 자산의 실제 크기와 SHA256 digest를 로컬 파일에 전부 대조했다. [원격 확인](assets/20261013-finalization/release.json)에 다운로드 주소와 해시가 있다. 별도 [독립 최종 검토](assets/20261013-finalization/independent-review.json)도 archive member·실행 코드·새 데이터·저자·형식·재현 경로에서 막힌 항목이 없음을 확인했다.

준비·재현·문서·포장·공유 작업은 완료됐다. PR16은 팀 검토에 넘기며 KLMS 업로드·개인 Contribution Survey·`main` 병합은 수행하지 않았다.
