import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func retryTextInsidePortraitRegionReturnsCurrentOCRTarget() async throws {
    let targetRect = CGRect(x: 60, y: 240, width: 80, height: 30)
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", confidence: 0.95, rect: targetRect),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.ruleID == "reward_retry")
    #expect(candidate.targetText == "다시 하기")
    #expect(candidate.boundingBox == targetRect)
    #expect(candidate.confidence == 0.95)
}

@Test
func missingRequiredTextYieldsNoSceneCandidate() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("확인", rect: CGRect(x: 60, y: 240, width: 80, height: 30)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func observedForbiddenTextBlocksRetryCandidate() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", rect: CGRect(x: 60, y: 240, width: 80, height: 30)),
            recognized("장면 넘기기", rect: CGRect(x: 40, y: 20, width: 120, height: 30)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func rewardDetailFiresAloneOnLootScreenClickingHeaderGlyph() async throws {
    // 실측(loot3.png 1512×949): 은동전 쓴 런의 발견전리품 화면. '발견한
    // 전리품'(cf 0.50) 헤더 외에 다른 룰 시그니처(다시 하기·입장하기·도전·
    // 계속하기·장면 넘기기·화면을 터치)가 없다 → reward_detail만 발동해
    // 후보가 1개다(2개면 모호성으로 앱이 얼어붙어 정지한다). 빈 공간이
    // 아니라 헤더 글자 박스를 눌러 재도전 메뉴(나가기/다시하기/다음구역)로
    // 넘어간다.
    let lootHeader = CGRect(x: 694, y: 369, width: 123, height: 27)
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "룬다 1층 2구역",
                confidence: 0.5,
                rect: CGRect(x: 683, y: 251, width: 154, height: 32)
            ),
            recognized(
                "C 순수 전투 시간 0:13",
                confidence: 1.0,
                rect: CGRect(x: 683, y: 295, width: 142, height: 17)
            ),
            recognized("발견한 전리품", confidence: 0.5, rect: lootHeader),
            recognized(
                "골드",
                confidence: 0.5,
                rect: CGRect(x: 551, y: 541, width: 32, height: 20)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try blankImage(width: 1512, height: 949),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "reward_detail")
    #expect(candidate.targetText == "발견한 전리품")
    #expect(candidate.boundingBox == lootHeader)
}

@Test
func rewardDetailFiresFromRealOCROnLootScreenshot() async throws {
    // 골든 테스트: 손먹인 OCR 값이 아니라 실제 캡처(landscape-reward-detail
    // = 은동전런 발견전리품 화면)를 진짜 Vision OCR에 돌려 파이프라인 전체를
    // 검증한다. 손먹인 테스트가 못 잡는 실화면 OCR 변화(') 입장하기' 류)를
    // 여기서 잡는다. Vision은 OS버전 따라 미세 변동 → 박스 정확값 대신
    // 발동·단독·중심 근사(±0.08)로 검증한다.
    let observer = SceneObserver() // 실제 VisionTextRecognizer + 픽셀 분석기
    let image = try fixtureImage(named: "landscape-reward-detail")

    let result = try await observer.observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(
        result.actionCandidates.first { $0.ruleID == "reward_detail" }
    )
    #expect(candidate.targetText == "발견한 전리품")
    let centerX = candidate.boundingBox.midX / 1512.0
    let centerY = candidate.boundingBox.midY / 949.0
    #expect(abs(centerX - 0.50) < 0.08)
    #expect(abs(centerY - 0.40) < 0.08)
}

@Test
func noCoinResultScreenPrefersRetryOverLootHeader() async throws {
    // 골든 테스트(landscape-reward-detail-nocoin = 은동전 안 쓴 런의 결과
    // 화면). 실측: 이 화면엔 '발견한 전리품'(cf 0.50)과 '다시 하기'(cf 1.0)가
    // 함께 뜬다 — 코인런(landscape-reward-detail)엔 재도전 메뉴가 없어
    // 안 겹쳤던 조합이다. 둘 다 후보가 되면 모호성으로 자동화가 얼어붙어
    // 정지하므로, 재도전 메뉴가 이미 떴으면 전리품 헤더는 누르지 않고
    // 곧장 '다시 하기'로 간다(목적지가 같다).
    let observer = SceneObserver()
    let image = try fixtureImage(named: "landscape-reward-detail-nocoin")

    let result = try await observer.observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == "reward_retry")
    #expect(
        !result.actionCandidates.contains { $0.ruleID == "reward_detail" }
    )
}

