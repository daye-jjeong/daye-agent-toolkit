import BackgroundAutomatorCore
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func bundledWorkflowContainsOnlyApprovedCanonicalRules() throws {
    // 기본은 은동전을 쓰지 않는다 — 임무를 해제하고 들어간다.
    let rules = try RuleLoader().loadDefaultRules()

    #expect(
        Set(rules.map(\.id)) == [
            "scene_skip",
            "clear_touch",
            "reward_detail",
            "reward_retry",
            "continue_dialog",
            "turn_off_double_loot",
            "deselect_challenge",
            "deselect_double_loot",
            "enter_ready",
            "running",
        ]
    )
}

@Test
func silverCoinChoiceSwapsExactlyOneRule() throws {
    // 두 규칙은 같은 화면(임무 선택, 은동전 충분)에 반응하므로 하나만
    // 남긴다. 둘 다 두면 후보가 겹쳐 자동화가 모호성으로 멈춘다.
    let off = try RuleLoader().loadDefaultRules(usesSilverCoin: false)
    let on = try RuleLoader().loadDefaultRules(usesSilverCoin: true)

    #expect(off.contains { $0.id == "deselect_double_loot" })
    #expect(!off.contains { $0.id == "enter_with_coin" })
    #expect(on.contains { $0.id == "enter_with_coin" })
    #expect(!on.contains { $0.id == "deselect_double_loot" })
    #expect(off.count == on.count)
}

