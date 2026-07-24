import Foundation

public enum AutomationScene: String, CaseIterable, Equatable, Sendable {
    case clearTouch
    case sceneSkip
    case rewardRetry
    case continueDialog
    case missionSelection
    case deselectChallenge
    case enterReady
    case running

    /// 장면 넘기기 컷신을 빈 공간 탭으로 넘기는 규칙 id.
    /// 이 규칙만 '장면 넘기기' 차단(관찰·평가·전역 freeze)에서 예외다 —
    /// 컷신 화면에서 빈 공간을 눌러 넘기되, 장면 넘기기 버튼 자체는 안 누른다.
    public static let sceneSkipRuleID = "scene_skip"
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