@Test
func lowConfidenceSceneSkipStillBlocksHighConfidenceAction() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                confidence: 0.95,
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
            recognized(
                "장면 넘기기",
                confidence: 0.79,
                rect: CGRect(x: 40, y: 20, width: 120, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func lowConfidenceRuleSpecificForbiddenTextBlocksAction() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                confidence: 0.95,
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
            recognized(
                "취소",
                confidence: 0.79,
                rect: CGRect(x: 40, y: 20, width: 80, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [
            makeRule(forbiddenTexts: ["취소"]),
        ]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func lowConfidenceForbiddenSubstringDoesNotBlockExactMatching() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                confidence: 0.95,
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
            recognized(
                "장면 넘기기 안내",
                confidence: 0.79,
                rect: CGRect(x: 30, y: 20, width: 140, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.count == 1)
}

@Test
func sceneSkipCanNeverBecomeAnActionCandidate() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("장면 넘기기", rect: CGRect(x: 40, y: 240, width: 120, height: 30)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [
            makeRule(
                id: "unsafe_scene_skip",
                requiredTexts: ["장면 넘기기"],
                forbiddenTexts: [],
                targetText: "장면 넘기기"
            ),
        ]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func sceneSkipObservationBlocksRulesThatOmitTheForbiddenText() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("확인", rect: CGRect(x: 60, y: 240, width: 80, height: 30)),
            recognized("장면 넘기기", rect: CGRect(x: 40, y: 20, width: 120, height: 30)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [
            makeRule(
                id: "unsafe_omitted_forbidden_text",
                requiredTexts: ["확인"],
                forbiddenTexts: [],
                targetText: "확인"
            ),
        ]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func sceneSkipRuleClicksSafePointDespiteSceneSkipButton() async throws {
    // 컷신 화면: '장면 넘기기'만 뜬다. 전역 차단 대상이지만 scene_skip은
    // 이 화면의 지정 핸들러라 후보를 만든다(빈 공간 탭 = targetText nil).
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "장면 넘기기",
                confidence: 0.5,
                rect: CGRect(x: 40, y: 20, width: 120, height: 30)
            ),
        ])
    )
    let rule = AutomationRule(
        id: "scene_skip",
        requiredTexts: ["장면 넘기기"],
        forbiddenTexts: [],
        action: AutomationAction(
            targetText: nil,
            safePointRegion: NormalizedRegion(
                minX: 0.68,
                minY: 0.2,
                maxX: 0.78,
                maxY: 0.28
            )
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 0.5
            ),
        ]),
        minimumOCRConfidence: 0.4,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 1
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [rule]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "scene_skip")
    #expect(candidate.targetText == nil)
}

@Test
func duplicateTargetsInsideSearchRegionAreRejectedAsAmbiguous() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", rect: CGRect(x: 30, y: 230, width: 60, height: 25)),
            recognized("다시 하기", rect: CGRect(x: 110, y: 250, width: 60, height: 25)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func enterReadyRequiresGreySelectionAndEnabledTargetAppearance() async throws {
    let contextRect = CGRect(x: 50, y: 190, width: 70, height: 24)
    let targetRect = CGRect(x: 55, y: 240, width: 90, height: 28)
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("도전", rect: contextRect),
            recognized("입장하기", rect: targetRect),
        ]),
        appearanceAnalyzer: FakeAppearanceAnalyzer([
            (contextRect, .init(
                medianSaturation: 0.08,
                medianLuminance: 0.55,
                sampleCount: 100
            )),
            (targetRect, .init(
                medianSaturation: 0.45,
                medianLuminance: 0.55,
                sampleCount: 100
            )),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [enterReadyAppearanceRule()]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "enter_ready")
    #expect(candidate.boundingBox == targetRect)
}

