import BackgroundAutomatorCore
import Foundation

public enum AutomationMenuStatus: Equatable, Sendable {
    case stopped
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
