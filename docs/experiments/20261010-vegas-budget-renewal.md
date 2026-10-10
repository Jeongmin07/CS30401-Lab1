# Vegas 갱신 후 혼잡 추정 여유 보존 — v2

## 결론

**이번 보수적 변경을 v1의 대체 개선안으로 채택하지 않는다.** 위성 경로에서 기본 Vegas보다 처리량은 늘지만 v1보다 22.51% 낮고, 지연 증가+CUBIC 경쟁의 평균 실제 큐 대기시간은 v1보다 30.18% 늘었다. 갱신 순간의 내부 혼잡 추정 여유를 보존하는 수학적 조건은 지켰지만, 목표했던 실제 혼잡 비용의 일관된 감소는 얻지 못했다. 이 기록은 조원들의 중복 시도를 줄이기 위한 검증 근거다. v2를 최종 보고서의 주된 개선안으로 묶도록 제안하지 않는다.

[PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14)의 같은 문제를 이어서 검증했다. v1의 patch/코드/결과/원본은 수정하지 않았다. 조원 3명은 별도 노트북에서 자기 AI를 사용한다. 이 문서는 각 AI가 현재 해석과 근거를 확인하고 반박할 수 있도록 작성했으며, 공통 프롬프트나 역할을 강제하지 않는다. 내부 AI 검토는 다른 두 조원의 실제 검토를 대신하지 않는다. 공통 PLAN/팀 최종 주제/보고서/병합을 확정하지 않았다.

## 문제와 실행 전 선언

