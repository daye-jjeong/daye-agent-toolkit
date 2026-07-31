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

/// 한 바퀴가 클릭 없이 끝난 이유.
///
/// '누를 게 없었다'와 '누를 것을 찾고도 못 눌렀다'는 사용자가 손댈 곳이
/// 전혀 다른데, 예전엔 둘 다 그냥 아무 일도 안 한 것으로 끝나 구분이 없었다.
/// 그래서 멈춤 안내가 늘 '누를 버튼을 못 찾았습니다'로 나갔다 — 버튼을
/// 후보로 잡아 둔 채 서 있을 때조차(2026-07-29 실측).
public enum NoActionReason: String, Codable, Equatable, Sendable {
    /// 누를 후보가 아예 없다. 게임이 예상 밖 화면에 있다.
    case noCandidate
    /// 화면을 안전하게 판별하지 못했다(지원 밖 비율·금지어·후보 중복).
    case unsafeFrame
    /// 장면은 알아봤지만 대응하는 규칙이 없다.
    case sceneNotActionable
    /// 장면이 막 바뀌어 잠시 기다리는 중이다. 곧 스스로 풀린다.
    case sceneSettling
    /// 버튼을 봤지만 아직 한 번뿐이라 다음 관찰을 기다린다. 후보는 같은
    /// 자리에서 두 번 보여야 잡힌다. 한 바퀴 스치는 건 정상이지만, 계속
    /// 이 상태면 재확인이 매번 어긋난다는 뜻이라 '누를 게 없다'와 전혀 다르다.
    case awaitingStableCandidate
    /// 후보를 잡아 뒀는데 다음 관찰에서 사라졌다.
    case candidateVanished
    /// 클릭 직전 재확인에서 화면이 다른 장면으로 넘어갔다.
    case sceneChangedBeforeClick
    /// 후보는 그대로인데 재확인에서 유효하지 않다고 판정됐다.
    case revalidationFailed
    /// 재확인에서 다른 규칙의 후보가 올라왔다.
    case candidateChangedBeforeClick
    /// 후보의 화면 좌표를 구하지 못했다(창이 화면 밖으로 나갔을 때).
    case targetOffScreen

    /// 후보를 손에 쥐고도 못 누른 경우인지. 사람이 손댈 곳이 갈린다 —
    /// 앞쪽은 게임 화면을, 뒤쪽은 앱이 왜 주저했는지를 봐야 한다.
    public var heldACandidate: Bool {
        switch self {
        case .noCandidate, .unsafeFrame, .sceneNotActionable, .sceneSettling:
            false
        case .awaitingStableCandidate, .candidateVanished,
             .sceneChangedBeforeClick, .revalidationFailed,
             .candidateChangedBeforeClick, .targetOffScreen:
            true
        }
    }

    public var koreanDescription: String {
        switch self {
        case .noCandidate:
            "누를 버튼을 찾지 못했습니다"
        case .unsafeFrame:
            "화면을 안전하게 판별하지 못했습니다"
        case .sceneNotActionable:
            "이 화면에 맞는 규칙이 없습니다"
        case .sceneSettling:
            "화면이 바뀌어 기다리는 중입니다"
        case .awaitingStableCandidate:
            "버튼을 봤지만 같은 자리에서 다시 확인되지 않았습니다"
        case .candidateVanished:
            "버튼을 찾았지만 누르기 직전에 사라졌습니다"
        case .sceneChangedBeforeClick:
            "버튼을 찾았지만 누르기 직전에 화면이 바뀌었습니다"
        case .revalidationFailed:
            "버튼을 찾았지만 다시 확인할 때 어긋났습니다"
        case .candidateChangedBeforeClick:
            "버튼을 찾았지만 다른 버튼으로 바뀌었습니다"
        case .targetOffScreen:
            "버튼 위치를 화면 좌표로 옮기지 못했습니다"
        }
    }
}

public enum AutomationCoordinatorError: Error, Equatable, Sendable {
    case invalidIdleThreshold
    case invalidClearTouchDelay
    case invalidEnterReadyCooldown
}

