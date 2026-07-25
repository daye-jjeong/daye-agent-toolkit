import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func capturedWindowObserverComposesCaptureLayoutAndOCR() async throws {
    let capture = try WindowCaptureResult(
        image: coordinatorImage(width: 600, height: 900),
        candidate: coordinatorWindow,
        captureIdentity: CaptureIdentity(
            sessionID: coordinatorCaptureSession,
            sequence: 1
        )
    )
    let captureService = FakeCoordinatorCaptureService(result: capture)
    let textRecognizer = CoordinatorTextRecognizer(observations: [
        RecognizedTextObservation(
            text: "다시 하기",
            confidence: 0.99,
            boundingBox: CGRect(x: 20, y: 700, width: 80, height: 20)
        ),
    ])
    let observer = CapturedWindowSceneObserver(
        captureService: captureService,
        sceneObserver: SceneObserver(textRecognizer: textRecognizer),
        rules: coordinatorRules(),
        bundleIdentifier: "com.example.game",
        titleContains: "Game"
    )

    let frame = try await observer.observe()

    #expect(frame.window == coordinatorWindow)
    #expect(frame.layout == .portraitMobile)
    #expect(
        frame.observation.captureIdentity
            == capture.captureIdentity
    )
    #expect(frame.observation.actionCandidates.first?.ruleID == "reward_retry")
    #expect(await captureService.requestCount == 1)
}

@Test
func forbiddenFreezeExemptsSceneSkipCandidate() {
    let sceneSkipText = RecognizedTextObservation(
        text: "장면 넘기기",
        confidence: 0.5,
        boundingBox: CGRect(x: 1330, y: 60, width: 80, height: 20)
    )
    let sceneSkipCandidate = SceneActionCandidate(
        ruleID: "scene_skip",
        targetText: nil,
        boundingBox: CGRect(x: 1000, y: 200, width: 40, height: 20),
        confidence: 0.5
    )
    let enterCandidate = SceneActionCandidate(
        ruleID: "enter_ready",
        targetText: "입장하기",
        boundingBox: CGRect(x: 700, y: 800, width: 40, height: 20),
        confidence: 0.5
    )

    // 컷신: 장면 넘기기 + scene_skip 후보 → 얼리지 않고 빈 공간 탭으로 진행.
    let cutscene = SceneObservation(
        recognizedTexts: [sceneSkipText],
        actionCandidates: [sceneSkipCandidate]
    )
    #expect(
        !AutomationCoordinator.shouldFreezeForForbiddenContent(cutscene)
    )

    // 장면 넘기기가 떴는데 scene_skip이 아닌 후보 → 종전대로 얼린다(오클릭 방지).
    let danger = SceneObservation(
        recognizedTexts: [sceneSkipText],
        actionCandidates: [enterCandidate]
    )
    #expect(
        AutomationCoordinator.shouldFreezeForForbiddenContent(danger)
    )

    // 장면 넘기기 없음 → 얼리지 않는다.
    let clean = SceneObservation(
        recognizedTexts: [
            RecognizedTextObservation(
                text: "입장하기",
                confidence: 0.5,
                boundingBox: CGRect(x: 700, y: 800, width: 40, height: 20)
            ),
        ],
        actionCandidates: [enterCandidate]
    )
    #expect(
        !AutomationCoordinator.shouldFreezeForForbiddenContent(clean)
    )
}

@Test
func coordinatorRejectsWeakenedSafetyTimings() throws {
    let observer = FakeAutomationObserver(frames: [])
    let actioner = FakeAutomationActioner(results: [])
    let clock = FakeAutomationClock()

    #expect(
        throws: AutomationCoordinatorError.invalidIdleThreshold
    ) {
        _ = try AutomationCoordinator(
            rules: coordinatorRules(),
            observer: observer,
            inputMonitor: ImmediateIdleMonitor(),
            actionPerformer: actioner,
            clock: clock,
            idleThreshold: .milliseconds(500)
        )
    }
    #expect(
        throws: AutomationCoordinatorError.invalidClearTouchDelay
    ) {
        _ = try AutomationCoordinator(
            rules: coordinatorRules(),
            observer: observer,
            inputMonitor: ImmediateIdleMonitor(),
            actionPerformer: actioner,
            clock: clock,
            clearTouchDelay: .milliseconds(500)
        )
    }
    #expect(
        throws: AutomationCoordinatorError.invalidEnterReadyCooldown
    ) {
        _ = try AutomationCoordinator(
            rules: coordinatorRules(),
            observer: observer,
            inputMonitor: ImmediateIdleMonitor(),
            actionPerformer: actioner,
            clock: clock,
            enterReadyCooldown: .seconds(1)
        )
    }
}

@Test
func screenProgressAlwaysAdoptsNewestRecognizedScene() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .clearTouch, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .continueDialog, sequence: 3),
        .make(scene: .missionSelection, sequence: 4),
        .make(scene: .enterReady, sequence: 5),
        .make(scene: .running, sequence: 6),
    ])

    await fixture.coordinator.start()

    for expected in [
        AutomationScene.clearTouch,
        .rewardRetry,
        .continueDialog,
        .missionSelection,
        .enterReady,
    ] {
        _ = try await fixture.coordinator.runCycle()
        #expect(await fixture.coordinator.state == .observing(expected))
    }
    _ = try await fixture.coordinator.runCycle()
    #expect(await fixture.coordinator.state == .unknown)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func userCanJumpMultipleStepsWithoutCoordinatorGuessingIntermediateProgress() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .clearTouch, sequence: 1),
        .make(scene: .enterReady, sequence: 2),
    ])
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    #expect(await fixture.coordinator.state == .observing(.enterReady))
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func unknownScreenDoesNothingAndLaterRecognizedScreenResynchronizes() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: nil, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
    ])
    await fixture.coordinator.start()

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .unknown)
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .observing(.rewardRetry))
}