v1은 최근 20개 유효 cycle의 최소 SRTT 전체를 기준 RTT로 올렸다. LEO에서 큰 이득을 얻었지만 CUBIC이 만드는 큐 지연도 기준값에 흡수했다. 평평한 RTT만으로 빈 큐를 증명할 수 없다는 점은 [RFC6817 §4.4](https://www.rfc-editor.org/rfc/rfc6817.html#section-4.4)의 지연 기반 제어 예와도 일치한다. 이번에는 안정성 임계값을 맞추거나 새로운 탐색 시간을 도입하지 않고 원래 Vegas의 beta=4 패킷 추정 여유를 재사용했다.

현재 segment window `w`, 최근 20개 유효 cycle의 최소 SRTT `R`에서 `C=floor(R*(w-beta)/w)`를 정수 ns로 계산한다. `w<=beta`이면 갱신하지 않는다. 원본 double 계산에서도 `diff>=beta`인지 확인하고 아니면 거부한다. 기존 `C-oldBase>=1ms` 상승 조건, 현재 cycle 포함, CA_OPEN/샘플>2/CA window 조건을 유지한다. 갱신 후보를 거부하면 history를 유지한다. 성공한 갱신 뒤와 기존 invalid cycle·ENABLE·DISABLE 전이 때 history를 비운다. 기존 하향 최소값, startup/loss recovery, +/-1MSS 결정은 그대로다. 새 switch 기본값은 off다.

`R<=현재 cycle 최소 M`이므로 갱신 직후 실수형 내부 추정 `w*(1-C/M)>=beta`, 원래 정수 `diff=w-floor(w*C/M)>=beta`다. **실제 큐4패킷 보장, 경로/혼잡 식별, 누적 기준 상승 상한은 아니다.** 반복 갱신과 지속 큐 흡수는 여전히 가능하다. 실제 입력은 raw RTT가 아니라 소켓 SRTT다.

실행 전10개 matched 조건과 호환 검증을 commit `ac133157c5faa3dac56534ab105cd2ed804fd12c`에 선언했다. 200초,100Mbps,q100,seed123456789, 단독 고정/45->48ms one-way step100s/각 CUBIC competitor80s/제공된 Seoul-London LEO를 기본 Vegas와 v2로 실행했다. 결과 후 정책/20cycle/1ms/beta 설정을 바꾸지 않았다. 파라미터 탐색이나 숨긴 재실행은 없다. 원본 v1 방식도 새 binary에서 고정 경쟁과 LEO로 실행했다.

## 관측 결과

단독은 같은 전체 200초 app delivery goodput이다.

| 조건 | 기본 Vegas | v1 최근 최소 전체 갱신 | v2 beta 여유 보존 |
|---|---:|---:|---:|
| 고정90ms RTT |56.2704|56.2704|56.2704|
| RTT90->96ms 증가 |33.8117|68.3846|50.0810|
| 제공된 LEO |41.5113|69.3432|53.7309|

단위는 Mbps. v2의 LEO 이득은 기본 대비 29.4367%, v1 대비 −22.5146%다. v2 LEO 갱신은 123.587678350s,189.549221350s 두 번이며 초기2.3s의 v1 갱신은 발생하지 않았다. 갱신 후 실제 정수 diff는 두 번 모두 5, 동일 cycle cwnd는1MSS 감소했다. v1에서는 해당 후반 갱신의 diff가 1이고1MSS 증가했다. v2 첫 후반 history min91.663461ms에서 후보91.009889ms를 사용했고, 두 번째는99.255491->98.367298ms였다. 이 상태 전이와 감소한 처리량을 함께 관측했으며, v1 이득 전체를 후반 두 경로 변경만으로 설명하지 않는다.

아래는 **두 흐름이 모두 활성인 같은80–200초** 결과다. 각 TCP 몫과 합계 모두120초로 나눴다. 실제 forward device FIFO의 enqueue->dequeue 평균 대기시간이며 serialization/propagation을 제외하고0 대기를 포함한다.

| 고정 경로+CUBIC | 기본 | v1 | v2 |
|---|---:|---:|---:|
| Vegas Mbps |37.3433|38.4198|34.0060|
| CUBIC Mbps |55.9401|55.3829|59.6232|
| 합계 Mbps |93.2834|93.8027|93.6291|
| Jain |.96178|.96833|.93035|
| 평균 큐 대기 ms |4.0348|4.7240|4.6080|
| TcDrop 행 |204|186|183|

| RTT 증가+CUBIC | 기본 | v1 | v2 |
|---|---:|---:|---:|
| Vegas Mbps |19.5320|37.0452|26.2614|
| CUBIC Mbps |72.7560|56.0532|67.0523|
| 합계 Mbps |92.2880|93.0984|93.3137|
| Jain |.75041|.95998|.83957|
| 평균 큐 대기 ms |3.8479|4.4340|5.7721|
| TcDrop 행 |189|199|190|

v2 고정 경로 경쟁의 전체 경쟁 평균은 v1보다 조금 낮지만, 마지막 180–200초 평균은7.7647ms로 v1의6.3205ms보다 길다. 지연 증가 경쟁에서도 마지막 평균 8.4708ms는 v1의7.0063ms보다 길다. 따라서 ‘큐 지연을 줄였다’고 일반화하지 않는다. v2는 step 경쟁의 aggregate/TcDrop 일부 지표에서는 v1보다 낫지만, Vegas 몫/공정성/큐 지연을 일관되게 개선하지 못했다. 다른 CC의 점유가 함께 바뀌므로 내부 RTT 기준 상승의 감소를 실제 큐 감소와 동일시할 수 없다.

고정 경쟁 갱신 횟수28->13, 최대 갱신 기준99.452851->95.701028ms; step 경쟁22->13,106.000245->102.621483ms로 줄었다. **고정 경로에서도 13번 갱신했으므로 지속 큐 오인 문제는 남는다.** LEO에는 직접 queue 관측이 없으므로 SRTT에서 지리적 RTT를 빼 실제 queue delay라고 부르지 않는다. TcDrop과 device queue drop은 별개이며 QueueDrop=0은 network loss=0이 아니다.

## 검증과 재현

- 10/10 본 실행 완료, matrix 실제520.093초(two workers).12개 primary run은 모두 exit0. 개별 본 실행15.331–355.586초, 별도 legacy compatibility36.780/439.663초다. 동시에 다른 분석/빌드를 실행했으므로 노트북 성능 benchmark로 쓰지 않는다.
- 기존 두 분석기로 app 합산/bin/actual socket/delay/queue conservation을10/10 교차 확인했다. 원본 분석은8 micro와2 LEO가 겹쳐 실행된 별도 matrix다. merge receipt는 실제 source/commit 같음과 완결/중복 없음을 확인하며 합산 전체 wall-time을 발명하지 않는다.
- 독립 budget audit은12개 primary run의26,223개 상태 행,61개 갱신(v2 budget30개+legacy31개)을 재구성해0 errors. v2 accepted 갱신의 최소 정수 diff는5. 후보 exact integer floor/history/상승 gate/state/cwnd/ssthresh/count를 확인했다. 이 Python double 감사가 ns-3 Time 변환의 모든 반올림 경계까지 bit-identical함을 주장하지 않는다; C++ guard는 실제 원본 계산을 실행한다.
- 기본 동작 5개와 legacy2개에서 기존 measurement CSV131/131개가 bytes/SHA256까지 일치했다. versioned Vegas state schema와 wall-clock timing은 이 호환 비교에서 제외했다.
- 깨끗한 공식 image volume+launch commit의 별도 clone에 complete patch를 적용하고 새로 build해 대표2조건(고정 경쟁v2/LEOv2)을 재실행했다. state24개 필드를 포함한 measurement CSV37/37개, 조건/policy/source/fullpatch/executable/shared libraries가 일치했다. fresh build122.454초, fresh cases104.270/216.309초. 초기 local clone2회는 소스 ownership trust 오류로 실패했으며 시뮬레이션은 시작되지 않았다. 해당 setup 로그를 보존하고 **격리된 컨테이너** Git trust를 설정해 복사했다; 호스트 Git 전역 설정은 바꾸지 않았다.
- v1/v2 baseline 비교는 불일치0, 비교표262행을 생성했다. 같은 입력의 결정적 재현이지 통계적 반복 표본이 아니다.

[실행/분석/비교 코드](../../code/vegas-study/v2/README.md), [3방향 비교](../../code/vegas-study/v2/evidence/comparison/compare.csv), [원본 app/queue 결과표](../../code/vegas-study/v2/evidence/results.csv), [독립 감사](../../code/vegas-study/v2/evidence/budget-audit.json), [호환 검증](../../code/vegas-study/v2/evidence/compatibility.json), [fresh 비교](../../code/vegas-study/v2/evidence/replay-comparison.json).

중간 분석의 legacy label `first-false-renew` [90.194745440,91.958450720)는 **v1 최초 오갱신 history를 공통 비교 구간으로 사용한 것**이며 실제 v2 최초 history가 아니다. 원본 분석/label은 보존하고 merge metadata에서 바로잡았다. 향후 실행 helper의 label은 `v1-false-reference`로 명확히 바꿨다. 분석 후 metadata 설명만 수정했으며 simulation 코드나 결과값은 바꾸지 않았다.

원본 archive는 [vegas-budget-20261010](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-budget-20261010)에 공유한다.1,570,260,935bytes, SHA256 `780baeaf73468f4b914f9c49abf3048a480c9275ed2b49518c826ad9ce67bf4a`;389개 파일의 size/hash를 독립 stream 검증했다. 제공된 constellation state/ns3tree/build/binary는 포함하지 않는다. byte-identical fresh replay raw CSV는 중복하지 않고 원본 대비 비교/실행/실패 로그와 manifests를 넣었다. v1 원본 release는 그대로다.

## 범위와 다음 연구 판단

이 실험은 단일 제공 위성 경로, deterministic200초,1개 CUBIC competitor와 한 synthetic step이다. 다양한 routing timing/속도/큐/경쟁 흐름 수/손실 모델의 일반적인 우월성은 미검증이다. 잘 알려진 최소 RTT의 persistent-congestion 식별 한계를 해결한 새 발명이라고 주장하지 않는다.

v1의 큰 단독 LEO 이득과 혼잡 비용은 유효한 근거로 남는다. v2는 ‘기존 beta를 남기면 큐 비용도 줄어들 것’이라는 가설을 지지하지 않아 주된 개선안에서 제외한다. 더 진행한다면 경로 변화에 대한 추가 정보가 얼마나 정확하고 빨라야 도움이 되는지, 혹은 실제 큐를 낮춰 확인하는 탐색의 비용이 얼마인지 **별도 가설과 대조군**으로 평가해야 한다. supplied path truth를 입력하는 경우 정보 지원 benchmark로 표시하고 endpoint-only 해결책과 구분해야 한다.