/// 오래 멈췄을 때 사용자에게 내보내는 안내 문구.
///
/// 예전엔 사유와 무관하게 늘 '누를 버튼을 못 찾았습니다'로 나갔다. 버튼을
/// 후보로 잡아 둔 채 서 있을 때도 같은 문구라, 게임 화면을 아무리 봐도
/// 멀쩡해서 어디를 손봐야 할지 알 수 없었다(2026-07-29).
public enum QuietStallMessage {
    public static func text(
        seconds: Int,
        reason: NoActionReason?
    ) -> String {
        guard let reason else {
            return "\(seconds)초 넘게 아무 동작도 하지 못했습니다."
                + " 게임 화면을 확인하세요."
        }
        let tail = reason.heldACandidate
            // 게임 화면은 멀쩡하다. 앱이 왜 주저했는지를 봐야 한다.
            ? " 앱 상태를 확인하세요."
            : " 게임 화면을 확인하세요."
        return "\(seconds)초 넘게 진행되지 않았습니다"
            + " — \(reason.koreanDescription)." + tail
    }
}

public actor AutomationCoordinator {
    public struct ClickRecord: Equatable, Sendable {
        public let ruleID: String
        public let dungeonName: String?
        /// 이 클릭에 든 시간을 구간별로 쪼갠 값. 어디가 느린지 짚는 데 쓴다.
        public let phases: ClickPhaseTimings?

        public init(
            ruleID: String,
            dungeonName: String?,
            phases: ClickPhaseTimings? = nil
        ) {
            self.ruleID = ruleID
            self.dungeonName = dungeonName
            self.phases = phases
        }
    }

    public private(set) var state: AutomationState = .stopped
    public private(set) var lastObservation: ObservationDiagnostics?
    public private(set) var lastClick: ClickRecord?
    /// 직전 바퀴가 클릭 없이 끝난 이유. 클릭이 나가면 비운다.
    public private(set) var lastNoActionReason: NoActionReason?
    public private(set) var lastRestorationFailures: [ForegroundRestorationFailure] = []
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
        idleThreshold: Duration = .seconds(1),
        clearTouchDelay: Duration = .seconds(1),
        enterReadyCooldown: Duration = .seconds(2),
        statusReporter: (
            @Sendable (AutomationMenuStatus) async -> Void
        )? = nil
    ) throws {
        guard idleThreshold >= .seconds(1) else {
            throw AutomationCoordinatorError.invalidIdleThreshold
        }
        guard clearTouchDelay >= .seconds(1) else {
            throw AutomationCoordinatorError.invalidClearTouchDelay
        }
        // A방식: 입장 후 2초 억제로 중복 입장만 막고 관찰을 재개한다.
        guard enterReadyCooldown >= .seconds(2) else {
            throw AutomationCoordinatorError.invalidEnterReadyCooldown
        }
        evaluator = try RuleEvaluator(
            rules: rules,
            targetRectangleTolerancePixels:
                Self.targetRectangleTolerancePixels
        )
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
        // 구간별 소요를 재 어디가 느린지 짚는다(관찰·유휴 대기·재관찰·클릭).
        let observeStartedAt = await clock.now()
        let frame = try await observer.observe()
        lastObservation = ObservationDiagnostics(frame: frame)
        try ensureCanContinue(token: cycleToken)
        let now = await clock.now()
        let observeDuration = now - observeStartedAt
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
            // adopt가 막은 경우와 후보가 아예 없는 경우를 가른다. 앞은 앱이
            // 안전을 위해 물러선 것이고, 뒤는 게임이 예상 밖 화면에 있다.
            return noAction(
                validatedCandidate == nil ? .noCandidate : .unsafeFrame
            )
        }
        updateLastSeenDungeonName(from: frame, scene: scene)
        guard Self.expectedRuleID(for: scene) != nil else {
            return noAction(.sceneNotActionable)
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
                return abortBeforeClick(.revalidationFailed)
            }
        }

        guard let pendingCandidate else {
            return noAction(.awaitingStableCandidate)
        }
        if scene == .clearTouch,
           let sceneFirstRecognizedAt,
           now - sceneFirstRecognizedAt < clearTouchDelay
        {
            return noAction(.sceneSettling)
        }

        await statusReporter?(.buttonDetected)
        await statusReporter?(.waitingForUserIdle)
        let idleStartedAt = await clock.now()
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
        let reobserveStartedAt = await clock.now()
        let idleWaitDuration = reobserveStartedAt - idleStartedAt

        let freshFrame = try await observer.observe()
        lastObservation = ObservationDiagnostics(frame: freshFrame)
        try ensureCanContinue(token: cycleToken)
        let freshNow = await clock.now()
        let reobserveDuration = freshNow - reobserveStartedAt
        try ensureCanContinue(token: cycleToken)
        let freshValidatedCandidate = evaluator.validatedCandidate(
            observation: freshFrame.observation,
            windowIdentity: freshFrame.window,
            layout: freshFrame.layout
        )
        // 조건을 하나씩 끊어 본다. 한 덩어리로 묶으면 어디서 떨어졌는지
        // 알 수 없어, 클릭이 안 나갈 때마다 추측으로 진단하게 된다.
        guard let freshScene = adopt(
            frame: freshFrame,
            validatedCandidate: freshValidatedCandidate,
            at: freshNow
        ) else {
            return abortBeforeClick(.candidateVanished)
        }
        guard freshScene == scene else {
            return abortBeforeClick(.sceneChangedBeforeClick)
        }
        guard evaluator.revalidate(
            pendingCandidate,
            freshObservation: freshFrame.observation,
            windowIdentity: freshFrame.window,
            layout: freshFrame.layout
        ) else {
            return abortBeforeClick(.revalidationFailed)
        }
        guard
            let freshTarget = freshFrame.observation.actionCandidates.first,
            freshTarget.ruleID == pendingCandidate.ruleID
        else {
            return abortBeforeClick(.candidateChangedBeforeClick)
        }
        guard
            let imageSize = freshFrame.observation.imageSize,
            let screenTargetBox = Self.screenTargetBox(
                pixelRect: freshTarget.boundingBox,
                imageSize: imageSize,
                windowFrame: freshFrame.window.frame
            )
        else {
            return abortBeforeClick(.targetOffScreen)
        }

        let targetApplication = ApplicationIdentity(
            processIdentifier: freshFrame.window.processID,
            bundleIdentifier: freshFrame.window.bundleIdentifier
        )
        do {
            try ensureCanContinue(token: cycleToken)
            await statusReporter?(.clicking)
            try ensureCanContinue(token: cycleToken)
            let clickStartedAt = await clock.now()
            _ = try await actionPerformer.perform(
                targetApplication: targetApplication,
                targetBox: screenTargetBox,
                expectedInputGeneration: idleSnapshot.generation
            )
            try ensureCanContinue(token: cycleToken)
            let clickFinishedAt = await clock.now()
            self.pendingCandidate = nil
            // 클릭이 나갔으니 못 누른 이유는 지운다. 남겨 두면 다음 멈춤
            // 때 지난 사유를 지금 원인으로 오독한다.
            lastNoActionReason = nil
            lastClick = ClickRecord(
                ruleID: Self.expectedRuleID(for: scene) ?? "",
                dungeonName: lastSeenDungeonName,
                phases: ClickPhaseTimings(
                    observe: observeDuration,
                    idleWait: idleWaitDuration,
                    reobserve: reobserveDuration,
                    click: clickFinishedAt - clickStartedAt
                )
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
                lastRestorationFailures = error.restorationFailures
                latchRestorationFailure()
                return .action(.restorationFailed)
            }
            try ensureCurrentRun(token: cycleToken)
            return handleActionError(error, scene: scene)
        }
    }
}