@Test
func enterReadyRejectsColoredUnselectedChallenge() async throws {
    let fixture = appearanceObserver(
        context: .init(
            medianSaturation: 0.6,
            medianLuminance: 0.55,
            sampleCount: 100
        ),
        target: enabledTargetAppearance
    )

    let result = try await fixture.observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [enterReadyAppearanceRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func enterReadyRejectsGreySelectionWhenEntryButtonIsDim() async throws {
    let fixture = appearanceObserver(
        context: selectedGreyAppearance,
        target: .init(
            medianSaturation: 0.45,
            medianLuminance: 0.1,
            sampleCount: 100
        )
    )

    let result = try await fixture.observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [enterReadyAppearanceRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func enterReadyRejectsAmbiguousDuplicateChallengeContext() async throws {
    let contextRect = appearanceContextRect
    let targetRect = appearanceTargetRect
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("도전", rect: contextRect),
            recognized(
                "도전",
                rect: contextRect.offsetBy(dx: 40, dy: 0)
            ),
            recognized("입장하기", rect: targetRect),
        ]),
        appearanceAnalyzer: FakeAppearanceAnalyzer([
            (contextRect, selectedGreyAppearance),
            (targetRect, enabledTargetAppearance),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [enterReadyAppearanceRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test(arguments: [
    LayoutProfile.portraitMobile,
    .landscape,
])
func enterReadyAppearanceUsesLayoutSpecificNormalizedContextRegion(
    layout: LayoutProfile
) async throws {
    let fixture = appearanceObserver(
        context: selectedGreyAppearance,
        target: enabledTargetAppearance
    )
    let image = layout == .portraitMobile
        ? try fixtureImage(named: "portrait-reward")
        : try fixtureImage(named: "landscape-clear-touch")

    let result = try await fixture.observer.observe(
        image: image,
        layout: layout,
        rules: [enterReadyAppearanceRule()]
    )

    #expect(result.actionCandidates.count == 1)
}

@Test
func enterReadyFailsClosedWhenAppearancePixelsAreUnavailable() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("도전", rect: appearanceContextRect),
            recognized("입장하기", rect: appearanceTargetRect),
        ]),
        appearanceAnalyzer: FakeAppearanceAnalyzer([])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [enterReadyAppearanceRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func appearanceSeparatesActiveMissionFromGreyEnterReady() async throws {
    let activeObserver = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("도전", rect: appearanceContextRect),
            recognized("입장하기", rect: appearanceTargetRect),
        ]),
        appearanceAnalyzer: FakeAppearanceAnalyzer([
            (appearanceContextRect, .init(
                medianSaturation: 0.5,
                medianLuminance: 0.55,
                sampleCount: 100
            )),
            (appearanceTargetRect, .init(
                medianSaturation: 0.05,
                medianLuminance: 0.1,
                sampleCount: 100
            )),
        ])
    )
    let selectedObserver = appearanceObserver(
        context: selectedGreyAppearance,
        target: enabledTargetAppearance
    ).observer
    let rules = [
        missionSelectionAppearanceRule(),
        enterReadyAppearanceRule(),
    ]
    let image = try fixtureImage(named: "portrait-reward")

    let active = try await activeObserver.observe(
        image: image,
        layout: .portraitMobile,
        rules: rules
    )
    let selected = try await selectedObserver.observe(
        image: image,
        layout: .portraitMobile,
        rules: rules
    )

    #expect(active.actionCandidates.map(\.ruleID) == ["mission_selection"])
    #expect(selected.actionCandidates.map(\.ruleID) == ["enter_ready"])
}

@Test
func duplicateRequiredContextInsideRegionIsRejectedAsAmbiguous() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("보상", rect: CGRect(x: 30, y: 230, width: 50, height: 25)),
            recognized("보상", rect: CGRect(x: 90, y: 230, width: 50, height: 25)),
            recognized("확인", rect: CGRect(x: 60, y: 265, width: 80, height: 25)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [
            makeRule(
                id: "ambiguous_context",
                requiredTexts: ["보상", "확인"],
                targetText: "확인"
            ),
        ]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func layoutRegionDisambiguatesDuplicateTargets() async throws {
    let inside = CGRect(x: 60, y: 240, width: 80, height: 30)
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", rect: inside),
            recognized("다시 하기", rect: CGRect(x: 60, y: 20, width: 80, height: 30)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.boundingBox == inside)
}

@Test
func clearTouchFiresOnLiveResultScreenDespiteLowConfidenceTitle() async throws {
    // 실측(2026-07-24, 마비노기 모바일 결과 화면). 300×200 fixture에
    // 정규화 위치를 맞춰 재현: '던전 클리어!'는 신뢰도 0.50이라 탈락하고
    // '화면을 터치해 주세요'(1.00)만으로 클리어 화면을 판별해야 한다.
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "던전 클리어!",
                confidence: 0.50,
                rect: CGRect(x: 140, y: 50, width: 24, height: 14)
            ),
            recognized(
                "160점 이상 S등급",
                confidence: 1.0,
                rect: CGRect(x: 50, y: 66, width: 76, height: 14)
            ),
            recognized(
                "화면을 터치해 주세요",
                confidence: 1.0,
                rect: CGRect(x: 120, y: 178, width: 60, height: 12)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "landscape-clear-touch"),
        layout: .landscape,
        rules: [liveClearTouchRule()]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.ruleID == "clear_touch")
    #expect(candidate.targetText == nil)
}

@Test
func clearTouchStaysSilentOnFieldScreenWithoutTouchPrompt() async throws {
    // 실측 필드 화면: 터치 유도 문구가 없으면 후보를 만들지 않는다.
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "마비노기 모바일",
                confidence: 1.0,
                rect: CGRect(x: 20, y: 4, width: 40, height: 10)
            ),
            recognized(
                "파티 플레이",
                confidence: 1.0,
                rect: CGRect(x: 20, y: 40, width: 40, height: 12)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "landscape-clear-touch"),
        layout: .landscape,
        rules: [liveClearTouchRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func safePointRuleReturnsCurrentImageClickTarget() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "화면을 터치해주세요",
                confidence: 0.92,
                rect: CGRect(x: 30, y: 220, width: 140, height: 25)
            ),
        ])
    )
    let rule = AutomationRule(
        id: "clear_touch",
        requiredTexts: ["화면을 터치해주세요"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: nil,
            safePointRegion: NormalizedRegion(
                minX: 0.4,
                minY: 0.45,
                maxX: 0.6,
                maxY: 0.55
            )
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0.7,
                maxX: 1,
                maxY: 1
            ),
        ]),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [rule]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.targetText == nil)
    expectSceneRect(
        candidate.boundingBox,
        equals: CGRect(x: 80, y: 135, width: 40, height: 30)
    )
    #expect(candidate.confidence == 0.92)
}

