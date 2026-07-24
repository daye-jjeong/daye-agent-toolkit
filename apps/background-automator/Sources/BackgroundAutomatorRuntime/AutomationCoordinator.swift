import BackgroundAutomatorCore
@preconcurrency import CoreGraphics
import Foundation

public struct AutomationScreenFrame: Sendable {
    public let observation: SceneObservation
    public let window: WindowCandidate
    public let layout: LayoutProfile

    public init(
        observation: SceneObservation,
        window: WindowCandidate,
        layout: LayoutProfile
    ) {
        self.observation = observation
        self.window = window
        self.layout = layout
    }
}

public protocol AutomationScreenObserving: Sendable {
    func observe() async throws -> AutomationScreenFrame
}

public struct CapturedWindowSceneObserver: AutomationScreenObserving {
    private let captureService: any WindowCapturing
    private let sceneObserver: SceneObserver
    private let rules: [AutomationRule]
    private let bundleIdentifier: String
    private let titleContains: String

    public init(
        captureService: any WindowCapturing,
        sceneObserver: SceneObserver,
        rules: [AutomationRule],
        bundleIdentifier: String,
        titleContains: String
    ) {
        self.captureService = captureService
        self.sceneObserver = sceneObserver
        self.rules = rules
        self.bundleIdentifier = bundleIdentifier
        self.titleContains = titleContains
    }

    public func observe() async throws -> AutomationScreenFrame {
        let capture = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        let layout = LayoutClassifier.classify(
            imageSize: CGSize(
                width: capture.image.width,
                height: capture.image.height
            )
        )
        let observation = try await sceneObserver.observe(
            capture: capture,
            layout: layout,
            rules: rules
        )
        return AutomationScreenFrame(
            observation: observation,
            window: capture.candidate,
            layout: layout
        )
    }
}

public protocol AutomationActionPerforming: Sendable {
    func perform(
        targetApplication: ApplicationIdentity,
        targetBox: CGRect,
        expectedInputGeneration: UInt64
    ) async throws -> ForegroundActionResult
}

extension ForegroundActionCoordinator: AutomationActionPerforming {}

public protocol AutomationClockReading: Sendable {
    func now() async -> Duration
}

public struct ContinuousAutomationClock: AutomationClockReading {
    private let origin: ContinuousClock.Instant
    private let clock: ContinuousClock

    public init() {
        let clock = ContinuousClock()
        self.clock = clock
        origin = clock.now
    }

    public func now() async -> Duration {
        origin.duration(to: clock.now)
    }
}

public enum AutomationActionOutcome: Equatable, Sendable {
    case clicked
    case cancelled
    case failedBeforeClick
    case clickOutcomeUncertain
    case restorationFailed
}

public enum AutomationCycleResult: Equatable, Sendable {
    case noAction
    case action(AutomationActionOutcome)
    case cooldown
    case paused
    case busy
}

public enum AutomationCoordinatorError: Error, Equatable, Sendable {
    case invalidIdleThreshold
    case invalidClearTouchDelay
    case invalidEnterReadyCooldown
}

