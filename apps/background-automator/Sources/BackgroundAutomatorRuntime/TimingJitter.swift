import Foundation

/// 고정된 대기 시간을 기준값 둘레로 흩뿌린다.
///
/// 클릭 위치는 이미 임의로 고르지만(`RandomTargetPointSelector`) 박자는
/// 정확히 일정했다 — 클릭 후 대기 0.500초, 폴링 0.100초가 매번 같은 값.
/// 위치보다 이 규칙적인 간격이 더 티가 난다. 평균은 기준값 그대로 두고
/// 분산만 만들어, 흩뿌리는 대가로 느려지지 않게 한다.
public struct TimingJitter: Sendable {
    /// 실측 클릭 간격이 2~4초라 ±25%면 사람이 낼 법한 폭이면서
    /// 규칙의 쿨다운(1초 이상)을 침범하지 않는다.
    public static let defaultSpread = 0.25

    private let spread: Double
    private let randomness: @Sendable (ClosedRange<Double>) -> Double

    public init(spread: Double = Self.defaultSpread) {
        self.init(spread: spread, randomness: { Double.random(in: $0) })
    }

    init(
        spread: Double,
        randomness: @escaping @Sendable (ClosedRange<Double>) -> Double
    ) {
        self.spread = spread
        self.randomness = randomness
    }

    public func applied(to base: Duration) -> Duration {
        guard spread > 0, base > .zero else {
            return base
        }
        let factor = randomness((1 - spread) ... (1 + spread))
        return .microseconds(
            Int64((Double(base.microseconds) * factor).rounded())
        )
    }
}

extension Duration {
    var microseconds: Int64 {
        let (seconds, attoseconds) = components
        return seconds * 1_000_000 + attoseconds / 1_000_000_000_000
    }
}