@Test
func forbiddenAmbiguousAndUnsupportedObservationsNeverAct() async throws {
    let frames = [
        AutomationScreenFrame.make(
            scene: .rewardRetry,
            sequence: 1,
            texts: ["다시 하기", "장면 넘기기"]
        ),
        .make(
            scene: .rewardRetry,
            sequence: 2,
            candidateRuleIDs: ["reward_retry", "continue_dialog"]
        ),
        .make(
            scene: .rewardRetry,
            sequence: 3,
            layout: .unsupported
        ),
    ]
    let fixture = try CoordinatorFixture(frames: frames)
    await fixture.coordinator.start()

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .attention(.forbiddenContent))
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .attention(.ambiguousObservation))
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .attention(.unsupportedLayout))
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func sceneOnlyAllowsItsOwnRule() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(
            scene: .enterReady,
            sequence: 1,
            candidateRuleIDs: ["reward_retry"]
        ),
        .make(
            scene: .enterReady,
            sequence: 2,
            candidateRuleIDs: ["reward_retry"]
        ),
    ])
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    #expect(await fixture.coordinator.state == .unknown)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func conflictingSceneTextsRejectOtherwisePlausibleCandidate() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(
            scene: .enterReady,
            sequence: 1,
            texts: ["도전", "입장하기"]
        ),
    ])
    await fixture.coordinator.start()

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .unknown)
}

@Test
func rawRunningTextAloneRemainsUnknown() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .running, sequence: 1),
    ])
    await fixture.coordinator.start()

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .unknown)
}

@Test
func validatedCandidateAdoptsItsActionScene() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .continueDialog, sequence: 1),
    ])
    await fixture.coordinator.start()

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .observing(.continueDialog))
}

@Test
func clearTouchWaitsAtLeastOneSecondFromFirstRecognition() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .clearTouch, sequence: 1),
        .make(scene: .clearTouch, sequence: 2),
        .make(scene: .clearTouch, sequence: 3),
        .make(scene: .clearTouch, sequence: 4),
    ])
    await fixture.coordinator.start()

    await fixture.clock.set(.zero)
    _ = try await fixture.coordinator.runCycle()
    await fixture.clock.set(.milliseconds(500))
    _ = try await fixture.coordinator.runCycle()
    #expect(await fixture.actioner.requests.isEmpty)

    await fixture.clock.set(.seconds(1))
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
    #expect(await fixture.actioner.requests.count == 1)
}

@Test
func restartRequiresANewClearTouchDelayWindow() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .clearTouch, sequence: 1),
        .make(scene: .clearTouch, sequence: 2),
        .make(scene: .clearTouch, sequence: 3),
        .make(scene: .clearTouch, sequence: 4),
    ])
    await fixture.clock.set(.zero)
    await fixture.coordinator.start()
    _ = try await fixture.coordinator.runCycle()

    await fixture.coordinator.stop()
    await fixture.clock.set(.seconds(100))
    await fixture.coordinator.start()
    _ = try await fixture.coordinator.runCycle()
    await fixture.clock.set(.milliseconds(100_500))

    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func actionUsesFreshRevalidatedCaptureAndCurrentTargetRectangle() async throws {
    let first = CGRect(x: 20, y: 40, width: 40, height: 20)
    let latest = CGRect(x: 21, y: 41, width: 40, height: 20)
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .rewardRetry, sequence: 1, targetRect: first),
        .make(scene: .rewardRetry, sequence: 2, targetRect: first),
        .make(scene: .rewardRetry, sequence: 3, targetRect: latest),
    ])
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )

    let request = try #require(await fixture.actioner.requests.first)
    #expect(request.targetBox == CGRect(x: 121, y: 241, width: 40, height: 20))
    #expect(request.expectedInputGeneration == 7)
    #expect(await fixture.observerCallCount() == 3)
}

@Test
func staleFinalCaptureDoesNotClickAndRequiresFreshStability() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
        .make(scene: .rewardRetry, sequence: 4),
        .make(scene: .rewardRetry, sequence: 5),
    ])
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.actioner.requests.isEmpty)
    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
}

@Test
func changedProcessLifetimeOnFinalCaptureNeverClicks() async throws {
    let restartedWindow = WindowCandidate(
        windowID: coordinatorWindow.windowID,
        processID: coordinatorWindow.processID,
        bundleIdentifier: coordinatorWindow.bundleIdentifier,
        title: coordinatorWindow.title,
        frame: coordinatorWindow.frame,
        isOnScreen: true,
        processLifetimeIdentity: try ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: 456
        )
    )
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(
            scene: .rewardRetry,
            sequence: 3,
            window: restartedWindow
        ),
    ])
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func changedUserInputGenerationRearmsFreshStabilityWithoutProgress() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: .inputGenerationChanged(expected: 7, actual: 8),
        restorationFailures: []
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: .rewardRetry, sequence: 4),
            .make(scene: .rewardRetry, sequence: 5),
            .make(scene: .rewardRetry, sequence: 6),
        ],
        actionResults: [.failure(error), .success]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.cancelled)
    )
    #expect(await fixture.coordinator.state == .observing(.rewardRetry))
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
}

@Test
func realForegroundPostClickCancellationBlocksAutomaticRetry() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
        .make(scene: .rewardRetry, sequence: 4),
    ])
    let foreground = makeRealForegroundAction(
        sleeper: CancellingPostClickSleeper()
    )
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: foreground.coordinator,
        clock: FakeAutomationClock()
    )
    await coordinator.start()

    _ = try await coordinator.runCycle()
    #expect(
        try await coordinator.runCycle()
            == .action(.clickOutcomeUncertain)
    )
    #expect(
        await coordinator.state
            == .attention(.actionOutcomeUncertain)
    )
    #expect(try await coordinator.runCycle() == .noAction)
    #expect(foreground.clicker.clickCount == 1)
}

