import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func evaluatorRequiresConsecutiveStableObservations() throws {
    var evaluator = try RuleEvaluator(rules: [evaluatorRule()])
    let firstScene = evaluatorScene(captureSequence: 1)
    let secondScene = evaluatorScene(captureSequence: 2)
    let window = evaluatorWindow()

    #expect(
        evaluator.evaluate(
            observation: firstScene,
            windowIdentity: window,
            layout: .portraitMobile
        ) == nil
    )
    let candidate = evaluator.evaluate(
        observation: secondScene,
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
                rect: CGRect(x: 80, y: 70, width: 40, height: 20)
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
    let firstScene = evaluatorScene(captureSequence: 10)
    let secondScene = evaluatorScene(captureSequence: 11)
    let window = evaluatorWindow()
    _ = evaluator.evaluate(
        observation: firstScene,
        windowIdentity: window,
        layout: .portraitMobile
    )
    let evaluatedCandidate = evaluator.evaluate(
        observation: secondScene,
        windowIdentity: window,
        layout: .portraitMobile
    )
    let candidate = try #require(evaluatedCandidate)
    let freshWithinTolerance = evaluatorScene(
        captureSequence: 12,
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
func finalRevalidationRejectsSameOlderAndRestartedCaptureIdentities() throws {
    let evaluator = try RuleEvaluator(rules: [evaluatorRule()])
    let candidate = try evaluatorActionCandidate(captureSequence: 10)

    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(captureSequence: 10),
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(captureSequence: 9),
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(
            captureSequence: 11,
            captureSessionID: UUID(
                uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
            )!
        ),
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile
    ))
}

@Test
func maliciousProgrammaticCandidatesAreRejected() throws {
    let rule = evaluatorRule()
    let maliciousCandidates = [
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "확인",
            boundingBox: evaluatorTargetRect,
            confidence: 0.95
        ),
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "다시 하기",
            boundingBox: CGRect(x: 150, y: 75, width: 40, height: 15),
            confidence: 0.95
        ),
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "다시 하기",
            boundingBox: evaluatorTargetRect,
            confidence: .nan
        ),
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "다시 하기",
            boundingBox: evaluatorTargetRect,
            confidence: 0
        ),
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "다시 하기",
            boundingBox: evaluatorTargetRect,
            confidence: 0.79
        ),
        SceneActionCandidate(
            ruleID: "retry",
            targetText: "다시 하기",
            boundingBox: evaluatorTargetRect,
            confidence: 1.01
        ),
    ]

    for (offset, malicious) in maliciousCandidates.enumerated() {
        var evaluator = try RuleEvaluator(rules: [rule])
        for sequence in [UInt64(offset * 2 + 1), UInt64(offset * 2 + 2)] {
            let scene = evaluatorScene(
                captureSequence: sequence,
                actionCandidate: malicious
            )
            #expect(evaluator.evaluate(
                observation: scene,
                windowIdentity: evaluatorWindow(),
                layout: .portraitMobile
            ) == nil)
        }
    }
}

@Test
func forgedSafePointCandidateIsRejected() throws {
    let safeRule = evaluatorRule(
        requiredTexts: ["화면을 터치해주세요"],
        targetText: nil,
        safePointRegion: NormalizedRegion(
            minX: 0.4,
            minY: 0.4,
            maxX: 0.6,
            maxY: 0.6
        )
    )
    let forged = SceneActionCandidate(
        ruleID: "retry",
        targetText: nil,
        boundingBox: CGRect(x: 70, y: 40, width: 40, height: 20),
        confidence: 0.95
    )
    var evaluator = try RuleEvaluator(rules: [safeRule])

    for sequence in UInt64(1) ... 2 {
        let scene = evaluatorScene(
            captureSequence: sequence,
            recognizedTexts: [
                recognizedForEvaluator("화면을 터치해주세요"),
            ],
            actionCandidate: forged
        )
        #expect(evaluator.evaluate(
            observation: scene,
            windowIdentity: evaluatorWindow(),
            layout: .portraitMobile
        ) == nil)
    }
}

