# 미래 경로 단축 전후 새 데이터 송신의 짧은 조절

2026-10-12, kim-seongchan/root. 네 후보 병렬 실행 중 송신 조절 담당이다. **실행 전 선언**이며 기존 손실 판정 보호를 사용하지 않는다. 원본 문턱3을 유지하고 패킷 추월 자체를 줄일 수 있는지, 송신을 쉬는 비용이 더 큰지 실제로 비교한다.

입력은 공급 state의 기존 기하 기록과 예정된 경로 변경이다. 각 경로 단축 T에서 양방향 전파 RTT 감소의 절반을 편도 근사 D로 둔다. D는 큐/전송 중 경로 변경을 포함한 실제 패킷 지연 차이의 보장이 아니다. 이전 packet evidence의 실제 지연 차이나 결과를 최적화 입력으로 쓰지 않는다.

기하 기반 작은 두 규칙을 미리 정한다: 짧은 hold `[T-D,T+D)`와 여유를 둔 hold `[T-2D,T+2D)`. 26.2초에서는 총6.634ms와13.268ms다. TCP의 실제 새 데이터 송신 지점에서만 적용하고, 재전송·RTO 경로를 정지시키지 않는다. 끝나는 시각에 pending data를 다시 보내며 close/dispose 때 timer를 취소한다. 이미 네트워크/장치 큐에 들어간 패킷을 소급 정지할 수 없음을 명시한다.

먼저10Mbps/q100/200초 Seoul→London 단일100GB CUBIC의 원본/짧은/여유 hold 세 조건을 실행한다. 정확한 전환은26.2와75.0초이며 고정 평가창 `[25.7,28.2)`, `[74.5,77.0)`과 전체 수신량, 실제 reorder·재전송/복구·drop·SRTT를 함께 본다. SRTT를 직접 측정한 큐 대기로 바꾸어 쓰지 않는다.

다음 실제 손실 경계 대조는stable100Mbps/편도50ms/q2000/4초/20MSS 첫 segment 실제 손실이다. 원본과13.268ms의 false hold `[0.198366,0.211634)`를 비교해 실제 재전송은 진행되고 새 데이터 지연이 얼마나 생기는지 확인한다. 개선이 있다고 주장하기 위한 조건이 아니라 송신 중단 비용을 보기 위한 대조다. 총5조건·각240초 cap이며 새로운 state나 sweep을 생성하지 않는다.

환경은 새 lab1-orbit-order-20261012/container와 cs30401-orbit-order-ns3-20261012/volume, 공식 digest3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4다. 기존 canonical v6 관측 위에 새 hold만 더한 combined patch 한 장을 export하고 설치 diff/runtime/runner/input/output hashes와 명령을 보존한다. 원본/off 대조는 기존 baseline CSV와도 비교한다. 실제 실행/분석 결과는 후속 기록에 추가한다.

## 실제 완료 결과

선언한5조건을 모두 실행·분석했다. [결과표](assets/20261012-orbit-order/export/results.csv), [원본/정책 비교와 검증](assets/20261012-orbit-order/export/comparison.json), [각 조건의 manifest·설정·summary](assets/20261012-orbit-order/export/cases/)에 실제 데이터를 보존했다. 이 정책은 **LEO 처리량·재정렬 개선을 보여주지 않았고, 실제 손실 대조에서 완료 시간 비용이 있었다.**

| 조건 | 전체 앱 goodput Mbps |26.2초 평가창 goodput Mbps| 전체 재전송 / 복구 / TcDrop | 유한 전송 FCT |
|---|---:|---:|---|---:|
| LEO 원본 |9.544356|9.485568|523 / 41 / 499|미완료100GB이므로 보고하지 않음|
| LEO 짧은 hold |9.544356|9.485568|523 / 41 / 499|같음|
| LEO 여유 hold |9.544356|9.485568|523 / 41 / 499|같음|
| 실제 첫 손실 원본,20MSS |전체4초0.0552|해당 없음|1 / 1 / 1|0.251509920초|
| 실제 첫 손실 false hold,20MSS |전체4초0.0552|해당 없음|1 / 1 / 1|0.362097200초|

LEO 세 조건의 실제 앱 수신량은 모두238,608,900B다.26.2초 창에는 원본·짧은·여유 모두 out-of-order wire payload5행, 재전송3회, recovery1회, 관측 drop0회가 남았다.75.0초 창도 goodput9.62688Mbps, out-of-order1행, 재전송·복구0회로 같았다. 행 수는 재정렬 episode 수와 구별한다. 기존 분석의 송수신 transmission tag·original eventual arrival와 drop hook coverage에 따른 불필요한 복구 후보 분류도 줄지 않았다.