@Test
func taskCancellationAfterRealClickStillLatchesUncertainOutcome() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
    ])
    let sleeper = BlockingPostClickSleeper()
    let foreground = makeRealForegroundAction(sleeper: sleeper)
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: foreground.coordinator,
        clock: FakeAutomationClock()
    )
    await coordinator.start()
    _ = try await coordinator.runCycle()

    let actionCycle = Task {
        try await coordinator.runCycle()
    }
    await sleeper.waitUntilRequested()
    actionCycle.cancel()
    await sleeper.releaseSuccessfully()

    #expect(
        try await actionCycle.value
            == .action(.clickOutcomeUncertain)
    )
    #expect(
        await coordinator.state
            == .attention(.actionOutcomeUncertain)
    )
    #expect(foreground.clicker.clickCount == 1)
}

@Test
func restorationFailurePausesUntilExplicitResume() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: nil,
        restorationFailures: [.pointerRestoreFailed("denied")]
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: .rewardRetry, sequence: 4),
            .make(scene: .rewardRetry, sequence: 5),
            .make(scene: .rewardRetry, sequence: 6),
        ],
        actionResults: [.failure(error), .success]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.restorationFailed)
    )
    #expect(await fixture.coordinator.state == .pausedRestorationFailure)
    #expect(try await fixture.coordinator.runCycle() == .paused)
    #expect(await fixture.actioner.requests.count == 1)

    await fixture.coordinator.resumeAfterRestorationFailure()
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
}

@Test
func restorationFailureRecordsFailureDetailForDiagnostics() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: nil,
        restorationFailures: [.originalApplicationNotFrontmost]
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: .rewardRetry, sequence: 4),
            .make(scene: .rewardRetry, sequence: 5),
            .make(scene: .rewardRetry, sequence: 6),
        ],
        actionResults: [.failure(error)]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.restorationFailed)
    )
    #expect(
        await fixture.coordinator.lastRestorationFailures
            == [.originalApplicationNotFrontmost]
    )
}

@Test
func restorationLatchSurvivesStopAndPausesNextStart() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: nil,
        restorationFailures: [.pointerRestoreFailed("denied")]
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
        ],
        actionResults: [.failure(error)]
    )
    await fixture.coordinator.start()
    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    await fixture.coordinator.stop()
    #expect(await fixture.coordinator.state == .stopped)
    await fixture.coordinator.start()

    #expect(await fixture.coordinator.state == .pausedRestorationFailure)
    #expect(try await fixture.coordinator.runCycle() == .paused)
    #expect(await fixture.actioner.requests.count == 1)
}

@Test
func actionFailureRetriesOnlyAfterExplicitReset() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: .targetNotFrontmost,
        restorationFailures: []
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: .rewardRetry, sequence: 4),
            .make(scene: .rewardRetry, sequence: 5),
            .make(scene: .rewardRetry, sequence: 6),
            .make(scene: .rewardRetry, sequence: 7),
        ],
        actionResults: [.failure(error), .success]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.failedBeforeClick)
    )
    #expect(await fixture.coordinator.state == .attention(.actionFailed))
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.actioner.requests.count == 1)

    await fixture.coordinator.resetForRetry()
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
}

@Test
func changedObservedSceneClearsPriorActionFailureBlock() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: .targetNotFrontmost,
        restorationFailures: []
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: .continueDialog, sequence: 4),
            .make(scene: .continueDialog, sequence: 5),
            .make(scene: .continueDialog, sequence: 6),
        ],
        actionResults: [.failure(error), .success]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.failedBeforeClick)
    )
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .observing(.continueDialog))
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
}

@Test
func unknownTransientDoesNotClearPriorActionFailureBlock() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: .targetNotFrontmost,
        restorationFailures: []
    )
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            .make(scene: nil, sequence: 4),
            .make(scene: .rewardRetry, sequence: 5),
            .make(scene: .rewardRetry, sequence: 6),
        ],
        actionResults: [.failure(error), .success]
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.failedBeforeClick)
    )
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(try await fixture.coordinator.runCycle() == .noAction)

    #expect(await fixture.coordinator.state == .attention(.actionFailed))
    #expect(await fixture.actioner.requests.count == 1)
}

@Test
func unvalidatedContinueTextCannotUnlockFailedRetryScene() async throws {
    let error = ForegroundActionCoordinatorError(
        primaryFailure: .targetNotFrontmost,
        restorationFailures: []
    )
    let lowConfidenceContinue = AutomationScreenFrame.rawText(
        "계속하기",
        confidence: 0.1,
        sequence: 4
    )
    let outOfRegionContinue = AutomationScreenFrame.rawText(
        "계속하기",
        confidence: 0.99,
        sequence: 5,
        rect: CGRect(x: 20, y: 40, width: 40, height: 20)
    )
    let wrongLayoutContinue = AutomationScreenFrame.rawText(
        "계속하기",
        confidence: 0.99,
        sequence: 6,
        layout: .landscape
    )
    let rules = [
        coordinatorRule(id: "reward_retry", targetText: "다시 하기"),
        coordinatorRule(
            id: "continue_dialog",
            targetText: "계속하기",
            region: NormalizedRegion(
                minX: 0,
                minY: 0.7,
                maxX: 1,
                maxY: 1
            )
        ),
    ]
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
            lowConfidenceContinue,
            outOfRegionContinue,
            wrongLayoutContinue,
            .make(scene: .rewardRetry, sequence: 7),
        ],
        actionResults: [.failure(error), .success],
        rules: rules
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    #expect(await fixture.coordinator.state == .attention(.actionFailed))
    #expect(await fixture.actioner.requests.count == 1)
}

