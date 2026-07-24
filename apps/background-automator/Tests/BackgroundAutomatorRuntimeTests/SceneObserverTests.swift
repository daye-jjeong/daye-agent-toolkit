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
