import BackgroundAutomatorCore
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func bundledWorkflowContainsOnlyApprovedCanonicalRules() throws {
    let rules = try RuleLoader().loadDefaultRules()

    #expect(
        Set(rules.map(\.id)) == [
            "clear_touch",
            "reward_retry",
            "continue_dialog",
            "mission_selection",
            "enter_ready",
            "running",
        ]
    )
    #expect(!rules.contains { $0.id == "scene_skip" })
}

@Test
func everyWorkflowRuleHasBothLayoutsAndSceneSkipGuard() throws {
    let rules = try RuleLoader().loadDefaultRules()

    for rule in rules {
        #expect(rule.regions[.landscape] != nil)
        #expect(rule.regions[.portraitMobile] != nil)
        #expect(
            rule.forbiddenTexts.contains {
                normalizedWorkflowText($0) == "장면넘기기"
            }
        )
        #expect(rule.stableObservationCount >= 2)
        if rule.id == "continue_dialog" {
            // 실측: '계속하기' 버튼이 신뢰도 0.50 장식 폰트라 기준을
            // 낮춘다. 시그니처 '던전 탐험을 계속하시겠습니까?'(1.0)를
            // 이중 확인으로 함께 요구해 오탐을 막는다.
            #expect(rule.minimumOCRConfidence >= 0.4)
            #expect(
                rule.requiredTexts.contains(
                    "던전 탐험을 계속하시겠습니까?"
                )
            )
        } else {
            #expect(rule.minimumOCRConfidence >= 0.8)
        }
        #expect(rule.postActionDelaySeconds >= 0.5)
        #expect(rule.cooldownSeconds >= 0.5)
    }
}

@Test
func clearTouchRequiresExactContextAndUsesOnlySafePoint() throws {
    let rule = try workflowRule("clear_touch")

    // 실측(2026-07-24): '던전 클리어!'는 신뢰도 0.50 장식 폰트라
    // 신뢰 불가. 신뢰도 1.00의 '화면을 터치해 주세요' 단독을 시그니처로.
    #expect(Set(rule.requiredTexts) == ["화면을 터치해 주세요"])
    #expect(!rule.requiredTexts.contains("던전 클리어"))
    #expect(rule.action.targetText == nil)
    #expect(rule.action.safePointRegion != nil)
    #expect(rule.cooldownSeconds >= 2)
}

@Test(arguments: [
    ("reward_retry", "다시 하기", 0.5),
    ("continue_dialog", "계속하기", 0.5),
    ("mission_selection", "도전", 0.5),
    // A방식: 입장 후 억제를 5초로 단축(실시간 결과 감지).
    ("enter_ready", "입장하기", 5.0),
])
func textActionsUseExactOCRTargetBoundingBoxConfiguration(
    id: String,
    targetText: String,
    minimumCooldown: Double
) throws {
    let rule = try workflowRule(id)

    #expect(rule.requiredTexts.contains(targetText))
    #expect(rule.action.targetText == targetText)
    #expect(rule.action.safePointRegion == nil)
    #expect(rule.cooldownSeconds >= minimumCooldown)
}

@Test
func enterReadyRequiresGreyChallengeAndEnabledEntryAppearance() throws {
    let rule = try workflowRule("enter_ready")
    let appearance = try #require(rule.appearance)

    #expect(appearance.contextText == "도전")
    #expect(
        appearance.contextRange.maximumSaturation <= 0.25
    )
    #expect(
        appearance.targetRange.minimumSaturation >= 0.1
    )
    #expect(
        appearance.targetRange.minimumLuminance >= 0.2
    )
    #expect(appearance.contextRegions[.landscape] != nil)
    #expect(appearance.contextRegions[.portraitMobile] != nil)
}

@Test
func missionSelectionKeepsOCRTargetAndRequiresActiveAppearance() throws {
    let rule = try workflowRule("mission_selection")
    let appearance = try #require(rule.appearance)
    let enterAppearance = try #require(
        workflowRule("enter_ready").appearance
    )

    #expect(rule.action.targetText == "도전")
    #expect(appearance.contextText == "도전")
    #expect(
        appearance.contextRange.minimumSaturation
            > enterAppearance.contextRange.maximumSaturation
    )
}

@Test
func runningRuleIsExplicitlyNonActionableUntilLiveCalibration() throws {
    let rule = try workflowRule("running")

    #expect(!rule.requiredTexts.isEmpty)
    #expect(rule.action.targetText == nil)
    #expect(rule.action.safePointRegion == nil)
    #expect(
        SceneObserver.actionCandidate(
            for: rule,
            observations: [],
            layout: .portraitMobile,
            imageSize: .init(width: 626, height: 949)
        ) == nil
    )
}

private func workflowRule(_ id: String) throws -> AutomationRule {
    let rules = try RuleLoader().loadDefaultRules()
    return try #require(rules.first { $0.id == id })
}

private func normalizedWorkflowText(_ text: String) -> String {
    text.filter { !$0.isWhitespace }
}