@Test
func landscapeUsesItsOwnSearchRegion() async throws {
    let landscapeTarget = CGRect(x: 120, y: 150, width: 60, height: 25)
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", rect: landscapeTarget),
            recognized("다시 하기", rect: CGRect(x: 120, y: 20, width: 60, height: 25)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "landscape-clear-touch"),
        layout: .landscape,
        rules: [retryRule()]
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.boundingBox == landscapeTarget)
}

@Test
func portraitRegionDoesNotLeakIntoLandscape() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("다시 하기", rect: CGRect(x: 130, y: 130, width: 40, height: 20)),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "landscape-clear-touch"),
        layout: .landscape,
        rules: [
            makeRule(
                id: "portrait_only",
                regions: LayoutRegionMap([
                    .portraitMobile: NormalizedRegion(
                        minX: 0,
                        minY: 0.7,
                        maxX: 1,
                        maxY: 1
                    ),
                ])
            ),
        ]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func koreanTextMatchesAfterWhitespaceNormalization() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "  다시\n\t하기  ",
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.count == 1)
}

@Test
func semanticMatchingDoesNotUseSubstringMatches() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기 안내",
                rect: CGRect(x: 40, y: 240, width: 120, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func observationsBelowRuleConfidenceAreIgnored() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                confidence: 0.79,
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test(arguments: [
    1.000_001,
    -0.001,
    Double.nan,
    Double.infinity,
])
func invalidActionConfidenceIsRejected(confidence: Double) async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                confidence: confidence,
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func malformedRecognizedBoundingBoxIsRejected() async throws {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                rect: CGRect(x: 100, y: 240, width: -40, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        image: try fixtureImage(named: "portrait-reward"),
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func fixtureImagesHaveStableMinimalDimensions() throws {
    let portrait = try fixtureImage(named: "portrait-reward")
    let landscape = try fixtureImage(named: "landscape-clear-touch")

    #expect(portrait.width == 200)
    #expect(portrait.height == 300)
    #expect(landscape.width == 300)
    #expect(landscape.height == 200)
}

@Test
func captureResultIdentityIsCarriedIntoSceneObservation() async throws {
    let image = try fixtureImage(named: "portrait-reward")
    let captureIdentity = try CaptureIdentity(
        sessionID: UUID(
            uuidString: "13572468-2468-1357-2468-135724681357"
        )!,
        sequence: 42
    )
    let capture = WindowCaptureResult(
        image: image,
        candidate: WindowCandidate(
            windowID: 7,
            processID: 42,
            bundleIdentifier: "com.example.game",
            title: "Game",
            frame: CGRect(x: 0, y: 0, width: 200, height: 300),
            isOnScreen: true,
            processLifetimeIdentity: try ProcessLifetimeIdentity(
                launchTimeIntervalSinceReferenceDate: 1_000
            )
        ),
        captureIdentity: captureIdentity
    )
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized(
                "다시 하기",
                rect: CGRect(x: 60, y: 240, width: 80, height: 30)
            ),
        ])
    )

    let result = try await observer.observe(
        capture: capture,
        layout: .portraitMobile,
        rules: [retryRule()]
    )

    #expect(result.captureIdentity == captureIdentity)
    #expect(result.imageSize == CGSize(width: 200, height: 300))
}

