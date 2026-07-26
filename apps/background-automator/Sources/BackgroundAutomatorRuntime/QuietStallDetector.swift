/// 아무 버튼도 못 찾는 상태가 오래 가면 멈춤으로 본다.
///
/// 상태가 `.observing`인 채 굳어버리는 경우가 실제로 있었다(2026-07-26,
/// 던전 클리어 화면). 앱은 살아서 초당 화면을 읽지만 어떤 규칙에도 안
/// 맞아 조용히 대기만 하고, 메뉴바도 정상으로 보이며 status.json은 매
/// 프레임 덮어써져 그때 화면이 남지 않았다. 그 침묵을 감지해 소리를 낸다.
///
/// 임계값은 정상 파밍의 침묵보다 넉넉히 길어야 한다. 실측(132판) 입장하기
/// → 보스 컷신 구간은 중앙값 66초, p95 73초, 최대 77초 동안 아무 버튼도
/// 안 뜬다. 그 두 배인 150초를 기본값으로 둔다.
public struct QuietStallDetector: Sendable {
    public static let defaultThreshold: Duration = .seconds(150)

    public enum Transition: Equatable, Sendable {
        /// 보고할 변화 없음.
        case none
        /// 침묵이 방금 임계값을 넘었다. 이 순간에만 기록·알림을 낸다.
        case entered
        /// 멈춰 있다가 다시 동작했다.
        case recovered
    }

    private let threshold: Duration
    private var lastActivityAt: Duration?
    private var isStalled = false

    public init(threshold: Duration = Self.defaultThreshold) {
        self.threshold = threshold
    }

    /// 사이클 한 번의 결과를 넣는다. `didAct`는 이번 사이클에 실제로
    /// 클릭이 일어났는지다.
    public mutating func note(
        didAct: Bool,
        at now: Duration
    ) -> Transition {
        guard let since = lastActivityAt else {
            // 첫 관찰을 기준으로 잡는다. 앱을 켠 시각을 0으로 두면
            // 시작하자마자 멈춤으로 오판한다.
            lastActivityAt = now
            return .none
        }

        if didAct {
            lastActivityAt = now
            guard isStalled else {
                return .none
            }
            isStalled = false
            return .recovered
        }

        guard now - since >= threshold, !isStalled else {
            return .none
        }
        isStalled = true
        return .entered
    }

    /// 자동화를 켜고 끌 때 이전 세션의 침묵을 끌고 가지 않게 비운다.
    public mutating func reset() {
        lastActivityAt = nil
        isStalled = false
    }
}