@Test
func successfulEnterReadyStartsShortSuppressionThenResumesObserving() async throws {
    // A방식: 입장 후 2초만 억제(중복 입장 방지)하고 관찰을 재개해
    // 던전 길이와 무관하게 결과 화면을 실시간에 가깝게 감지한다.
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .enterReady, sequence: 1),
        .make(scene: .enterReady, sequence: 2),
        .make(scene: .enterReady, sequence: 3),
        .make(scene: .running, sequence: 4),
    ])
    await fixture.coordinator.start()
    await fixture.clock.set(.seconds(10))

    _ = try await fixture.coordinator.runCycle()
    #expect(
        try await fixture.coordinator.runCycle()
            == .action(.clicked)
    )
    #expect(
        await fixture.coordinator.state
            == .cooldown(scene: .running, until: .seconds(12))
    )

    // 억제 2초 동안엔 관찰하지 않는다(중복 입장 방지).
    await fixture.clock.set(.seconds(11))
    #expect(try await fixture.coordinator.runCycle() == .cooldown)
    #expect(await fixture.observerCallCount() == 3)

    // 2초가 지나면 곧바로 관찰을 재개한다.
    await fixture.clock.set(.seconds(12))
    #expect(try await fixture.coordinator.runCycle() == .noAction)
    #expect(await fixture.coordinator.state == .unknown)
}

@Test
func cancellationDuringIdlePropagatesWithoutForcingSemanticProgress() async throws {
    let idle = CancellingIdleMonitor()
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
        ],
        idle: idle
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    await #expect(throws: CancellationError.self) {
        _ = try await fixture.coordinator.runCycle()
    }
    #expect(await fixture.coordinator.state == .observing(.rewardRetry))
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func cancellationDuringObservationPropagatesWithoutChangingState() async throws {
    let observer = CancellingAutomationObserver()
    let fixture = try CoordinatorFixture(observer: observer)
    await fixture.coordinator.start()

    await #expect(throws: CancellationError.self) {
        _ = try await fixture.coordinator.runCycle()
    }

    #expect(await fixture.coordinator.state == .unknown)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func stoppedCoordinatorCannotCompletePendingAction() async throws {
    let idle = SuspendingIdleMonitor()
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
        ],
        idle: idle
    )
    await fixture.coordinator.start()
    _ = try await fixture.coordinator.runCycle()

    let task = Task {
        try await fixture.coordinator.runCycle()
    }
    await idle.waitUntilRequested()
    await fixture.coordinator.stop()
    await idle.release()

    await #expect(throws: CancellationError.self) {
        _ = try await task.value
    }
    #expect(await fixture.coordinator.state == .stopped)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func stopStartDuringObservationInvalidatesOldCycle() async throws {
    let observer = BlockingAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
    ])
    let fixture = try CoordinatorFixture(observer: observer)
    await fixture.coordinator.start()

    let oldCycle = Task {
        try await fixture.coordinator.runCycle()
    }
    await observer.waitUntilRequested()
    await fixture.coordinator.stop()
    await fixture.coordinator.start()
    await observer.release()

    await #expect(throws: CancellationError.self) {
        _ = try await oldCycle.value
    }
    #expect(await fixture.coordinator.state == .unknown)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func stopStartDuringIdleInvalidatesOldCycle() async throws {
    let idle = SuspendingIdleMonitor()
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
        ],
        idle: idle
    )
    await fixture.coordinator.start()
    _ = try await fixture.coordinator.runCycle()

    let oldCycle = Task {
        try await fixture.coordinator.runCycle()
    }
    await idle.waitUntilRequested()
    await fixture.coordinator.stop()
    await fixture.coordinator.start()
    await idle.release()

    await #expect(throws: CancellationError.self) {
        _ = try await oldCycle.value
    }
    #expect(await fixture.coordinator.state == .unknown)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func stoppingDuringActionDoesNotForceCooldownOrSemanticProgress() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .enterReady, sequence: 1),
        .make(scene: .enterReady, sequence: 2),
        .make(scene: .enterReady, sequence: 3),
    ])
    let actioner = SuspendingAutomationActioner()
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: actioner,
        clock: FakeAutomationClock()
    )
    await coordinator.start()
    _ = try await coordinator.runCycle()

    let task = Task {
        try await coordinator.runCycle()
    }
    await actioner.waitUntilRequested()
    await coordinator.stop()
    await actioner.release()

    await #expect(throws: CancellationError.self) {
        _ = try await task.value
    }
    #expect(await coordinator.state == .stopped)
}

@Test
func stopDuringRealPostClickCleanupKeepsStoppedStateAndOneClick() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
    ])
    let sleeper = BlockingPostClickSleeper()
    let foreground = makeRealForegroundAction(sleeper: sleeper)
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: foreground.coordinator,
        clock: FakeAutomationClock()
    )
    await coordinator.start()
    _ = try await coordinator.runCycle()

    let oldCycle = Task {
        try await coordinator.runCycle()
    }
    await sleeper.waitUntilRequested()
    await coordinator.stop()
    await sleeper.releaseWithCancellation()

    await #expect(throws: CancellationError.self) {
        _ = try await oldCycle.value
    }
    #expect(await coordinator.state == .stopped)
    #expect(foreground.clicker.clickCount == 1)
}