public actor AutomationCoordinator {
    public struct ClickRecord: Equatable, Sendable {
        public let ruleID: String
        public let dungeonName: String?

        public init(ruleID: String, dungeonName: String?) {
            self.ruleID = ruleID
            self.dungeonName = dungeonName
        }
    }

    public private(set) var state: AutomationState = .stopped
    public private(set) var lastObservation: ObservationDiagnostics?
    public private(set) var lastClick: ClickRecord?
    private var lastSeenDungeonName: String?

    private let observer: any AutomationScreenObserving
    private let inputMonitor: any UserIdleMonitoring
    private let actionPerformer: any AutomationActionPerforming
    private let clock: any AutomationClockReading
    private let idleThreshold: Duration
    private let clearTouchDelay: Duration
    private let enterReadyCooldown: Duration
    private let statusReporter: (
        @Sendable (AutomationMenuStatus) async -> Void
    )?

    private var evaluator: RuleEvaluator
    private var runToken: UUID?
    private var cycleInProgress = false
    private var currentScene: AutomationScene?
    private var sceneFirstRecognizedAt: Duration?
    private var pendingCandidate: ActionCandidate?
    private var blockedScene: AutomationScene?
    private var blockedAttention: AutomationAttention?
    private var restorationFailureLatched = false

    public init(
        rules: [AutomationRule],
        observer: any AutomationScreenObserving,
        inputMonitor: any UserIdleMonitoring,
        actionPerformer: any AutomationActionPerforming,
        clock: any AutomationClockReading = ContinuousAutomationClock(),
        idleThreshold: Duration = .seconds(3),
        clearTouchDelay: Duration = .seconds(2),
        enterReadyCooldown: Duration = .seconds(5),
        statusReporter: (
            @Sendable (AutomationMenuStatus) async -> Void
        )? = nil
    ) throws {
        guard idleThreshold >= .seconds(3) else {
            throw AutomationCoordinatorError.invalidIdleThreshold
        }
        guard clearTouchDelay >= .seconds(2) else {
            throw AutomationCoordinatorError.invalidClearTouchDelay
        }
        // A방식: 입장 후 5초 억제로 중복 입장만 막고 관찰을 재개한다.
        guard enterReadyCooldown >= .seconds(5) else {
            throw AutomationCoordinatorError.invalidEnterReadyCooldown
        }
        evaluator = try RuleEvaluator(rules: rules)
        self.observer = observer
        self.inputMonitor = inputMonitor
        self.actionPerformer = actionPerformer
        self.clock = clock
        self.idleThreshold = idleThreshold
        self.clearTouchDelay = clearTouchDelay
        self.enterReadyCooldown = enterReadyCooldown
        self.statusReporter = statusReporter
    }

    public func start() {
        runToken = UUID()
        if restorationFailureLatched {
            state = .pausedRestorationFailure
        } else if state == .stopped {
            state = .unknown
        }
    }

    public func stop() {
        runToken = nil
        currentScene = nil
        sceneFirstRecognizedAt = nil
        pendingCandidate = nil
        blockedScene = nil
        blockedAttention = nil
        evaluator.resetForRetry()
        state = .stopped
    }

    public func resetForRetry() {
        guard
            runToken != nil,
            !restorationFailureLatched,
            state != .pausedRestorationFailure
        else {
            return
        }
        pendingCandidate = nil
        blockedScene = nil
        blockedAttention = nil
        evaluator.resetForRetry()
        if let currentScene {
            state = .observing(currentScene)
        } else {
            state = .unknown
        }
    }

    public func resumeAfterRestorationFailure() {
        guard runToken != nil, restorationFailureLatched else {
            return
        }
        restorationFailureLatched = false
        pendingCandidate = nil
        blockedScene = nil
        blockedAttention = nil
        evaluator.resetForRetry()
        if let currentScene {
            state = .observing(currentScene)
        } else {
            state = .unknown
        }
    }

    public func runCycle() async throws -> AutomationCycleResult {
        guard let cycleToken = runToken else {
            return .paused
        }
        guard
            !restorationFailureLatched,
            state != .pausedRestorationFailure
        else {
            return .paused
        }
        guard !cycleInProgress else {
            return .busy
        }

        cycleInProgress = true
        defer {
            cycleInProgress = false
        }

        if case let .cooldown(_, until) = state {
            let now = await clock.now()
            try ensureCanContinue(token: cycleToken)
            guard now >= until else {
                return .cooldown
            }
        }

        try ensureCanContinue(token: cycleToken)
        let frame = try await observer.observe()
        lastObservation = ObservationDiagnostics(frame: frame)
        try ensureCanContinue(token: cycleToken)
        let now = await clock.now()
        try ensureCanContinue(token: cycleToken)

        let validatedCandidate = evaluator.validatedCandidate(
            observation: frame.observation,
            windowIdentity: frame.window,
            layout: frame.layout
        )
        guard let scene = adopt(
            frame: frame,
            validatedCandidate: validatedCandidate,
            at: now
        ) else {
            return .noAction
        }
        updateLastSeenDungeonName(from: frame, scene: scene)
        guard Self.expectedRuleID(for: scene) != nil else {
            return .noAction
        }

        let existingPending = pendingCandidate
        let candidate = evaluator.evaluate(
            observation: frame.observation,
            windowIdentity: frame.window,
            layout: frame.layout
        )
        if let candidate {
            pendingCandidate = candidate
        } else if let existingPending {
            guard evaluator.revalidate(
                existingPending,
                freshObservation: frame.observation,
                windowIdentity: frame.window,
                layout: frame.layout
            ) else {
                pendingCandidate = nil
                evaluator.resetForRetry()
                return .noAction
            }
        }

        guard let pendingCandidate else {
            return .noAction
        }
        if scene == .clearTouch,
           let sceneFirstRecognizedAt,
           now - sceneFirstRecognizedAt < clearTouchDelay
        {
            return .noAction
        }

        await statusReporter?(.buttonDetected)
        await statusReporter?(.waitingForUserIdle)
        let idleSnapshot: UserInputSnapshot
        do {
            idleSnapshot = try await inputMonitor.waitUntilIdle(
                for: idleThreshold
            )
        } catch is CancellationError {
            rearmAfterCancellation(token: cycleToken)
            throw CancellationError()
        }
        try ensureCanContinue(token: cycleToken)

        let freshFrame = try await observer.observe()
        lastObservation = ObservationDiagnostics(frame: freshFrame)
        try ensureCanContinue(token: cycleToken)
        let freshNow = await clock.now()
        try ensureCanContinue(token: cycleToken)
        let freshValidatedCandidate = evaluator.validatedCandidate(
            observation: freshFrame.observation,
            windowIdentity: freshFrame.window,
            layout: freshFrame.layout
        )
        guard
            let freshScene = adopt(
                frame: freshFrame,
                validatedCandidate: freshValidatedCandidate,
                at: freshNow
            ),
            freshScene == scene,
            evaluator.revalidate(
                pendingCandidate,
                freshObservation: freshFrame.observation,
                windowIdentity: freshFrame.window,
                layout: freshFrame.layout
            ),
            let freshTarget =
                freshFrame.observation.actionCandidates.first,
            freshTarget.ruleID == pendingCandidate.ruleID,
            let imageSize = freshFrame.observation.imageSize,
            let screenTargetBox = Self.screenTargetBox(
                pixelRect: freshTarget.boundingBox,
                imageSize: imageSize,
                windowFrame: freshFrame.window.frame
            )
        else {
            self.pendingCandidate = nil
            evaluator.resetForRetry()
            return .noAction
        }

        let targetApplication = ApplicationIdentity(
            processIdentifier: freshFrame.window.processID,
            bundleIdentifier: freshFrame.window.bundleIdentifier
        )
        do {
            try ensureCanContinue(token: cycleToken)
            await statusReporter?(.clicking)
            try ensureCanContinue(token: cycleToken)
            _ = try await actionPerformer.perform(
                targetApplication: targetApplication,
                targetBox: screenTargetBox,
                expectedInputGeneration: idleSnapshot.generation
            )
            try ensureCanContinue(token: cycleToken)
            self.pendingCandidate = nil
            lastClick = ClickRecord(
                ruleID: Self.expectedRuleID(for: scene) ?? "",
                dungeonName: lastSeenDungeonName
            )
            if scene == .enterReady {
                let cooldownStart = await clock.now()
                try ensureCanContinue(token: cycleToken)
                state = .cooldown(
                    scene: .running,
                    until: cooldownStart + enterReadyCooldown
                )
            }
            return .action(.clicked)
        } catch is CancellationError {
            rearmAfterCancellation(token: cycleToken)
            throw CancellationError()
        } catch let error as ForegroundActionCoordinatorError {
            if !error.restorationFailures.isEmpty {
                latchRestorationFailure()
                return .action(.restorationFailed)
            }
            try ensureCurrentRun(token: cycleToken)
            return handleActionError(error, scene: scene)
        }
    }
}

