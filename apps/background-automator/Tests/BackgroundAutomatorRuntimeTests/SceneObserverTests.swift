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
    ])
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
