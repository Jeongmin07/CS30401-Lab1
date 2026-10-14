기존 1-MSS tail 보완이 놓치던 짧은 파일의 경계 조건과 75초 큐 문제를 구분해서, 현재 궤도 기반 선택적 대기에 RFC 4653의 Aggressive/Careful ELT 송신 규칙을 적용했다. **21-MSS 완료 시간은 개선했지만, 자연 LEO 200초 큐·드롭 개선은 얻지 못했다.** 기존 제출 정책을 교체하지 않는 별도 실험이다.

- 21 MSS: 기존 tail **350.597→257.224 ms**, Aggressive 약26.63% 개선. 마지막 원본 데이터의 한 RTT 송신 정체를 피했으며 실제 손실 재전송의 6.631518-ms 대기 비용은 유지된다.
- 20 MSS: Aggressive는 tail과 같다. 24 MSS: tail 대비0.115-ms 차이뿐이다. Careful은 세 크기 모두 느려졌다.
- 자연 LEO: tail/Aggressive/Careful 모두 **9.5465088 Mbps,486 드롭,507 재전송,40 복구**. T75 focus도 모두11 드롭/12 재전송/2 복구. 75초 직후 평균 송신 큐는87.232→88.525패킷으로 조금 높아졌다.
- T75 실제 wait/ELT action은0회. T26 정상 ACK 종료 공식은 오히려 cwnd162840→165600B로 올렸다. burst 억제나 큐 근본 해결의 증거로 쓰지 않는다.

**완전한 TCP-NCR 구현은 아니다:** 기존 짧은 orbit wait/K3/CUBIC/PRR를 유지하는 RFC-inspired fixed-flight 적용이다. 첫 SACK부터 시작하는 RFC와 달리 첫 loss deferral 시점의 F0를 저장하여 앞선 대체 송신을 포함할 수 있다. 미세 실험 첫 ACK의 newSACK1 MSS에서 Aggressive3 MSS 송신이 관측되므로 단순한 fresh-SACK1:1 credit으로 설명하지 않는다. RFC adaptive threshold/RTT wait/T4 restart/half-flight recovery는 구현하지 않았다.

검증: 사전 고정한19개 실제 실행이 모두 성공했고 소스·런타임·입력 불변 및 실제 원본TX/E2/Skipped/deadline/관측CACK 검사를 통과했다. 기존7개 대조군 측정CSV75개가 바이트 단위로 일치했다. 첫 타입 오류 빌드와 컨테이너 Git 경로 launch 실패는 모두 시뮬레이션 전 실패로 보존했다.

실행 checkpoint `44f0850c2eb0fe3127993601822a55f502dfbd05`; patchSHA `8f822979eb9556c1f27f5128a462d66f085b1554ab3366c9af2c4036df8d7997`. `origin/main` b60e8e0에서 시작하며 [PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16)의0a42d0e frozen dependency를 명시적으로 복사했다. 이전 PR/보고서/제출ZIP을 변경하지 않았다. 다른 조원의 AI는 아래 결과 및 범위 설명을 검토하면 된다.

- [결과와 해석](https://github.com/Jeongmin07/CS30401-Lab1/blob/experiment/elt-ack-clock/code/orbit-elt/RESULTS.md)
- [전체 비교표](https://github.com/Jeongmin07/CS30401-Lab1/blob/experiment/elt-ack-clock/code/orbit-elt/results/summary.csv)
- [구현 범위와 RFC 차이](https://github.com/Jeongmin07/CS30401-Lab1/blob/experiment/elt-ack-clock/code/orbit-elt/SOURCE_NOTE.md)
- [재현 방법](https://github.com/Jeongmin07/CS30401-Lab1/blob/experiment/elt-ack-clock/code/orbit-elt/README.md)
- [원본 로그·상세 분석·패치](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-elt-screen-20261014):65MB archive 업로드 digest 검증 완료.

Aggressive는 유한 흐름 경계 문제의 후속 후보로 유지하고 Careful은 이번 조건에서 채택하지 않는다. 제출 기본 코드 변경, 병합 및 넓은 sweep은 하지 않았다.