private struct FakeTextRecognizer: TextRecognizing {
    let observations: [RecognizedTextObservation]

    init(_ observations: [RecognizedTextObservation]) {
        self.observations = observations
    }

    func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation] {
        observations
    }
}

private struct FakeAppearanceAnalyzer: AppearanceAnalyzing {
    let entries: [(CGRect, AppearanceStatistics)]

    init(_ entries: [(CGRect, AppearanceStatistics)]) {
        self.entries = entries
    }

    func statistics(
        in image: CGImage,
        around textBoundingBox: CGRect
    ) -> AppearanceStatistics? {
        entries.first { $0.0 == textBoundingBox }?.1
    }
}

private let appearanceContextRect = CGRect(
    x: 50,
    y: 120,
    width: 70,
    height: 24
)
private let appearanceTargetRect = CGRect(
    x: 55,
    y: 160,
    width: 90,
    height: 28
)
private let selectedGreyAppearance = AppearanceStatistics(
    medianSaturation: 0.08,
    medianLuminance: 0.55,
    sampleCount: 100
)
private let enabledTargetAppearance = AppearanceStatistics(
    medianSaturation: 0.45,
    medianLuminance: 0.55,
    sampleCount: 100
)

private func appearanceObserver(
    context: AppearanceStatistics,
    target: AppearanceStatistics
) -> (
    observer: SceneObserver,
    contextRect: CGRect,
    targetRect: CGRect
) {
    let observer = SceneObserver(
        textRecognizer: FakeTextRecognizer([
            recognized("도전", rect: appearanceContextRect),
            recognized("입장하기", rect: appearanceTargetRect),
        ]),
        appearanceAnalyzer: FakeAppearanceAnalyzer([
            (appearanceContextRect, context),
            (appearanceTargetRect, target),
        ])
    )
    return (observer, appearanceContextRect, appearanceTargetRect)
}

private func enterReadyAppearanceRule() -> AutomationRule {
    AutomationRule(
        id: "enter_ready",
        requiredTexts: ["입장하기"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: "입장하기",
            safePointRegion: nil
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
            .landscape: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
        ]),
        appearance: AutomationAppearanceConstraint(
            contextText: "도전",
            contextRegions: LayoutRegionMap([
                .portraitMobile: NormalizedRegion(
                    minX: 0,
                    minY: 0,
                    maxX: 1,
                    maxY: 0.8
                ),
                .landscape: NormalizedRegion(
                    minX: 0,
                    minY: 0,
                    maxX: 1,
                    maxY: 0.8
                ),
            ]),
            contextRange: AppearanceRange(
                minimumSaturation: 0,
                maximumSaturation: 0.22,
                minimumLuminance: 0.15,
                maximumLuminance: 0.9
            ),
            targetRange: AppearanceRange(
                minimumSaturation: 0.12,
                maximumSaturation: 1,
                minimumLuminance: 0.25,
                maximumLuminance: 0.95
            )
        ),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 120
    )
}

private func missionSelectionAppearanceRule() -> AutomationRule {
    AutomationRule(
        id: "mission_selection",
        requiredTexts: ["도전"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: "도전",
            safePointRegion: nil
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
            .landscape: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
        ]),
        appearance: AutomationAppearanceConstraint(
            contextText: "도전",
            contextRegions: LayoutRegionMap([
                .portraitMobile: NormalizedRegion(
                    minX: 0,
                    minY: 0,
                    maxX: 1,
                    maxY: 1
                ),
                .landscape: NormalizedRegion(
                    minX: 0,
                    minY: 0,
                    maxX: 1,
                    maxY: 1
                ),
            ]),
            contextRange: AppearanceRange(
                minimumSaturation: 0.25,
                maximumSaturation: 1,
                minimumLuminance: 0.25,
                maximumLuminance: 0.95
            ),
            targetRange: AppearanceRange(
                minimumSaturation: 0.25,
                maximumSaturation: 1,
                minimumLuminance: 0.25,
                maximumLuminance: 0.95
            )
        ),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )
}