@Test
func staleRestorationFailurePausesRestartedRunUntilExplicitResume() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
    ])
    let sleeper = BlockingPostClickSleeper()
    let pointer = CoordinatorPointerController(failOnMoveNumber: 2)
    let foreground = makeRealForegroundAction(
        sleeper: sleeper,
        pointer: pointer
    )
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: foreground.coordinator,
        clock: FakeAutomationClock()
    )
    await coordinator.start()
    _ = try await coordinator.runCycle()

    let staleCycle = Task {
        try await coordinator.runCycle()
    }
    await sleeper.waitUntilRequested()
    await coordinator.stop()
    await coordinator.start()
    await sleeper.releaseWithCancellation()

    #expect(
        try await staleCycle.value
            == .action(.restorationFailed)
    )
    #expect(await coordinator.state == .pausedRestorationFailure)
    #expect(try await coordinator.runCycle() == .paused)
    #expect(foreground.clicker.clickCount == 1)

    await coordinator.resumeAfterRestorationFailure()
    #expect(await coordinator.state == .unknown)
}

@Test
func staleNonRestorationActionErrorCannotOverwriteRestartedRun() async throws {
    let observer = FakeAutomationObserver(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
    ])
    let sleeper = BlockingPostClickSleeper()
    let foreground = makeRealForegroundAction(sleeper: sleeper)
    let coordinator = try AutomationCoordinator(
        rules: coordinatorRules(),
        observer: observer,
        inputMonitor: ImmediateIdleMonitor(),
        actionPerformer: foreground.coordinator,
        clock: FakeAutomationClock()
    )
    await coordinator.start()
    _ = try await coordinator.runCycle()

    let staleCycle = Task {
        try await coordinator.runCycle()
    }
    await sleeper.waitUntilRequested()
    await coordinator.stop()
    await coordinator.start()
    await sleeper.releaseWithCancellation()

    await #expect(throws: CancellationError.self) {
        _ = try await staleCycle.value
    }
    #expect(await coordinator.state == .unknown)
    #expect(foreground.clicker.clickCount == 1)
}

@Test
func concurrentCyclesNeverOverlapOrDuplicateActions() async throws {
    let observer = BlockingAutomationObserver(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
        ]
    )
    let fixture = try CoordinatorFixture(observer: observer)
    await fixture.coordinator.start()

    let first = Task {
        try await fixture.coordinator.runCycle()
    }
    await observer.waitUntilRequested()
    #expect(try await fixture.coordinator.runCycle() == .busy)
    await observer.release()
    #expect(try await first.value == .noAction)
    #expect(await fixture.actioner.requests.isEmpty)
}

@Test
func coordinatorExposesLastObservationDiagnosticsAfterCycle() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .rewardRetry, sequence: 1),
    ])
    await fixture.coordinator.start()
    #expect(await fixture.coordinator.lastObservation == nil)

    _ = try await fixture.coordinator.runCycle()

    let diagnostics = try #require(
        await fixture.coordinator.lastObservation
    )
    #expect(diagnostics.layout == "portrait-mobile")
    #expect(diagnostics.imageWidth == 600)
    #expect(diagnostics.recognizedTexts.map(\.text) == ["다시 하기"])
    #expect(
        diagnostics.actionCandidates.map(\.ruleID) == ["reward_retry"]
    )
}

@Test
func dungeonNameTrackedOnlyFromScreensThatActuallyShowIt() {
    // 실측: 던전 이름('룬다 1층 2구역')은 선택·도전·입장 화면 상단에만
    // 안정적으로 뜬다. clear_touch(던전 클리어 연출)엔 던전 이름이 없어
    // 몬스터명('자이언트 헤드리스')이 오추출되므로 그 화면에선 갱신하지 않는다.
    #expect(AutomationCoordinator.sceneHasDungeonName(.rewardRetry))
    #expect(AutomationCoordinator.sceneHasDungeonName(.missionSelection))
    #expect(AutomationCoordinator.sceneHasDungeonName(.enterReady))
    #expect(!AutomationCoordinator.sceneHasDungeonName(.clearTouch))
    #expect(!AutomationCoordinator.sceneHasDungeonName(.continueDialog))
    #expect(!AutomationCoordinator.sceneHasDungeonName(.running))
}

@Test
func coordinatorRecordsLastClickSceneForActivityLog() async throws {
    let fixture = try CoordinatorFixture(frames: [
        .make(scene: .rewardRetry, sequence: 1),
        .make(scene: .rewardRetry, sequence: 2),
        .make(scene: .rewardRetry, sequence: 3),
    ])
    await fixture.coordinator.start()
    #expect(await fixture.coordinator.lastClick == nil)

    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    let click = try #require(await fixture.coordinator.lastClick)
    #expect(click.ruleID == "reward_retry")
    // fixture 화면엔 던전 이름 텍스트가 없으므로 nil.
    #expect(click.dungeonName == nil)
}

@Test
func coordinatorReportsActionablePhasesInOrder() async throws {
    let recorder = AutomationStatusRecorder()
    let fixture = try CoordinatorFixture(
        frames: [
            .make(scene: .rewardRetry, sequence: 1),
            .make(scene: .rewardRetry, sequence: 2),
            .make(scene: .rewardRetry, sequence: 3),
        ],
        statusReporter: { status in
            await recorder.record(status)
        }
    )
    await fixture.coordinator.start()

    _ = try await fixture.coordinator.runCycle()
    _ = try await fixture.coordinator.runCycle()

    #expect(
        await recorder.statuses
            == [.buttonDetected, .waitingForUserIdle, .clicking]
    )
}

private struct CoordinatorFixture {
    let observer: any AutomationScreenObserving
    let actioner: FakeAutomationActioner
    let clock: FakeAutomationClock
    let coordinator: AutomationCoordinator

