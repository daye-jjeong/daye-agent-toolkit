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

    /// 사람이 손대야 풀리는, 진행이 막힌 상태인지.
    /// 전투 대기·쿨다운처럼 곧 스스로 풀리는 상태는 포함하지 않는다.
    /// 이 상태로 들어간 순간의 화면을 따로 보존해 정지 원인을 진단한다.
    public var isStalled: Bool {
        switch self {
        case .needsAttention, .pausedRestorationFailure:
            true
        case .stopped, .checkingPreflight, .observing, .combatWait,
             .buttonDetected, .waitingForUserIdle, .clicking, .cooldown,
             .stopping:
            false
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

/// 화면 확인 실패에 대한 자동 재시도 정책.
///
/// 포기하지 않는다. 맥이 잠들거나 게임이 재시작하면 접근성 조회가 몇 분에서
/// 몇 시간씩 실패하는데, 그 사이 손을 떼면 깨어나도 스스로 돌아오지 못한다.
/// 실측(2026-07-29): 5회(총 15초) 만에 포기한 뒤 3시간을 멈춘 채 있었고,
/// 그때 접근성은 이미 정상으로 돌아와 있었다. 실패하는 동안은 아무 일도
/// 하지 않으므로 오래 기다려도 비용이 없다.
public struct AutomationRetryPolicy: Sendable {
    /// 간격이 이만큼 벌어지면 더 늘리지 않는다. 긴 중단에도 조용하고,
    /// 회복은 늦어도 이 시간 안에 알아챈다.
    public static let maximumBackoff = Duration.seconds(60)

    public init() {}

    /// 재시도 전 대기: 1s → 2s → 3s … 최대 60s로 늘어나는 선형 백오프.
    /// 짧은 끊김은 촘촘히 따라붙고, 긴 중단에는 간격이 벌어진다.
    public func backoff(consecutiveFailures: Int) -> Duration {
        .seconds(min(60, max(1, consecutiveFailures)))
    }
}

public enum AutomationPollingSchedule {
    public static func delay(
        for status: AutomationMenuStatus
    ) -> Duration {
        switch status {
        case .observing, .buttonDetected:
            // 액션 구간(버튼 탐지·안정화)의 간격이 곧 반응 시간이다.
            // 안정화에 관찰을 두 번 하므로 간격 하나가 두 번 곱해진다.
            // 인식 자체가 265ms 걸려 100ms면 사실상 쉬지 않고 이어 본다.
            // OCR은 Neural Engine 가속이라 CPU 부담이 거의 없다.
            .milliseconds(100)
        case .cooldown:
            // 클릭 직후 다음 확인까지의 대기. 500ms로 다음 액션을 앞당긴다.
            .milliseconds(500)
        case .combatWait:
            // 전투 대기는 ~90초 게임 시간이라 1초 유지(폴링 낭비 방지).
            .seconds(1)
        default:
            .milliseconds(500)
        }
    }
}
