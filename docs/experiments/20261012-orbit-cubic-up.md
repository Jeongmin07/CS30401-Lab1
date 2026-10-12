# CUBIC 경로 증가와 선제 윈도우 확대의 빠른 선별

2026-10-12, 실행 전 선언. 이번 채팅 안의 후보 선별이며 팀의 최종 주제나 조원 역할을 확정하지 않는다.

질문은 자연 경로 증가 때 CUBIC의 실제 윈도우 부족이 링크 유휴와 전달량 감소를 만드는지다. 이미 큰 cwnd나 전파 BDP 계산만으로 필요·불필요를 확정하지 않는다. 제공 state의 증가 전환은121.6초(+3.061ms,1.034980배)와187.4초(+7.231ms,1.079762배)다. RTT를 인위적으로 두 배 늘리거나 새 토폴로지를 만들지 않는다.

먼저 기존10Mbps/q100/200초 CUBIC 원본의 자료와 새100Mbps/q100/200초 단일100GB CUBIC 원본을 비교한다. 시작0초, 서울1584→런던1585, pacing off, 원래MSS1380·SACK·PRR·K3를 유지한다. 새 원본은 별도 공식 이미지·빈ns-3 volume, CPU2·4GiB, build-j1, 개별실행240초 wall cap을 사용한다. timeout은 성공 결과에 섞지 않는다. canonicalv6 관측 위에 passive socket-window와 장치 queue/service 관측만 합친 complete patch를 사용한다.

윈도우 관측은 기존SendPendingData의 AvailableWindow 계산 직후 값을 읽는다. 관측 때문에 BytesInFlight/AvailableWindow를 다시 호출하거나 ACK·cwnd·recovery·timer·routing을 변경하지 않는다. cwnd, 실제 계산된pipe, rwnd, available window, unsent buffer, congestion/socket state, 기존cwnd-limited flag를 보존한다. 전환focus는[26.1,26.6),[74.9,75.4),[121.1,124.1),[186.9,189.9)이며 이 구간은 각 callback을 기록한다. 다른 시간은100ms 표본이다.

장치별100ms queue enqueue/dequeue·served wait·pending·flush 시각과 실제PhyTxBegin/End 직렬화 busy interval을 기록한다. service busy는 전송에 점유된 장치 시간을 뜻하며 app goodput·종단간큐RTT와 다르다. 같은 물리적drop을 layer별로 합쳐 고유 손실이라고 부르지 않는다. 기존tagged TX/Rx/app/drop/retx/event 원본도 유지해 두 번째 후보인 경로 단축 선제drain 검토와 공유한다.

평가는 전체[0,200), 증가 전환의pre[T−0.5,T),post[T,T+0.5),legacy[T−0.5,T+2)와 단축26.2/75.0의 같은창을 미리 고정한다. 수신app의 고유순서전달 바이트를 goodput으로 사용하고, 흐름이100GB를 완료하지 않으면 FCT를 계산하지 않는다. 장치queue·service는 실제 forward 경로에 속하는 장치를 따로 확인하며 모든hop의 평균idle을 종단간병목으로 바꾸지 않는다.

확대 정책 gate는 app data가 남아 있고 rwnd·recovery가 아닌 cwnd 제한이 실제로 존재하며, 증가 후 forward 병목 유휴와 전달량 감소에 연결되는 근거다. gate가 없으면 선제 확대를 구현하지 않고 근거와 함께 중단한다. gate가 있을 때만 opt-in 작은증분·burst 방지·CA_OPEN 조건의 정책을 준비해 같은binary의 원본과 최대1ON 및 필요한micro1을 비교한다. 단순비율이100%이용률·overflow없음을 보장하지 않는다. CUBIC의epoch/Wmax/ssthresh 처리 여부와 실제작동을 별도로 명시한다.

첫simulation은 공유선행commit 이후 진행한다. source/runner/runtime/input/output hashes, 실제명령과시간을 보존하고, 기본OFF 관측의 기존원본measurement 동등성도 확인한다.

## 실제 완료 결과와 선별 종료

총2개 원본을 시도했다. `cubic10-observed200`은29.240159초에 성공했으며 `cubic100-observed200`은240.101341초 wall cap에 도달해 timeout이었다. 정책ON이나 추가OFF 재실행은 하지 않았다. **완료된10Mbps에서는 선제 확대 필요성이 입증되지 않아 구현하지 않았다. 100Mbps 조건은 미검증으로 남긴다.** timeout을 정책 무효나 성공한200초 성능으로 해석하지 않는다.