@Test
func evaluatorUsesCompleteSharedRuleValidation() {
    let invalidTiming = evaluatorRule(
        postActionDelaySeconds: .nan,
        cooldownSeconds: 0
    )
    let invalidAction = evaluatorRule(
        targetText: nil,
        safePointRegion: nil
    )
    let contextFreeSafePoint = evaluatorRule(
        requiredTexts: [],
        targetText: nil,
        safePointRegion: NormalizedRegion(
            minX: 0.4,
            minY: 0.4,
            maxX: 0.6,
            maxY: 0.6
        )
    )
    let emptyRegions = evaluatorRule(
        regions: LayoutRegionMap([:])
    )
    let unsupportedRegion = evaluatorRule(
        regions: LayoutRegionMap([
            .unsupported: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
        ])
    )
    let malformedRegion = evaluatorRule(
        regions: LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: .nan,
                minY: 0,
                maxX: 1,
                maxY: 1
            ),
        ])
    )
    let blankForbiddenText = evaluatorRule(
        forbiddenTexts: [" "]
    )

    for rule in [
        invalidTiming,
        invalidAction,
        contextFreeSafePoint,
        emptyRegions,
        unsupportedRegion,
        malformedRegion,
        blankForbiddenText,
    ] {
        #expect(throws: RuleEvaluatorError.invalidRuleConfiguration(ruleID: "retry")) {
            try RuleEvaluator(rules: [rule])
        }
    }
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
        captureIdentity: try CaptureIdentity(
            sessionID: evaluatorCaptureSessionID,
            sequence: 2
        ),
        imageSize: CGSize(width: 200, height: 100),
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
        captureSequence: 2,
        recognizedTexts: [
            recognizedForEvaluator("다시 하기"),
            recognizedForEvaluator("새 문맥"),
        ]
    )
    let movedTarget = evaluatorScene(
        captureSequence: 2,
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
        freshObservation: evaluatorScene(captureSequence: 2),
        windowIdentity: movedFrame,
        layout: .portraitMobile
    ))
    #expect(!evaluator.revalidate(
        candidate,
        freshObservation: evaluatorScene(captureSequence: 2),
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
    requiredTexts: [String]? = nil,
    forbiddenTexts: [String] = ["장면 넘기기"],
    targetText: String? = "다시 하기",
    safePointRegion: NormalizedRegion? = nil,
    postActionDelaySeconds: Double = 0.5,
    cooldownSeconds: Double = 2,
    regions: LayoutRegionMap? = nil
) -> AutomationRule {
    AutomationRule(
        id: id,
        requiredTexts: requiredTexts ?? targetText.map { [$0] } ?? [],
        forbiddenTexts: forbiddenTexts,
        action: AutomationAction(
            targetText: targetText,
            safePointRegion: safePointRegion
        ),
        regions: regions ?? LayoutRegionMap([
            .portraitMobile: NormalizedRegion(
                minX: 0,
                minY: 0,
                maxX: 0.6,
                maxY: 1
            ),
        ]),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: postActionDelaySeconds,
        cooldownSeconds: cooldownSeconds
    )
}

private func evaluatorScene(
    captureSequence: UInt64 = 1,
    captureSessionID: UUID = evaluatorCaptureSessionID,
    recognizedTexts: [RecognizedTextObservation]? = nil,
    targetRect: CGRect = evaluatorTargetRect,
    actionCandidate: SceneActionCandidate? = nil
) -> SceneObservation {
    SceneObservation(
        captureIdentity: try! CaptureIdentity(
            sessionID: captureSessionID,
            sequence: captureSequence
        ),
        imageSize: CGSize(width: 200, height: 100),
        recognizedTexts: recognizedTexts ?? [
            recognizedForEvaluator("다시 하기", rect: targetRect),
        ],
        actionCandidates: [
            actionCandidate ?? SceneActionCandidate(
                ruleID: "retry",
                targetText: "다시 하기",
                boundingBox: targetRect,
                confidence: 0.95
            ),
        ]
    )
}

private func evaluatorWindow(
    frame: CGRect = CGRect(x: 0, y: 0, width: 626, height: 949),
    launchTime: Double = 1_000
) -> WindowCandidate {
    WindowCandidate(
        windowID: 7,
        processID: 42,
        bundleIdentifier: "com.example.game",
        title: "Mabinogi Mobile",
        frame: frame,
        isOnScreen: true,
        processLifetimeIdentity: try! ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: launchTime
        )
    )
}

private func evaluatorActionCandidate(
    captureSequence: UInt64 = 1
) throws -> ActionCandidate {
    try ActionCandidate(
        ruleID: "retry",
        windowIdentity: evaluatorWindow(),
        layout: .portraitMobile,
        sceneFingerprint: SceneFingerprint(
            semanticTexts: ["다시 하기"],
            targetText: "다시 하기"
        ),
        captureIdentity: try CaptureIdentity(
            sessionID: evaluatorCaptureSessionID,
            sequence: captureSequence
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
        captureIdentity: try CaptureIdentity(
            sessionID: evaluatorCaptureSessionID,
            sequence: 1
        ),
        layout: .portraitMobile,
        rules: [rule]
    )
}

private let evaluatorCaptureSessionID = UUID(
    uuidString: "11111111-2222-3333-4444-555555555555"
)!

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
