import Foundation

public enum AutomationScene: String, CaseIterable, Equatable, Sendable {
    case clearTouch
    case rewardRetry
    case continueDialog
    case missionSelection
    case enterReady
    case running
}

public enum AutomationAttention: Equatable, Sendable {
    case forbiddenContent
    case ambiguousObservation
    case unsupportedLayout
    case sceneRuleMismatch
    case actionFailed
    case actionOutcomeUncertain
}

public enum AutomationState: Equatable, Sendable {
    case stopped
    case observing(AutomationScene)
    case unknown
    case attention(AutomationAttention)
    case cooldown(scene: AutomationScene, until: Duration)
    case pausedRestorationFailure
}