extension AutomationCoordinator {
    /// 던전 이름이 화면에 실제로 표시되는 장면인지.
    /// clear_touch(던전 클리어 연출)·running·continue_dialog엔 던전 이름이
    /// 없으므로 이 화면에서 뽑은 텍스트는 던전 이름으로 신뢰하지 않는다.
    static func sceneHasDungeonName(_ scene: AutomationScene) -> Bool {
        switch scene {
        case .rewardRetry, .missionSelection, .enterReady:
            true
        case .clearTouch, .continueDialog, .running:
            false
        }
    }
}

private extension AutomationCoordinator {
    func updateLastSeenDungeonName(
        from frame: AutomationScreenFrame,
        scene: AutomationScene
    ) {
        guard
            Self.sceneHasDungeonName(scene),
            let size = frame.observation.imageSize
        else {
            return
        }
        if let name = DungeonNameExtractor.extract(
            from: frame.observation.recognizedTexts,
            imageSize: size
        ) {
            lastSeenDungeonName = name
        }
    }

    func adopt(
        frame: AutomationScreenFrame,
        validatedCandidate: ActionCandidate?,
        at now: Duration
    ) -> AutomationScene? {
        if frame.layout == .unsupported {
            recordUnsafeState(.unsupportedLayout)
            return nil
        }
        if Self.containsForbiddenText(frame.observation) {
            recordUnsafeState(.forbiddenContent)
            return nil
        }
        if frame.observation.actionCandidates.count > 1 {
            recordUnsafeState(.ambiguousObservation)
            return nil
        }
        guard
            let validatedCandidate,
            let scene = Self.scene(forRuleID: validatedCandidate.ruleID)
        else {
            currentScene = nil
            sceneFirstRecognizedAt = nil
            pendingCandidate = nil
            evaluator.resetForRetry()
            state = .unknown
            return nil
        }

        if scene != currentScene {
            currentScene = scene
            sceneFirstRecognizedAt = now
            pendingCandidate = nil
            if blockedScene != scene {
                blockedScene = nil
                blockedAttention = nil
            }
            evaluator.resetForRetry()
        }
        if blockedScene == scene, let blockedAttention {
            state = .attention(blockedAttention)
            return nil
        }
        state = .observing(scene)

        let expectedRuleID = Self.expectedRuleID(for: scene)
        let observedRuleID = frame.observation.actionCandidates.first?.ruleID
        if let observedRuleID, observedRuleID != expectedRuleID {
            recordUnsafeState(.sceneRuleMismatch, preserving: scene)
            return nil
        }
        return scene
    }

