import BackgroundAutomatorCore
import Foundation

public enum AutomationMenuStatus: Equatable, Sendable {
    case stopped
    case checkingPreflight
    case needsAttention(String)
    case observing
    case combatWait
    case buttonDetected
    case waitingForUserIdle
    case clicking
    case cooldown
    case pausedRestorationFailure
    case stopping

    public var koreanDescription: String {
        switch self {
        case .stopped:
            "중지됨"
        case .checkingPreflight:
            "준비 상태 확인 중"
        case let .needsAttention(guidance):
            "확인 필요: \(guidance)"
        case .observing:
            "화면 확인 중"
        case .combatWait:
            "전투 완료 대기 중"
        case .buttonDetected:
            "버튼 감지됨"
        case .waitingForUserIdle:
            "사용자 입력 대기 중"
        case .clicking:
            "클릭 및 화면 복원 중"
        case .cooldown:
            "다음 확인 대기 중"
        case .pausedRestorationFailure:
            "복원 실패로 일시정지"
        case .stopping:
            "안전하게 중지 중"
        }
    }

    /// 메뉴막대에서 상태를 한눈에 알리는 SF Symbol 이름.
    public var symbolName: String {
        switch self {
        case .stopped:
            "pause.circle"
        case .checkingPreflight, .combatWait:
            "hourglass"
        case .needsAttention, .pausedRestorationFailure:
            "exclamationmark.triangle.fill"
        case .observing:
            "eye"
        case .buttonDetected:
            "cursorarrow.rays"
        case .waitingForUserIdle:
            "hand.raised"
        case .clicking:
            "cursorarrow.click.2"
        case .cooldown:
            "clock"
        case .stopping:
            "stop.circle"
        }
    }

    public static func projecting(
        _ state: AutomationState
    ) -> AutomationMenuStatus {
        switch state {
        case .stopped:
            .stopped
        case .observing(.running):
            .combatWait
        case .observing:
            .observing
        case .unknown:
            .observing
        case .attention:
            .needsAttention("화면을 안전하게 판별할 수 없습니다.")
        case .cooldown:
            .cooldown
        case .pausedRestorationFailure:
            .pausedRestorationFailure
        }
    }
}

public struct AutomationLifecycleGate: Sendable {
    public struct Token: Equatable, Sendable {
        fileprivate let generation: UInt64
    }

    public struct StartSession: Equatable, Sendable {
        public let token: Token
        public let target: TargetConfiguration

        fileprivate init(
            token: Token,
            target: TargetConfiguration
        ) {
            self.token = token
            self.target = target
        }
    }

    private var generation: UInt64 = 0

    public init() {}

    public mutating func begin() -> Token {
        generation &+= 1
        return Token(generation: generation)
    }

    public mutating func beginStart(
        target: TargetConfiguration
    ) -> StartSession {
        StartSession(token: begin(), target: target)
    }

    public mutating func invalidate() {
        generation &+= 1
    }

    public func isCurrent(_ token: Token) -> Bool {
        token.generation == generation
    }
}

public enum AutomationTargetFieldPolicy {
    public static func isLocked(
        status: AutomationMenuStatus
    ) -> Bool {
        switch status {
        case .stopped, .needsAttention:
            false
        case .checkingPreflight,
             .observing,
             .combatWait,
             .buttonDetected,
             .waitingForUserIdle,
             .clicking,
             .cooldown,
             .pausedRestorationFailure,
             .stopping:
            true
        }
    }
}

public enum AutomationPollingSchedule {
    public static func delay(
        for status: AutomationMenuStatus
    ) -> Duration {
        switch status {
        case .combatWait, .cooldown:
            .seconds(120)
        default:
            .milliseconds(500)
        }
    }
}