extension AutomationCoordinator {
    /// 버튼이 프레임 간 이동해도 '같은 버튼'으로 인정하는 최대 px
    /// (x·y·폭·높이 각각 독립 적용). 안정 관찰·재확인의 위치 비교 기준.
    ///
    /// 실측(2026-07-24): 보상화면 '다시 하기'는 전리품 연출로 y축 ~36px
    /// 출렁이고 프레임 간 최대 35px 점프한다. 기존 2px면 매 프레임 다른
    /// 위치로 판정돼 애니메이션 내내 안정·재확인이 실패, 클릭이 3~14초
    /// 지연됐다. 다음 버튼까지 202px 떨어져 있어 50px는 오탐 없이 출렁임만
    /// 흡수한다. 클릭은 항상 최신 박스를 쓰므로 관용도를 넓혀도 위치
    /// 정확도는 유지된다(안정 '판정'만 완화, 클릭 '좌표'는 최신).
    static let targetRectangleTolerancePixels: Double = 50

    /// 던전 이름이 화면에 실제로 표시되는 장면인지.
    /// clear_touch(던전 클리어 연출)·running·continue_dialog엔 던전 이름이
    /// 없으므로 이 화면에서 뽑은 텍스트는 던전 이름으로 신뢰하지 않는다.
    static func sceneHasDungeonName(_ scene: AutomationScene) -> Bool {
        switch scene {
        // 공물 규칙은 은동전 짝과 같은 화면에 서므로 판정도 같이 간다.
        case .rewardRetry, .missionSelection, .enterReady, .rewardDetail,
             .enterWithCoin, .enterWithTribute:
            true
        // 퀘스트 보상 화면에 뜨는 굵은 글씨는 퀘스트 이름이지 던전 이름이
        // 아니다('모험가 길드의 고난도 심층 공략'). 그대로 믿으면 다음
        // 판이 엉뚱한 이름으로 기록된다.
        case .clearTouch, .continueDialog, .running, .deselectChallenge,
             .deselectCoin, .turnOffDoubleLoot, .sceneSkip, .autoStart,
             .deselectTribute, .questClearConfirm:
            false
        }
    }

