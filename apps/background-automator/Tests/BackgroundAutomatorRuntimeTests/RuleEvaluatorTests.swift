import BackgroundAutomatorCore
import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func evaluatorRequiresConsecutiveStableObservations() throws {
    var evaluator = try RuleEvaluator(rules: [evaluatorRule()])
    let scene = evaluatorScene()
    let window = evaluatorWindow()

    #expect(
        evaluator.evaluate(
            observation: scene,
            windowIdentity: window,
            layout: .portraitMobile
        ) == nil
    )
    let candidate = evaluator.evaluate(
        observation: scene,
        windowIdentity: window,
        layout: .portraitMobile
    )

    #expect(candidate?.ruleID == "retry")
    #expect(candidate?.targetPixelRect == evaluatorTargetRect)
}

@Test
func unsupportedLayoutAmbiguityAndNoSceneResetStability() throws {
    var evaluator = try RuleEvaluator(rules: [
        evaluatorRule(),
        evaluatorRule(id: "confirm", targetText: "확인"),
    ])
    let window = evaluatorWindow()
    let valid = evaluatorScene()
    let ambiguous = SceneObservation(
        recognizedTexts: valid.recognizedTexts,
        actionCandidates: [
            valid.actionCandidates[0],
            SceneActionCandidate(
                ruleID: "confirm",
                targetText: "확인",
                boundingBox: CGRect(x: 120, y: 220, width: 60, height: 30),
                confidence: 0.95
            ),
        ]
    )

    #expect(evaluator.evaluate(
        observation: valid,
        windowIdentity: window,
        layout: .portraitMobile
    ) == nil)
    #expect(evaluator.evaluate(
        observation: ambiguous,
        windowIdentity: window,
        layout: .portraitMobile
    ) == nil)
    #expect(evaluator.evaluate(
        observation: valid,
        windowIdentity: window,
        layout: .unsupported
    ) == nil)
    #expect(evaluator.evaluate(
        observation: nil,
        windowIdentity: window,
        layout: .portraitMobile
    ) == nil)
    #expect(evaluator.evaluate(
        observation: valid,
        windowIdentity: window,
        layout: .portraitMobile
    ) == nil)
}

@Test
func exactWhitespaceNormalizedSceneSkipAlwaysBlocksAction() throws {
    var evaluator = try RuleEvaluator(rules: [evaluatorRule()])
    let unsafe = SceneObservation(
        recognizedTexts: [
            recognizedForEvaluator("다시 하기"),
            recognizedForEvaluator(" 장면\n 넘기기 "),
        ],
        actionCandidates: [
            evaluatorScene().actionCandidates[0],
        ]
    )

    #expect(evaluator.evaluate(
        observation: unsafe,
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ) == nil)
    #expect(evaluator.evaluate(
        observation: unsafe,
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ) == nil)
}

@Test
func evaluatorComposesWithSceneObserverSafetyFiltering() async throws {
    let rule = evaluatorRule()
    var evaluator = try RuleEvaluator(rules: [rule])
    let window = evaluatorWindow()
    let lowConfidence = try await evaluatorObservedScene(
        texts: [
            recognizedForEvaluator("다시 하기", confidence: 0.79),
        ],
        rule: rule
    )
    let forbidden = try await evaluatorObservedScene(
        texts: [
            recognizedForEvaluator("다시 하기"),
            recognizedForEvaluator("장면 넘기기", confidence: 0.1),
        ],
        rule: rule
    )
    let ambiguous = try await evaluatorObservedScene(
        texts: [
            recognizedForEvaluator("다시 하기"),
            recognizedForEvaluator(
                "다시 하기",
                rect: CGRect(x: 120, y: 70, width: 60, height: 20)
            ),
        ],
        rule: rule
    )

    #expect(lowConfidence.actionCandidates.isEmpty)
    #expect(forbidden.actionCandidates.isEmpty)
    #expect(ambiguous.actionCandidates.isEmpty)
    for scene in [lowConfidence, forbidden, ambiguous] {
        #expect(evaluator.evaluate(
            observation: scene,
            windowIdentity: window,
            layout: .portraitMobile
        ) == nil)
    }
}

@Test
func invalidRuleConfigurationIsRejected() {
    let unsafeMinimum = AutomationRule(
        id: "retry",
        requiredTexts: ["다시 하기"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: "다시 하기",
            safePointRegion: nil
        ),
        regions: LayoutRegionMap([:]),
        minimumOCRConfidence: .nan,
        stableObservationCount: 1,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )

    #expect(throws: RuleEvaluatorError.invalidRuleConfiguration(ruleID: "retry")) {
        try RuleEvaluator(rules: [unsafeMinimum])
    }
    #expect(throws: RuleEvaluatorError.duplicateRuleID("retry")) {
        try RuleEvaluator(rules: [evaluatorRule(), evaluatorRule()])
    }
}

@Test
func sceneFingerprintIsDeterministicAcrossWhitespaceOrderAndOCRJitter() {
    let first = SceneFingerprint(
        semanticTexts: [" 다시 하기 ", "보상"],
        targetText: "다시 하기"
    )
    let reordered = SceneFingerprint(
        semanticTexts: ["보상", "다시\n하기"],
        targetText: "다시 하기"
    )
    let changedContext = SceneFingerprint(
        semanticTexts: ["보상", "계속 하기"],
        targetText: "계속 하기"
    )

    #expect(first == reordered)
    #expect(first != changedContext)
    #expect(first.semanticTexts == ["다시하기", "보상"])
}

