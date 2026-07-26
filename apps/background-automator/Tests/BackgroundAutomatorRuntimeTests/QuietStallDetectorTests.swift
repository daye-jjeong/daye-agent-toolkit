import Testing

@testable import BackgroundAutomatorRuntime

@Test
func quietDetectorIgnoresNormalCombatSilence() {
    // 실측(132판): 입장하기 → 보스 컷신 사이는 아무 버튼도 안 뜬다.
    // 중앙값 66초, p95 73초, 최대 77초. 이 구간을 멈춤으로 오판하면
    // 매 판 거짓 경보가 뜬다.
    var detector = QuietStallDetector()
    #expect(detector.note(didAct: true, at: .seconds(0)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(77)) == .none)
    #expect(detector.note(didAct: true, at: .seconds(78)) == .none)
}

@Test
func quietDetectorEntersStallOnceAfterThreshold() {
    var detector = QuietStallDetector(threshold: .seconds(150))
    #expect(detector.note(didAct: true, at: .seconds(0)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(149)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(150)) == .entered)
    // 같은 멈춤에서 폴링마다 반복 보고하지 않는다.
    #expect(detector.note(didAct: false, at: .seconds(200)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(600)) == .none)
}

@Test
func quietDetectorRecoversAndCanStallAgain() {
    var detector = QuietStallDetector(threshold: .seconds(150))
    _ = detector.note(didAct: true, at: .seconds(0))
    #expect(detector.note(didAct: false, at: .seconds(160)) == .entered)
    #expect(detector.note(didAct: true, at: .seconds(170)) == .recovered)
    #expect(detector.note(didAct: false, at: .seconds(200)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(321)) == .entered)
}

@Test
func quietDetectorStartsCountingFromFirstObservation() {
    // 앱을 켠 직후 기준 시각이 없으면 0부터 세어 즉시 멈춤으로 본다.
    // 첫 관찰을 기준으로 잡아 그 오판을 막는다.
    var detector = QuietStallDetector(threshold: .seconds(150))
    #expect(detector.note(didAct: false, at: .seconds(1000)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(1149)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(1150)) == .entered)
}

@Test
func quietDetectorResetClearsStallState() {
    // 시작/정지 시 이전 세션의 멈춤 상태를 끌고 가지 않는다.
    var detector = QuietStallDetector(threshold: .seconds(150))
    _ = detector.note(didAct: true, at: .seconds(0))
    #expect(detector.note(didAct: false, at: .seconds(200)) == .entered)
    detector.reset()
    #expect(detector.note(didAct: false, at: .seconds(300)) == .none)
    #expect(detector.note(didAct: false, at: .seconds(450)) == .entered)
}