    func recordUnsafeState(
        _ attention: AutomationAttention,
        preserving scene: AutomationScene? = nil
    ) {
        if let scene {
            currentScene = scene
        } else {
            currentScene = nil
            sceneFirstRecognizedAt = nil
        }
        pendingCandidate = nil
        evaluator.resetForRetry()
        state = .attention(attention)
    }

    func rearmAfterCancellation(token: UUID) {
        guard runToken == token else {
            return
        }
        pendingCandidate = nil
        evaluator.resetForRetry()
        if let currentScene {
            state = .observing(currentScene)
        }
    }

    func handleActionError(
        _ error: ForegroundActionCoordinatorError,
        scene: AutomationScene
    ) -> AutomationCycleResult {
        pendingCandidate = nil
        if !error.restorationFailures.isEmpty {
            latchRestorationFailure()
            return .action(.restorationFailed)
        }
        switch error.primaryFailure {
        case .cancelled, .inputGenerationChanged:
            evaluator.resetForRetry()
            state = .observing(scene)
            return .action(.cancelled)
        case .cancelledAfterClick, .postActionWaitFailed:
            blockedScene = scene
            blockedAttention = .actionOutcomeUncertain
            state = .attention(.actionOutcomeUncertain)
            return .action(.clickOutcomeUncertain)
        default:
            blockedScene = scene
            blockedAttention = .actionFailed
            state = .attention(.actionFailed)
            return .action(.failedBeforeClick)
        }
    }

    func latchRestorationFailure() {
        restorationFailureLatched = true
        guard runToken != nil else {
            return
        }
        state = .pausedRestorationFailure
    }

    func ensureCanContinue(token: UUID) throws {
        try Task.checkCancellation()
        try ensureCurrentRun(token: token)
    }

    func ensureCurrentRun(token: UUID) throws {
        guard runToken == token else {
            throw CancellationError()
        }
    }

    static func expectedRuleID(
        for scene: AutomationScene
    ) -> String? {
        switch scene {
        case .clearTouch:
            "clear_touch"
        case .rewardRetry:
            "reward_retry"
        case .continueDialog:
            "continue_dialog"
        case .missionSelection:
            "mission_selection"
        case .enterReady:
            "enter_ready"
        case .running:
            nil
        }
    }

    static func scene(forRuleID ruleID: String) -> AutomationScene? {
        AutomationScene.allCases.first {
            expectedRuleID(for: $0) == ruleID
        }
    }

    static func containsForbiddenText(
        _ observation: SceneObservation
    ) -> Bool {
        observation.recognizedTexts.contains {
            SceneFingerprint.normalize($0.text) == "장면넘기기"
        }
    }

    static func screenTargetBox(
        pixelRect: CGRect,
        imageSize: CGSize,
        windowFrame: CGRect
    ) -> CGRect? {
        guard
            imageSize.width.isFinite,
            imageSize.height.isFinite,
            imageSize.width > 0,
            imageSize.height > 0,
            ActionCandidate.isValid(pixelRect),
            windowFrame.origin.x.isFinite,
            windowFrame.origin.y.isFinite,
            windowFrame.width.isFinite,
            windowFrame.height.isFinite,
            windowFrame.width > 0,
            windowFrame.height > 0
        else {
            return nil
        }
        let scaleX = windowFrame.width / imageSize.width
        let scaleY = windowFrame.height / imageSize.height
        return CGRect(
            x: windowFrame.minX + pixelRect.minX * scaleX,
            y: windowFrame.minY + pixelRect.minY * scaleY,
            width: pixelRect.width * scaleX,
            height: pixelRect.height * scaleY
        )
    }
}