/// 은동전을 쓰는 enter_with_coin은 코인 off 모드에서 로드조차 되지 않아
/// 이 가드레일 밖에 있었다 — 파일에서 가장 낮은 문턱(0.25)에 유일한 끝말
/// 일치인데도 어떤 테스트도 안 봤다. 두 모드를 모두 검사한다.
@Test(arguments: [false, true])
func everyWorkflowRuleHasBothLayoutsAndSceneSkipGuard(
    usesSilverCoin: Bool
) throws {
    let rules = try RuleLoader()
        .loadDefaultRules(usesSilverCoin: usesSilverCoin)

    // 실측(2026-07-24): '계속하기'·'입장하기'·'선택됨'은 신뢰도 0.50
    // 장식 폰트라 기준을 낮춘다. 각 규칙은 신뢰도 1.0 고유 시그니처를
    // 함께 요구하거나(continue_dialog·deselect_challenge) exact-match와
    // forbidden으로 오탐을 막는다(enter_ready).
    // clear_touch도 2026-07-26에 0.85에서 내렸다 — 아래 전용 테스트 참조.
    let lowConfidenceRules: Set<String> = [
        "continue_dialog", "deselect_challenge", "deselect_double_loot",
        "enter_ready", "scene_skip", "reward_detail", "clear_touch",
        "reward_retry", "turn_off_double_loot",
    ]
    // enter_with_coin만 더 낮다 — 실측 ') 입장하기' cf 0.30.
    // 정확한 하한은 silverCoinEntryKeepsItsMeasuredSafetyBounds가 못박는다.
    let lowestConfidenceRules: Set<String> = ["enter_with_coin"]

    for rule in rules {
        #expect(rule.regions[.landscape] != nil)
        #expect(rule.regions[.portraitMobile] != nil)
        // scene_skip은 장면 넘기기를 시그니처로 요구하는 유일한 예외라
        // forbidden에 두지 않는다. 그 외 규칙은 컷신 중 반드시 얼어야 한다.
        if rule.id != AutomationScene.sceneSkipRuleID {
            #expect(
                rule.forbiddenTexts.contains {
                    normalizedWorkflowText($0) == "장면넘기기"
                }
            )
        }
        #expect(rule.stableObservationCount >= 2)
        if lowestConfidenceRules.contains(rule.id) {
            #expect(rule.minimumOCRConfidence >= 0.2)
        } else if lowConfidenceRules.contains(rule.id) {
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
    // 회귀(2026-07-26): 기준이 0.85라 전체 규칙 중 가장 높았고, 같은
    // 화면에서 신뢰도가 흔들리면 이 규칙만 골라서 안 잡혔다. 실측으로
    // 정적 UI 글자도 몇 분 사이 1.00 → 0.50 → 0.30으로 움직인다.
    // 시그니처가 9글자 고유 문장이라 exact-match 자체가 필터 역할을
    // 하므로 신뢰도 문턱은 다른 장면 규칙과 같은 0.45로 낮춘다.
    #expect(rule.minimumOCRConfidence <= 0.45)
    #expect(rule.minimumOCRConfidence >= 0.4)
}

@Test(arguments: [
    ("reward_retry", "다시 하기", 0.5),
    ("continue_dialog", "계속하기", 0.5),
    // A방식: 입장 후 억제를 2초로 단축(실시간 결과 감지).
    ("enter_ready", "입장하기", 2.0),
    ("reward_detail", "발견한 전리품", 0.5),
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
func rewardDetailClicksLootHeaderWithLowConfidenceExactMatch() throws {
    let rule = try workflowRule("reward_detail")

    // 실측(2026-07-25, loot3.png 1512×949): '발견한 전리품'은 cf 0.50
    // 장식 폰트로 화면 중앙(정규화 x0.50·y0.40)에 뜬다. 은동전 쓴 런은
    // 결과가 접혀 있어 눌러야 펼쳐지고, 안 쓴 런은 눌러도 무변화(무해)다.
    // 빈 공간이 아닌 글자 자체를 눌러 재도전 메뉴로 넘어간다. cf 0.50이라
    // exact-match + '장면 넘기기' forbidden으로 오탐을 막는다.
    #expect(rule.requiredTexts == ["발견한 전리품"])
    #expect(rule.action.targetText == "발견한 전리품")
    #expect(rule.action.safePointRegion == nil)
    #expect(rule.minimumOCRConfidence >= 0.4)
    #expect(rule.minimumOCRConfidence <= 0.5)
    #expect(rule.appearance == nil)
    // 규칙 id ↔ scene 매핑 누락(회귀 방지): 후보는 생겨도 adopt에서 막힘.
    #expect(
        AutomationCoordinator.scene(forRuleID: "reward_detail")
            == .rewardDetail
    )
    // 발견전리품 화면엔 던전명이 표시된다(정규화 y0.26, cf 0.50 —
    // 추출 신뢰도 향상은 loot-log 단계에서).
    #expect(AutomationCoordinator.sceneHasDungeonName(.rewardDetail))
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
func sceneSkipClicksEmptySafePointAndOmitsForbiddenGuard() throws {
    let rule = try workflowRule("scene_skip")

    // 실측(2026-07-24): 컷신 화면은 '장면 넘기기'(cf 0.5)만 뜨는 거의 빈
    // 화면. 이 시그니처로 컷신을 감지하고, 장면 넘기기 버튼은 안 누른 채
    // 비어있는 안전지대(우상단, 모든 메뉴화면에서 빔)를 눌러 컷신을 넘긴다.
    #expect(rule.requiredTexts == ["장면 넘기기"])
    #expect(rule.action.targetText == nil)
    let safe = try #require(rule.action.safePointRegion)
    // 장면 넘기기 버튼(우상단 x~0.92, y~0.08)과 겹치지 않는 빈 지대.
    #expect(safe.minY >= 0.12)
    #expect(safe.maxX <= 0.85)
    // scene_skip만 장면 넘기기를 forbidden으로 두지 않는다(자기 시그니처).
    #expect(
        !rule.forbiddenTexts.contains {
            normalizedWorkflowText($0) == "장면넘기기"
        }
    )
    #expect(rule.minimumOCRConfidence >= 0.4)
    #expect(rule.minimumOCRConfidence <= 0.5)
    #expect(
        AutomationCoordinator.scene(forRuleID: "scene_skip") == .sceneSkip
    )
}

@Test
func noRuleEverClicksTheChallengeButton() throws {
    // 제거(2026-07-26): '도전'을 노리던 mission_selection을 뺐다.
    // 실측 세 상태를 다 보니 이 버튼이 눌릴 수 있는 유일한 경우가
    // '임무만 선택된 화면의 더블 루팅 도전'이었다 — 누르면 은동전이
    // 10개 더 나가 한 판 20개가 된다. 더블 루팅은 아직 지원하지 않으므로
    // 이 규칙이 할 수 있는 일은 원치 않는 소모뿐이다.
    let rules = try RuleLoader().loadDefaultRules(usesSilverCoin: true)
        + RuleLoader().loadDefaultRules(usesSilverCoin: false)
    #expect(!rules.contains { $0.action.targetText == "도전" })
    #expect(!rules.contains { $0.id == "mission_selection" })
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


@Test
func silverCoinEntryKeepsItsMeasuredSafetyBounds() throws {
    let rule = try #require(
        try RuleLoader().loadDefaultRules(usesSilverCoin: true)
            .first { $0.id == "enter_with_coin" }
    )

    // 실측(2026-07-26, landscape-mission-select-10coin): 이 버튼은
    // ') 입장하기' cf 0.30으로 읽힌다 — OCR이 코인 아이콘을 글자로 흘려
    // 앞에 붙이고 신뢰도도 떨군다. 0.45로는 걸러져 코인런이 멈췄다.
    #expect(rule.minimumOCRConfidence <= 0.30)
    #expect(rule.minimumOCRConfidence >= 0.20)
    // 앞이 흔들려도 끝말로 잡되, 완전 일치가 아니므로 시그니처 문장 두 개로
    // 화면을 못박아 엉뚱한 '입장하기'를 누르지 않게 한다.
    #expect(rule.action.targetTextSuffix == "입장하기")
    #expect(rule.requiredTexts.count == 2)
    #expect(rule.requiredTexts.contains("선택됨"))
    #expect(
        rule.forbiddenTexts.contains {
            normalizedWorkflowText($0) == "장면넘기기"
        }
    )
    // 입장 직후 결과 화면을 실시간 감지하므로 억제는 2초.
    #expect(rule.cooldownSeconds >= 2)
}