    static func expectedRuleID(
        for scene: AutomationScene
    ) -> String? {
        switch scene {
        case .autoStart:
            "auto_start"
        case .clearTouch:
            "clear_touch"
        case .rewardDetail:
            "reward_detail"
        case .sceneSkip:
            AutomationScene.sceneSkipRuleID
        case .rewardRetry:
            "reward_retry"
        case .continueDialog:
            "continue_dialog"
        case .questClearConfirm:
            "quest_clear_confirm"
        case .missionSelection:
            "mission_selection"
        case .deselectChallenge:
            "deselect_challenge"
        case .turnOffDoubleLoot:
            "turn_off_double_loot"
        case .deselectCoin:
            "deselect_coin"
        case .enterWithCoin:
            "enter_with_coin"
        case .deselectTribute:
            "deselect_tribute"
        case .enterWithTribute:
            "enter_with_tribute"
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

    /// 장면 넘기기(컷신)가 화면에 떠도 자동화를 얼릴지 판단한다.
    /// scene_skip 후보가 이 화면의 지정 핸들러면(빈 공간 탭으로 컷신을
    /// 넘김) 얼리지 않고 진행한다. 그 외 규칙엔 종전대로 forbidden freeze.
    static func shouldFreezeForForbiddenContent(
        _ observation: SceneObservation
    ) -> Bool {
        guard containsForbiddenText(observation) else {
            return false
        }
        let handledBySceneSkip = observation.actionCandidates.contains {
            scene(forRuleID: $0.ruleID) == .sceneSkip
        }
        return !handledBySceneSkip
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
        if Self.shouldFreezeForForbiddenContent(frame.observation) {
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

    /// 클릭 없이 한 바퀴를 끝낸다. 이유를 남기는 것이 이 함수의 전부다.
    func noAction(_ reason: NoActionReason) -> AutomationCycleResult {
        lastNoActionReason = reason
        return .noAction
    }

    /// 후보를 쥐고 있다가 클릭 직전에 접는다. 쥔 후보를 놓지 않으면
    /// 다음 바퀴가 낡은 좌표를 그대로 눌러 엉뚱한 데를 찍는다.
    func abortBeforeClick(
        _ reason: NoActionReason
    ) -> AutomationCycleResult {
        pendingCandidate = nil
        evaluator.resetForRetry()
        return noAction(reason)
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