@Test
func finalRevalidationRequiresFreshMatchingCapture() throws {
    var evaluator = try RuleEvaluator(
        rules: [evaluatorRule()],
        targetRectangleTolerancePixels: 2
    )
    let scene = evaluatorScene()
    let window = evaluatorWindow()
    _ = evaluator.evaluate(
        observation: scene,
        windowIdentity: window,
        layout: .portraitMobile
    )
    let evaluatedCandidate = evaluator.evaluate(
        observation: scene,
        windowIdentity: window,
        layout: .portraitMobile
    )
    let candidate = try #require(evaluatedCandidate)
    let freshWithinTolerance = evaluatorScene(
        targetRect: CGRect(x: 41, y: 74, width: 41, height: 16)
    )

    #expect(evaluator.revalidate(
        candidate,
        freshObservation: freshWithinTolerance,
        windowIdentity: window,
        layout: .portraitMobile
    ))
}

@Test
func finalRevalidationRejectsChangedSafetyIdentityOrGeometry() throws {
    let evaluator = try RuleEvaluator(
        rules: [
            evaluatorRule(),
            evaluatorRule(id: "other", targetText: "다시 하기"),
        ],
        targetRectangleTolerancePixels: 2
    )
    let candidate = try evaluatorActionCandidate()
    let changedRule = SceneObservation(
        recognizedTexts: evaluatorScene().recognizedTexts,
        actionCandidates: [
            SceneActionCandidate(
                ruleID: "other",
                targetText: "다시 하기",
                boundingBox: evaluatorTargetRect,
                confidence: 0.95
            ),
        ]
    )
    let changedScene = evaluatorScene(
        recognizedTexts: [
            recognizedForEvaluator("다시 하기"),
            recognizedForEvaluator("새 문맥"),
        ]
    )
    let movedTarget = evaluatorScene(
        targetRect: CGRect(x: 43, y: 75, width: 40, height: 15)
    )
    let movedFrame = evaluatorWindow(
        frame: CGRect(x: 1, y: 0, width: 626, height: 949)
    )

    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: changedRule,
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: changedScene,
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(),
        windowIdentity: movedFrame,
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(),
        windowIdentity: evaluatorWindow(),
        layout: .landscape
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: movedTarget,
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
}

private let evaluatorTargetRect = CGRect(
    x: 40,
    y: 75,
    width: 40,
    height: 15
)

private func evaluatorRule(
    id: String = "retry",
    targetText: String = "다시 하기"
) -> AutomationRule {
    AutomationRule(
        id: id,
        requiredTexts: [targetText],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: targetText,
            safePointRegion: nil
        ),
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
        ]),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )
}

private func evaluatorScene(
    recognizedTexts: [RecognizedTextObservation]? = nil,
    targetRect: CGRect = evaluatorTargetRect
) -> SceneObservation {
    SceneObservation(
        recognizedTexts: recognizedTexts ?? [
            recognizedForEvaluator("다시 하기", rect: targetRect),
        ],
        actionCandidates: [
            SceneActionCandidate(
                ruleID: "retry",
                targetText: "다시 하기",
                boundingBox: targetRect,
                confidence: 0.95
            ),
        ]
    )
}

private func evaluatorWindow(
    frame: CGRect = CGRect(x: 0, y: 0, width: 626, height: 949)
) -> WindowCandidate {
    WindowCandidate(
        windowID: 7,
        processID: 42,
        bundleIdentifier: "com.example.game",
        title: "Mabinogi Mobile",
        frame: frame,
        isOnScreen: true
    )
}

private func evaluatorActionCandidate() throws -> ActionCandidate {
    try ActionCandidate(
        ruleID: "retry",
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile,
        sceneFingerprint: SceneFingerprint(
            semanticTexts: ["다시 하기"],
            targetText: "다시 하기"
        ),
        targetPixelRect: evaluatorTargetRect
    )
}

private func recognizedForEvaluator(
    _ text: String,
    confidence: Double = 0.95,
    rect: CGRect = evaluatorTargetRect
) -> RecognizedTextObservation {
    RecognizedTextObservation(
        text: text,
        confidence: confidence,
        boundingBox: rect
    )
}

private struct EvaluatorTextRecognizer: TextRecognizing {
    let observations: [RecognizedTextObservation]

    func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation] {
        observations
    }
}

private func evaluatorObservedScene(
    texts: [RecognizedTextObservation],
    rule: AutomationRule
) async throws -> SceneObservation {
    let observer = SceneObserver(
        textRecognizer: EvaluatorTextRecognizer(observations: texts)
    )
    return try await observer.observe(
        image: evaluatorImage(),
        layout: .portraitMobile,
        rules: [rule]
    )
}

private func evaluatorImage() -> CGImage {
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let context = CGContext(
        data: nil,
        width: 200,
        height: 100,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )!
    return context.makeImage()!
}