실제 hold 시작·종료는 schedule과 나노초 단위로 일치했다. 짧은 hold의 총 설정 시간은9.977ms, 여유 hold는19.954ms이며 해당 구간의 새 데이터 TX는0B였다. 같은 시간창의 원본 새 데이터는 첫 전환에서 각각8,280/13,800B, 두 번째에서5,520/8,280B였다. 따라서 설정만 추가한 결과와 구별되는 송신 시각 변화는 확인했지만, 직접적인 blocked-send-opportunity counter는 없으므로 모든 차이를 gate hit 횟수로 설명하지 않는다. 이미 링크·장치 큐에 들어간 패킷과 한 sender-time 전환의 짧은 hold가 실제 모든 hop의 동적 변경을 막는다고 가정할 수 없다.

LEO 시간 가중 평균 SRTT는148.134825→148.131243/148.132676ms로 거의 같다. 이 값은 직접 측정한 queue wait가 아니며 약0.002–0.004ms 차이를 의미 있는 지연 개선으로 쓰지 않는다. root track에서는 device queue 관측을 추가하지 않았다.

20MSS 대조는 두 실행 모두27,600B를 완전히 전달한 **실제 첫 segment 손실**이다. recovery와 재전송은 두 실행 모두0.200477440초에 진행했고, hold 안에서도 기존 데이터 재전송1회가 확인됐다. 손실 판정 문턱은 실제 모든 관측에서3으로 유지됐다. 그럼에도 새 데이터 송신 중단과 ACK/복구 피드백으로 FCT가110.587280ms, **43.9694%** 늘었다. 직접 재전송을 막지 않는다고 완료 지연 비용까지 없어지는 것은 아니다. 전체4초 goodput은 유한 크기를 같은 분모로 나눠 같으므로 이 대조의 속도 지표로 삼지 않는다.

## 검증·비용·재현

- [재현 README](../../code/orbit-order/README.md)의 combined patch 한 장을 새 공식 volume에 적용해 build `-j1`을 완료한 뒤5회 실행했다. source/runner commit은 `8fd57045e616c29202cc3fd79d4a06fa4cabf777`, runner SHA `21e1554c20fa459bfbf49caa642564f7cc6765e388ad2afb472b32e8e06cfc3b`, full patch SHA `b34eb19f43b64ce2379ecff245f5632efaba78be5cc9bb2e72f420f070cdecd3`다. 기하 입력은 기존2,000행 SHA `49bd5418f2b13bdbf6d703f719d61075f814cc86d44c745651bf797f4e5f656c`를 사용했다.
- [실제 Docker receipt](assets/20261012-orbit-order/environment.json), 각 manifest에 source diff·binary/library·원본 state·조건·명령·출력 SHA를 보존했다. 쌍별 runtime/source/input/runner hash가 같고 policy만 변경됐다. 다른 track의 작성 파일 때문에 `repo_dirty=true`가 기록돼 있으며 이를 clean source commit이라고 부르지 않는다.
- exporter는 모든 raw output의 size/SHA, 실제 app delivery 누계와 FCT·평가창 분모, 실제 hold와 선언 구간 일치, sender TX의 새 sequence bytes0을 검사한다. 과거 canonical-v6 원본 조건과 **8개 original/legacy CSV가 byte-identical**임을 확인했다. 전체 조건의 독립 재현 또는 모든 off 상황에서의 무영향 증명은 아니다.
- simulation wall time은25.977325 /22.571987 /22.308276 /0.032322 /0.032889초, 합계70.922799초다. 이는 빌드·분석·압축·공유 시간을 포함하지 않는다. 새 토폴로지, 파라미터 sweep, seed 반복은 없다.
- [원본 inventory](assets/20261012-orbit-order/raw-inventory.json)는83개 member, 미압축181,168,662B를 압축 안에서 모두 size/SHA 확인했다. `orbit-order-20261012.tar.gz`는30,227,311B, SHA `1470111cdb6c062aee064e8d9d1d80002955e9419341058b29cbe0c9b15bffd2`다. 공유 업로드 기록은 [네 후보 공통 기록](20261012-parallel-candidates.md)에 연결한다. source/build/state는 압축에 포함하지 않는다.

이 두 고정 규칙의 작은 대조는 완료했다. **이 구현과 제공 조건에서 효과가 없고 손실 완료 비용이 있었으므로 확대하지 않는다.** 궤도 기반 정보를 사용하는 모든 pacing 또는 경로별 스케줄링 연구를 반증한 결과는 아니며, 좋은 수치가 나올 때까지 hold 시간을 늘리는 탐색도 하지 않았다.