    func observerCallCount() async -> Int {
        if let observer = observer as? FakeAutomationObserver {
            return await observer.observeCallCount
        }
        return 0
    }

    init(
        frames: [AutomationScreenFrame],
        actionResults: [FakeAutomationActioner.Result] = [.success],
        idle: any UserIdleMonitoring = ImmediateIdleMonitor(),
        rules: [AutomationRule] = coordinatorRules(),
        statusReporter: (
            @Sendable (AutomationMenuStatus) async -> Void
        )? = nil
    ) throws {
        let observer = FakeAutomationObserver(frames: frames)
        try self.init(
            observer: observer,
            actionResults: actionResults,
            idle: idle,
            rules: rules,
            statusReporter: statusReporter
        )
    }

    init(
        observer: any AutomationScreenObserving,
        actionResults: [FakeAutomationActioner.Result] = [.success],
        idle: any UserIdleMonitoring = ImmediateIdleMonitor(),
        rules: [AutomationRule] = coordinatorRules(),
        statusReporter: (
            @Sendable (AutomationMenuStatus) async -> Void
        )? = nil
    ) throws {
        self.observer = observer
        actioner = FakeAutomationActioner(results: actionResults)
        clock = FakeAutomationClock()
        coordinator = try AutomationCoordinator(
            rules: rules,
            observer: observer,
            inputMonitor: idle,
            actionPerformer: actioner,
            clock: clock,
            statusReporter: statusReporter
        )
    }
}

private actor AutomationStatusRecorder {
    private(set) var statuses: [AutomationMenuStatus] = []

    func record(_ status: AutomationMenuStatus) {
        statuses.append(status)
    }
}

private actor FakeAutomationObserver: AutomationScreenObserving {
    private var frames: [AutomationScreenFrame]
    private(set) var observeCallCount = 0

    init(frames: [AutomationScreenFrame]) {
        self.frames = frames
    }

    func observe() async throws -> AutomationScreenFrame {
        observeCallCount += 1
        return frames.removeFirst()
    }
}

private struct CancellingAutomationObserver: AutomationScreenObserving {
    func observe() async throws -> AutomationScreenFrame {
        throw CancellationError()
    }
}

private actor FakeCoordinatorCaptureService: WindowCapturing {
    private let result: WindowCaptureResult
    private(set) var requestCount = 0

    init(result: WindowCaptureResult) {
        self.result = result
    }

    func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate {
        result.candidate
    }

    func capture(windowID: UInt32) async throws -> CGImage {
        result.image
    }

    func captureWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCaptureResult {
        requestCount += 1
        return result
    }
}

private struct CoordinatorTextRecognizer: TextRecognizing {
    let observations: [RecognizedTextObservation]

    func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation] {
        observations
    }
}