10Mbps 원본의 앱 전달량은238,608,900B, 전체goodput9.544356Mbps다. 기존원본과 앱·송수신 패킷·drop·congestion event·cwnd·SRTT·progress의 **8개CSV가 size/SHA로 동일**했다. 이 조건에서 추가관측이 원본 궤적을 바꾸지 않은 근거이며 모든 조건의 무영향 증명이나 별도seed 반복은 아니다. [동등성검사](assets/20261012-orbit-cubic-up/equivalence10.json)

| 증가전환·구간 | 앱goodput Mbps | 송신자GSL직렬화점유 | 재전송/복구 | 송신장치평균served queue wait |
| --- | ---: | ---: | ---: | ---: |
| 121.6초직전0.5초 |9.626880|100%|0/0|31.455461ms|
| 121.6초직후0.5초 |9.229440|95.937589%|2/1|8.483792ms|
| 187.4초직전0.5초 |9.626880|100%|0/0|30.587744ms|
| 187.4초직후0.5초 |9.516480|100%|0/0|22.479068ms|

두 전환직전 실제socket은cwnd=pipe=161,460B, rwnd=33,554,432B, available window=0B, unsent약33MB, CA_OPEN, 기존cwnd-limited flag=1이었다. 따라서 **cwnd-limited 자체가 없었다는 결론은 틀리다.** 최대7.98% 증가의187.4초에서는 앞뒤와legacy2.5초 모두 송신자GSL(node1584/device1)이 쉬지 않고 직렬화했다. available0과cwnd-limited1만으로 확대의 성능 필요성을 판정하면 안 된다. 이미 큐 대기가 있는 흐름에서 수신구간 속도가 잠깐 낮아진 것을 송신링크 유휴나 부족한전파BDP로 바꿔 쓰지 않는다.

121.6초 뒤의 짧은송신유휴에는재전송2/복구1과134.032053ms의non-OPEN 상태가 함께 관측됐다. 그 유휴를 순수경로증가의cwnd부족으로 분리해 입증하지 않았다. 두전환 평가창의관측drop은0이다. 장치queue값은 served방문통계이며 실제inflight 전체나종단간queueRTT가 아니다. [완료원본summary](assets/20261012-orbit-cubic-up/cases/cubic10-observed200/summary.json), [13개선언창CSV](assets/20261012-orbit-cubic-up/windows.csv)

100Mbps 시도의 마지막console progress는sim154.79초/wall212.18초였다. 이는최종sim도달시각이아니다.240초에프로세스가종료되어최종service/queue flush와187.4초의완료관측을확보하지못했다. 부분CSV의마지막행도완전하다고보장하지않는다. 원래manifest의timeout/exit_code=null을그대로보존하고 [별도제외기록](assets/20261012-orbit-cubic-up/attempt-exclusion.json)을남겼다. 이조건의처리량·이벤트성공값은평가표에넣지않으며추가실행으로예산을늘리지않았다.

## 출처와 재현 범위

공식image digest3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4, 새container/volume, CPU2·4GiB를 [환경기록](assets/20261012-orbit-cubic-up/environment.json)에확인했다. canonicalv6 SHA473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245 위의 completepatch SHA910aac06723fac851e46eb6522146d896a433a04b3a8464d46e5c4c72ff8fc78이며build-j1을통과했다. [빌드receipt](../../code/orbit-cubic-up/build-receipt.json)는완료된main binary·모든library·실제소스identity를보존한다.

두manifest는실제명령·launchcommit/dirtyflag·runner/source/patch/runtime/input/outputSHA와240초cap을기록했다. source와runtime는두실행중수정하거나재빌드하지않았고before/afterbinary-libraryidentity도일치했다. postprocessing helper의SHA는summary에별도로기록했다. **유효원본1개+성능제외timeout1개이며 독립재현·확대정책성능평가는 아니다.**

압축은완료10M와제외100M를분리했다. [유효원본inventory](assets/20261012-orbit-cubic-up/raw-valid10-inventory.json)는13,418,032B·SHA34c840e67092bab00ce71f8889e95bbbe1bed5b8a2e17f8bc18b6fd9dd589400,25개파일을보존한다. [제외시도inventory](assets/20261012-orbit-cubic-up/raw-excluded100-inventory.json)는83,955,929B·SHA0b5cfdff1a6dfbdc7bb8cc4df63c7a1b904fae791c3579d316c90a03e4e1ebf6,21개파일을보존한다. 모든압축해제member의size/SHA를검증했고생성state·ns-3 source/build/runtime는포함하지않았다. [도구와명령](../../code/orbit-cubic-up/README.md), [exportreceipt](assets/20261012-orbit-cubic-up/export-receipt.json)을함께확인한다.

이번빠른선별은현재10Mbps자연전환에서실제원인을확대정책에연결하지못했다는결론이다. 다른조건·다른CUBIC구현·정확한송신예측의유용성전체를반증하지않는다.100Mbps/q100/200초에대한판단은실행상한에따른미완료로유보한다.
