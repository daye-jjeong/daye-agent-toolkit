import Testing

@testable import BackgroundAutomatorRuntime

@Test
func timingJitterKeepsAverageAtBaseValue() {
    // 목표는 '느려지는 것'이 아니라 '흩어지는 것'이다. 기준값을 중심으로
    // 위아래 대칭이라 평균은 그대로 유지된다.
    let low = TimingJitter(spread: 0.3, randomness: { $0.lowerBound })
    let high = TimingJitter(spread: 0.3, randomness: { $0.upperBound })
    #expect(low.applied(to: .milliseconds(500)) == .milliseconds(350))
    #expect(high.applied(to: .milliseconds(500)) == .milliseconds(650))
}

@Test
func timingJitterStaysWithinSpreadOverManyDraws() {
    let jitter = TimingJitter(spread: 0.25)
    let base = Duration.milliseconds(100)
    var sawDistinctValues = Set<Duration>()
    for _ in 0 ..< 200 {
        let value = jitter.applied(to: base)
        #expect(value >= .milliseconds(75))
        #expect(value <= .milliseconds(125))
        sawDistinctValues.insert(value)
    }
    // 실제로 흩어지는지 — 상수를 반환하면 변주가 아니다.
    #expect(sawDistinctValues.count > 10)
}

@Test
func timingJitterLeavesNonPositiveAndZeroSpreadAlone() {
    let none = TimingJitter(spread: 0)
    #expect(none.applied(to: .milliseconds(500)) == .milliseconds(500))

    let jitter = TimingJitter(spread: 0.25)
    #expect(jitter.applied(to: .zero) == .zero)
    #expect(jitter.applied(to: .milliseconds(-10)) == .milliseconds(-10))
}
