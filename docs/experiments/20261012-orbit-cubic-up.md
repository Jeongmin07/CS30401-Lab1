# CUBIC 경로 증가와 선제 윈도우 확대의 빠른 선별

2026-10-12, 실행 전 선언. 이번 채팅 안의 후보 선별이며 팀의 최종 주제나 조원 역할을 확정하지 않는다.

질문은 자연 경로 증가 때 CUBIC의 실제 윈도우 부족이 링크 유휴와 전달량 감소를 만드는지다. 이미 큰 cwnd나 전파 BDP 계산만으로 필요·불필요를 확정하지 않는다. 제공 state의 증가 전환은121.6초(+3.061ms,1.034980배)와187.4초(+7.231ms,1.079762배)다. RTT를 인위적으로 두 배 늘리거나 새 토폴로지를 만들지 않는다.

먼저 기존10Mbps/q100/200초 CUBIC 원본의 자료와 새100Mbps/q100/200초 단일100GB CUBIC 원본을 비교한다. 시작0초, 서울1584→런던1585, pacing off, 원래MSS1380·SACK·PRR·K3를 유지한다. 새 원본은 별도 공식 이미지·빈ns-3 volume, CPU2·4GiB, build-j1, 개별실행240초 wall cap을 사용한다. timeout은 성공 결과에 섞지 않는다. canonicalv6 관측 위에 passive socket-window와 장치 queue/service 관측만 합친 complete patch를 사용한다.

윈도우 관측은 기존SendPendingData의 AvailableWindow 계산 직후 값을 읽는다. 관측 때문에 BytesInFlight/AvailableWindow를 다시 호출하거나 ACK·cwnd·recovery·timer·routing을 변경하지 않는다. cwnd, 실제 계산된pipe, rwnd, available window, unsent buffer, congestion/socket state, 기존cwnd-limited flag를 보존한다. 전환focus는[26.1,26.6),[74.9,75.4),[121.1,124.1),[186.9,189.9)이며 이 구간은 각 callback을 기록한다. 다른 시간은100ms 표본이다.

장치별100ms queue enqueue/dequeue·served wait·pending·flush 시각과 실제PhyTxBegin/End 직렬화 busy interval을 기록한다. service busy는 전송에 점유된 장치 시간을 뜻하며 app goodput·종단간큐RTT와 다르다. 같은 물리적drop을 layer별로 합쳐 고유 손실이라고 부르지 않는다. 기존tagged TX/Rx/app/drop/retx/event 원본도 유지해 두 번째 후보인 경로 단축 선제drain 검토와 공유한다.

평가는 전체[0,200), 증가 전환의pre[T−0.5,T),post[T,T+0.5),legacy[T−0.5,T+2)와 단축26.2/75.0의 같은창을 미리 고정한다. 수신app의 고유순서전달 바이트를 goodput으로 사용하고, 흐름이100GB를 완료하지 않으면 FCT를 계산하지 않는다. 장치queue·service는 실제 forward 경로에 속하는 장치를 따로 확인하며 모든hop의 평균idle을 종단간병목으로 바꾸지 않는다.

확대 정책 gate는 app data가 남아 있고 rwnd·recovery가 아닌 cwnd 제한이 실제로 존재하며, 증가 후 forward 병목 유휴와 전달량 감소에 연결되는 근거다. gate가 없으면 선제 확대를 구현하지 않고 근거와 함께 중단한다. gate가 있을 때만 opt-in 작은증분·burst 방지·CA_OPEN 조건의 정책을 준비해 같은binary의 원본과 최대1ON 및 필요한micro1을 비교한다. 단순비율이100%이용률·overflow없음을 보장하지 않는다. CUBIC의epoch/Wmax/ssthresh 처리 여부와 실제작동을 별도로 명시한다.

첫simulation은 공유선행commit 이후 진행한다. source/runner/runtime/input/output hashes, 실제명령과시간을 보존하고, 기본OFF 관측의 기존원본measurement 동등성도 확인한다. 아직 새simulation 결과나 확대성과는 없다.