private func liveClearTouchRule() -> AutomationRule {
    AutomationRule(
        id: "clear_touch",
        requiredTexts: ["화면을 터치해 주세요"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: nil,
            safePointRegion: NormalizedRegion(
                minX: 0.45,
                minY: 0.75,
                maxX: 0.55,
                maxY: 0.85
            )
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0.05,
                minY: 0.05,
                maxX: 0.95,
                maxY: 0.95
            ),
            .landscape: NormalizedRegion(
                minX: 0.05,
                minY: 0.05,
                maxX: 0.95,
                maxY: 0.95
            ),
        ]),
        minimumOCRConfidence: 0.85,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )
}

private func recognized(
    _ text: String,
    confidence: Double = 0.9,
    rect: CGRect
) -> RecognizedTextObservation {
    RecognizedTextObservation(
        text: text,
        confidence: confidence,
        boundingBox: rect
    )
}

private func retryRule() -> AutomationRule {
    makeRule()
}

private func makeRule(
    id: String = "reward_retry",
    requiredTexts: [String] = ["다시 하기"],
    forbiddenTexts: [String] = ["장면 넘기기"],
    targetText: String = "다시 하기",
    regions: LayoutRegionMap = LayoutRegionMap([
        .portraitMobile: NormalizedRegion(
            minX: 0.1,
            minY: 0.7,
            maxX: 0.9,
            maxY: 1
        ),
        .landscape: NormalizedRegion(
            minX: 0.2,
            minY: 0.65,
            maxX: 0.8,
            maxY: 1
        ),
    ]),
    appearance: AutomationAppearanceConstraint? = nil
) -> AutomationRule {
    AutomationRule(
        id: id,
        requiredTexts: requiredTexts,
        forbiddenTexts: forbiddenTexts,
        action: AutomationAction(
            targetText: targetText,
            safePointRegion: nil
        ),
        regions: regions,
        appearance: appearance,
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )
}

private enum FixtureError: Error {
    case missing(String)
    case invalidImage(String)
}

private func fixtureImage(named name: String) throws -> CGImage {
    guard
        let url = Bundle.module.url(
            forResource: name,
            withExtension: "png",
            subdirectory: "Fixtures"
        )
    else {
        throw FixtureError.missing(name)
    }
    guard
        let source = CGImageSourceCreateWithURL(
            url as CFURL,
            nil
        ),
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        throw FixtureError.invalidImage(name)
    }
    return image
}

/// FakeTextRecognizer는 이미지를 크기 계산에만 쓰므로, 실측 캡처 크기의
/// 빈 이미지로 정규화 좌표를 실제 픽셀 박스와 일치시킨다.
private func blankImage(width: Int, height: Int) throws -> CGImage {
    guard
        let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ),
        let image = context.makeImage()
    else {
        throw FixtureError.invalidImage("blank \(width)x\(height)")
    }
    return image
}

private func expectSceneRect(
    _ actual: CGRect,
    equals expected: CGRect,
    tolerance: CGFloat = 0.000_001
) {
    #expect(abs(actual.origin.x - expected.origin.x) < tolerance)
    #expect(abs(actual.origin.y - expected.origin.y) < tolerance)
    #expect(abs(actual.size.width - expected.size.width) < tolerance)
    #expect(abs(actual.size.height - expected.size.height) < tolerance)
}

@Test
func entryNeverFiresWhileTheMissionBadgeIsStillOnScreen() throws {
    // 회귀(2026-07-26 13:16:50): 임무를 해제하지 않은 채 '입장하기'를 눌러
    // 은동전 10개가 나갔다. 그때까지 이 규칙을 막던 건 둘 다 불안정했다 —
    // 25자 안내문 완전일치, 그리고 OCR이 코인 숫자를 버튼 글자에 붙여
    // ('10 입장하기') 읽어 주기를 바라는 것. 둘 다 어긋나면 그대로 뚫린다.
    // '선택됨'은 3글자에 선택 상태에서만 뜨므로 훨씬 단단한 가드다.
    let rule = try #require(
        try RuleLoader().loadDefaultRules().first { $0.id == "enter_ready" }
    )
    let size = CGSize(width: 1512, height: 949)
    let candidate = SceneObserver.actionCandidate(
        for: rule,
        observations: [
            recognized(
                "입장하기",
                confidence: 0.5,
                rect: CGRect(x: 1100, y: 865, width: 100, height: 30)
            ),
            recognized(
                "선택됨",
                confidence: 0.5,
                rect: CGRect(x: 536, y: 374, width: 68, height: 27)
            ),
        ],
        layout: .landscape,
        imageSize: size
    )

    #expect(candidate == nil)
}
