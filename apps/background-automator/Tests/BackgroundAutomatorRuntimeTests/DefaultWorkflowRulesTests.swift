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
            "deselect_challenge",
            "enter_ready",
            "running",
        ]
    )
    #expect(!rules.contains { $0.id == "scene_skip" })
}

@Test
func everyWorkflowRuleHasBothLayoutsAndSceneSkipGuard() throws {
    let rules = try RuleLoader().loadDefaultRules()

    // 실측(2026-07-24): '계속하기'·'입장하기'·'선택됨'은 신뢰도 0.50
    // 장식 폰트라 기준을 낮춘다. 각 규칙은 신뢰도 1.0 고유 시그니처를
    // 함께 요구하거나(continue_dialog·deselect_challenge) exact-match와
    // forbidden으로 오탐을 막는다(enter_ready).
    let lowConfidenceRules: Set<String> = [
        "continue_dialog", "deselect_challenge", "enter_ready",
    ]

    for rule in rules {
        #expect(rule.regions[.landscape] != nil)
        #expect(rule.regions[.portraitMobile] != nil)
        #expect(
            rule.forbiddenTexts.contains {
                normalizedWorkflowText($0) == "장면넘기기"
            }
        )
        #expect(rule.stableObservationCount >= 2)
        if lowConfidenceRules.contains(rule.id) {
            #expect(rule.minimumOCRConfidence >= 0.4)
        } else {
            #expect(rule.minimumOCRConfidence >= 0.8)
        }
        if rule.id == "continue_dialog" {
            #expect(
                rule.requiredTexts.contains(
                    "던전 탐험을 계속하시겠습니까?"
                )
            )
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
    #expect(rule.cooldownSeconds >= 1)
}

@Test(arguments: [
    ("reward_retry", "다시 하기", 0.5),
    ("continue_dialog", "계속하기", 0.5),
    ("mission_selection", "도전", 0.5),
    // A방식: 입장 후 억제를 2초로 단축(실시간 결과 감지).
    ("enter_ready", "입장하기", 2.0),
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
func enterReadyBlocksSelectedStateAndUsesLowConfidenceExactMatch() throws {
    let rule = try workflowRule("enter_ready")

    // 실측(2026-07-24): 해제 상태의 '입장하기'(cf 0.50)만 클릭한다.
    // 선택됨 상태 버튼은 '10 입장하기'라 exact-match가 성립하지 않고,
    // 안내문을 forbidden으로 둬 이중 차단한다. 색상 기반 appearance는
    // OCR 인식으로 대체돼 제거됐다.
    #expect(rule.minimumOCRConfidence >= 0.4)
    #expect(rule.minimumOCRConfidence <= 0.5)
    #expect(rule.action.targetText == "입장하기")
    #expect(rule.action.safePointRegion == nil)
    #expect(rule.appearance == nil)
    #expect(
        rule.forbiddenTexts.contains(
            "선택을 해제하면 임무 없이 입장할 수 있습니다."
        )
    )
}

@Test
func deselectChallengeUsesInfoSignatureAndClicksSelectedBadge() throws {
    let rule = try workflowRule("deselect_challenge")

    // 실측(2026-07-24): 선택됨 상태에만 뜨는 안내문(cf 1.0)을
    // 시그니처로, 좌측 '선택됨' 뱃지(cf 0.50)를 눌러 임무 선택을
    // 해제한다. 해제되면 안내문이 사라져 규칙이 자연히 멈춘다.
    #expect(
        rule.requiredTexts.contains(
            "선택을 해제하면 임무 없이 입장할 수 있습니다."
        )
    )
    #expect(rule.action.targetText == "선택됨")
    #expect(rule.action.safePointRegion == nil)
    #expect(rule.minimumOCRConfidence >= 0.4)
    #expect(rule.minimumOCRConfidence <= 0.5)
    #expect(rule.appearance == nil)
}

@Test
func missionSelectionKeepsOCRTargetAndHighConfidence() throws {
    let rule = try workflowRule("mission_selection")

    // 실측(2026-07-24): 해제 상태의 '도전'(cf 0.50)을 다시 눌러
    // 선택하면 '선택↔해제' 무한 토글이 된다. 높은 신뢰도 기준을
    // 유지해 저신뢰 '도전'을 트리거하지 않는다.
    #expect(rule.action.targetText == "도전")
    #expect(rule.minimumOCRConfidence >= 0.8)
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

@Test
func everyActionableRuleMapsToAutomationScene() throws {
    // 회귀(2026-07-24): deselect_challenge를 JSON에만 추가하고
    // AutomationScene enum·expectedRuleID 매핑을 빠뜨려, 후보는
    // 생성되나 adopt 단계에서 막혀 클릭이 안 됐다. 규칙 id ↔ scene
    // 매핑을 전수 검증해 매핑 누락을 컴파일이 아닌 테스트로 잡는다.
    let rules = try RuleLoader().loadDefaultRules()
    for rule in rules where rule.id != "running" {
        #expect(
            AutomationCoordinator.scene(forRuleID: rule.id) != nil,
            "규칙 \(rule.id)에 대응하는 AutomationScene 매핑이 없음"
        )
    }
    #expect(
        AutomationCoordinator.scene(forRuleID: "deselect_challenge")
            == .deselectChallenge
    )
}

private func workflowRule(_ id: String) throws -> AutomationRule {
    let rules = try RuleLoader().loadDefaultRules()
    return try #require(rules.first { $0.id == id })
}

private func normalizedWorkflowText(_ text: String) -> String {
    text.filter { !$0.isWhitespace }
}