private actor BlockingAutomationObserver: AutomationScreenObserving {
    private var frames: [AutomationScreenFrame]
    private var requested = false
    private var continuation: CheckedContinuation<Void, Never>?

    init(frames: [AutomationScreenFrame]) {
        self.frames = frames
    }

    func observe() async throws -> AutomationScreenFrame {
        requested = true
        await withCheckedContinuation { continuation = $0 }
        return frames.removeFirst()
    }

    func waitUntilRequested() async {
        while !requested {
            await Task.yield()
        }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private actor FakeAutomationActioner: AutomationActionPerforming {
    enum Result: Sendable {
        case success
        case failure(ForegroundActionCoordinatorError)
    }

    struct Request: Equatable, Sendable {
        let targetApplication: ApplicationIdentity
        let targetBox: CGRect
        let expectedInputGeneration: UInt64
    }

    private var results: [Result]
    private(set) var requests: [Request] = []

    init(results: [Result]) {
        self.results = results
    }

    func perform(
        targetApplication: ApplicationIdentity,
        targetBox: CGRect,
        expectedInputGeneration: UInt64
    ) async throws -> ForegroundActionResult {
        requests.append(Request(
            targetApplication: targetApplication,
            targetBox: targetBox,
            expectedInputGeneration: expectedInputGeneration
        ))
        switch results.removeFirst() {
        case .success:
            return ForegroundActionResult(
                originalApplication: targetApplication,
                targetApplication: targetApplication,
                pointerBefore: .zero,
                targetPoint: .zero,
                pointerRestored: .zero,
                expectedInputGeneration: expectedInputGeneration,
                inputGenerationBeforeClick: expectedInputGeneration,
                restoration: .gameWasAlreadyFrontmost
            )
        case let .failure(error):
            throw error
        }
    }
}

private actor SuspendingAutomationActioner: AutomationActionPerforming {
    private var requested = false
    private var continuation: CheckedContinuation<Void, Never>?

    func perform(
        targetApplication: ApplicationIdentity,
        targetBox: CGRect,
        expectedInputGeneration: UInt64
    ) async throws -> ForegroundActionResult {
        requested = true
        await withCheckedContinuation { continuation = $0 }
        return ForegroundActionResult(
            originalApplication: targetApplication,
            targetApplication: targetApplication,
            pointerBefore: .zero,
            targetPoint: .zero,
            pointerRestored: .zero,
            expectedInputGeneration: expectedInputGeneration,
            inputGenerationBeforeClick: expectedInputGeneration,
            restoration: .gameWasAlreadyFrontmost
        )
    }

    func waitUntilRequested() async {
        while !requested {
            await Task.yield()
        }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private struct RealForegroundFixture {
    let coordinator: ForegroundActionCoordinator
    let clicker: CountingCoordinatorClicker
}

private func makeRealForegroundAction(
    sleeper: any ActionSleeping,
    pointer: any PointerControlling = CoordinatorPointerController()
) -> RealForegroundFixture {
    let game = ApplicationIdentity(
        processIdentifier: coordinatorWindow.processID,
        bundleIdentifier: coordinatorWindow.bundleIdentifier
    )
    let original = ApplicationIdentity(
        processIdentifier: 1,
        bundleIdentifier: "com.example.editor"
    )
    let applications = CoordinatorApplicationController(
        frontmost: original,
        running: [original, game]
    )
    let clicker = CountingCoordinatorClicker()
    let coordinator = ForegroundActionCoordinator(
        applications: applications,
        pointer: pointer,
        clicker: clicker,
        sleeper: sleeper,
        inputMonitor: ImmediateIdleMonitor()
    )
    return RealForegroundFixture(
        coordinator: coordinator,
        clicker: clicker
    )
}

private final class CoordinatorApplicationController:
    ApplicationCoordinating,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var current: ApplicationIdentity
    private let running: Set<ApplicationIdentity>

    init(
        frontmost: ApplicationIdentity,
        running: Set<ApplicationIdentity>
    ) {
        current = frontmost
        self.running = running
    }

    func frontmostApplication() -> ApplicationIdentity? {
        lock.withLock { current }
    }

    func activate(_ application: ApplicationIdentity) throws -> Bool {
        lock.withLock {
            current = application
        }
        return true
    }

    func isFrontmost(_ application: ApplicationIdentity) -> Bool {
        lock.withLock { current == application }
    }

    func isRunning(_ application: ApplicationIdentity) -> Bool {
        running.contains(application)
    }
}

private final class CoordinatorPointerController:
    PointerControlling,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var point = CGPoint(x: 10, y: 10)
    private var moveCount = 0
    private let failOnMoveNumber: Int?

    init(failOnMoveNumber: Int? = nil) {
        self.failOnMoveNumber = failOnMoveNumber
    }

    func location() throws -> CGPoint {
        lock.withLock { point }
    }

    func move(
        to point: CGPoint,
        sourceIdentifier: Int64
    ) throws {
        try lock.withLock {
            moveCount += 1
            if moveCount == failOnMoveNumber {
                throw CoordinatorPointerError.restoreFailed
            }
            self.point = point
        }
    }
}

private enum CoordinatorPointerError: Error {
    case restoreFailed
}

private final class CountingCoordinatorClicker:
    GlobalClicking,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var count = 0

    var clickCount: Int {
        lock.withLock { count }
    }

    func click(
        screenPoint: CGPoint,
        sourceIdentifier: Int64
    ) throws {
        lock.withLock {
            count += 1
        }
    }
}

private struct CancellingPostClickSleeper: ActionSleeping {
    func sleep(for duration: Duration) async throws {
        throw CancellationError()
    }
}

private actor BlockingPostClickSleeper: ActionSleeping {
    private var requested = false
    private var continuation:
        CheckedContinuation<Void, any Error>?

    func sleep(for duration: Duration) async throws {
        requested = true
        try await withCheckedThrowingContinuation {
            continuation = $0
        }
    }

    func waitUntilRequested() async {
        while !requested {
            await Task.yield()
        }
    }

    func releaseWithCancellation() {
        continuation?.resume(throwing: CancellationError())
        continuation = nil
    }

    func releaseSuccessfully() {
        continuation?.resume()
        continuation = nil
    }
}

private actor FakeAutomationClock: AutomationClockReading {
    private var current: Duration = .zero

    func now() -> Duration {
        current
    }

    func set(_ value: Duration) {
        current = value
    }
}

private struct ImmediateIdleMonitor: UserIdleMonitoring {
    func snapshot() async -> UserInputSnapshot {
        coordinatorInputSnapshot()
    }

    func waitUntilIdle(for duration: Duration) async throws -> UserInputSnapshot {
        #expect(duration == .seconds(1))
        return coordinatorInputSnapshot()
    }
}

private struct CancellingIdleMonitor: UserIdleMonitoring {
    func snapshot() async -> UserInputSnapshot {
        coordinatorInputSnapshot()
    }

    func waitUntilIdle(for duration: Duration) async throws -> UserInputSnapshot {
        throw CancellationError()
    }
}

private actor SuspendingIdleMonitor: UserIdleMonitoring {
    private var requested = false
    private var continuation: CheckedContinuation<Void, Never>?

    func snapshot() async -> UserInputSnapshot {
        coordinatorInputSnapshot()
    }

    func waitUntilIdle(for duration: Duration) async throws -> UserInputSnapshot {
        requested = true
        await withCheckedContinuation { continuation = $0 }
        return coordinatorInputSnapshot()
    }

    func waitUntilRequested() async {
        while !requested {
            await Task.yield()
        }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private extension AutomationScreenFrame {
    static func rawText(
        _ text: String,
        confidence: Double,
        sequence: UInt64,
        rect: CGRect = CGRect(x: 20, y: 40, width: 40, height: 20),
        layout: LayoutProfile = .portraitMobile
    ) -> Self {
        AutomationScreenFrame(
            observation: SceneObservation(
                captureIdentity: try! CaptureIdentity(
                    sessionID: coordinatorCaptureSession,
                    sequence: sequence
                ),
                imageSize: CGSize(width: 600, height: 900),
                recognizedTexts: [
                    RecognizedTextObservation(
                        text: text,
                        confidence: confidence,
                        boundingBox: rect
                    ),
                ],
                actionCandidates: []
            ),
            window: coordinatorWindow,
            layout: layout
        )
    }

    static func make(
        scene: AutomationScene?,
        sequence: UInt64,
        candidateRuleIDs: [String]? = nil,
        texts: [String]? = nil,
        layout: LayoutProfile = .portraitMobile,
        targetRect: CGRect = CGRect(x: 20, y: 40, width: 40, height: 20),
        window: WindowCandidate = coordinatorWindow
    ) -> Self {
        let ruleIDs = candidateRuleIDs
            ?? scene.flatMap(expectedRuleID).map { [$0] }
            ?? []
        let recognizedTexts = (texts ?? scene.map(defaultTexts) ?? [])
            .enumerated()
            .map { index, text in
                RecognizedTextObservation(
                    text: text,
                    confidence: 0.99,
                    boundingBox: CGRect(
                        x: targetRect.minX,
                        y: targetRect.minY + Double(index * 25),
                        width: targetRect.width,
                        height: targetRect.height
                    )
                )
            }
        let candidates = ruleIDs.compactMap { ruleID in
            if ruleID == "clear_touch" {
                return SceneObserver.actionCandidate(
                    for: coordinatorRule(
                        id: ruleID,
                        requiredTexts: [
                            "던전 클리어",
                            "화면을 터치해주세요",
                        ],
                        targetText: nil
                    ),
                    observations: recognizedTexts,
                    layout: layout,
                    imageSize: CGSize(width: 600, height: 900)
                )
            }
            return SceneActionCandidate(
                ruleID: ruleID,
                targetText: defaultTargetText(for: ruleID),
                boundingBox: targetRect,
                confidence: 0.99
            )
        }
        return AutomationScreenFrame(
            observation: SceneObservation(
                captureIdentity: try! CaptureIdentity(
                    sessionID: coordinatorCaptureSession,
                    sequence: sequence
                ),
                imageSize: CGSize(width: 600, height: 900),
                recognizedTexts: recognizedTexts,
                actionCandidates: candidates
            ),
            window: window,
            layout: layout
        )
    }
}

private let coordinatorCaptureSession = UUID(
    uuidString: "E9703D61-BA0B-44E2-B798-1BA85C8C1E04"
)!

private let coordinatorWindow = WindowCandidate(
    windowID: 42,
    processID: 2468,
    bundleIdentifier: "com.example.game",
    title: "Game",
    frame: CGRect(x: 100, y: 200, width: 600, height: 900),
    isOnScreen: true,
    processLifetimeIdentity: try! ProcessLifetimeIdentity(
        launchTimeIntervalSinceReferenceDate: 123
    )
)

private func coordinatorInputSnapshot() -> UserInputSnapshot {
    UserInputSnapshot(
        generation: 7,
        lastInputAt: ContinuousClock().now
    )
}

private func coordinatorImage(width: Int, height: Int) -> CGImage {
    let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: width * 4,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )
    return context!.makeImage()!
}

private func expectedRuleID(for scene: AutomationScene) -> String? {
    switch scene {
    case .clearTouch:
        "clear_touch"
    case .rewardDetail:
        "reward_detail"
    case .sceneSkip:
        "scene_skip"
    case .rewardRetry:
        "reward_retry"
    case .continueDialog:
        "continue_dialog"
    case .missionSelection:
        "mission_selection"
    case .deselectChallenge:
        "deselect_challenge"
    case .deselectDoubleLoot:
        "deselect_double_loot"
    case .enterReady:
        "enter_ready"
    case .running:
        nil
    }
}

private func defaultTexts(for scene: AutomationScene) -> [String] {
    switch scene {
    case .clearTouch:
        ["던전 클리어", "화면을 터치해주세요"]
    case .rewardDetail:
        ["발견한 전리품"]
    case .sceneSkip:
        ["장면 넘기기"]
    case .rewardRetry:
        ["다시 하기"]
    case .continueDialog:
        ["계속하기"]
    case .missionSelection:
        ["도전"]
    case .deselectChallenge:
        ["선택을 해제하면 임무 없이 입장할 수 있습니다.", "선택됨"]
    case .deselectDoubleLoot:
        ["도전에 성공하면 임무 전리품이 두 배가 됩니다.", "선택됨"]
    case .enterReady:
        ["입장하기"]
    case .running:
        ["던전 진행 중"]
    }
}

private func defaultTargetText(for ruleID: String) -> String? {
    switch ruleID {
    case "clear_touch":
        nil
    case "reward_retry":
        "다시 하기"
    case "continue_dialog":
        "계속하기"
    case "mission_selection":
        "도전"
    case "enter_ready":
        "입장하기"
    default:
        nil
    }
}

private func coordinatorRules() -> [AutomationRule] {
    [
        coordinatorRule(
            id: "clear_touch",
            requiredTexts: ["던전 클리어", "화면을 터치해주세요"],
            targetText: nil
        ),
        coordinatorRule(id: "reward_retry", targetText: "다시 하기"),
        coordinatorRule(id: "continue_dialog", targetText: "계속하기"),
        coordinatorRule(id: "mission_selection", targetText: "도전"),
        coordinatorRule(id: "enter_ready", targetText: "입장하기"),
    ]
}

private func coordinatorRule(
    id: String,
    requiredTexts: [String]? = nil,
    targetText: String?,
    region: NormalizedRegion = NormalizedRegion(
        minX: 0,
        minY: 0,
        maxX: 1,
        maxY: 1
    )
) -> AutomationRule {
    AutomationRule(
        id: id,
        requiredTexts: requiredTexts ?? targetText.map { [$0] } ?? [],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: targetText,
            safePointRegion: targetText == nil
                ? NormalizedRegion(
                    minX: 20.0 / 600.0,
                    minY: 40.0 / 900.0,
                    maxX: 60.0 / 600.0,
                    maxY: 60.0 / 900.0
                )
                : nil
        ),
        regions: LayoutRegionMap([
            .portraitMobile: region,
        ]),
        minimumOCRConfidence: 0.8,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 0.5
    )
}
