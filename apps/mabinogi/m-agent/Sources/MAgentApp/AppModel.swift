import AppKit
import MAgentCore
import MAgentRuntime
import Combine
import Foundation
import os

@MainActor
final class AppModel: ObservableObject {
    @Published var bundleIdentifier: String
    @Published var titleContains: String
    /// 임무를 그대로 두고 들어가 임무 보상을 받을지(은동전 10개 소모).
    /// 끄면 임무를 해제하고 들어가 은동전을 아낀다.
    @Published var usesSilverCoin: Bool {
        didSet {
            defaults.set(usesSilverCoin, forKey: Self.usesSilverCoinKey)
        }
    }
    /// 공물 던전(페카 고분)에서 같은 선택. 한 판에 공물 1개다.
    @Published var usesTribute: Bool {
        didSet {
            defaults.set(usesTribute, forKey: Self.usesTributeKey)
        }
    }
    @Published private(set) var status: AutomationMenuStatus = .stopped {
        didSet {
            writeDiagnostics()
        }
    }
    @Published private(set) var lastActionDescription = "없음"
    @Published private(set) var lastActionAt: Date?
    @Published private(set) var activitySummary = ActivitySummary(
        totalClicks: 0,
        dungeonRuns: 0,
        byDungeon: [:]
    )
    @Published private(set) var cycleSummary = CycleSummary(
        totalCycles: 0,
        byDungeon: [:]
    )
    /// 플랫폼 상태 — 시세 수집기(launchd) heartbeat. 메뉴 열 때 갱신한다.
    @Published private(set) var collectorStatus: PlatformStatusRow?

    /// 결과 화면이 떠 있는 5~8초 동안 전리품이 차례로 채워진다. 2초로
    /// 보면 3~4번뿐이라 그 사이에 들어온 항목을 놓쳤다 — 실측 248판에서
    /// '확정' 라벨이 붙은 보상마저 92~95%만 잡혔다(100%여야 한다).
    /// 1.2초로 좁혀 관찰을 1.7배로 늘린다. 늘어난 OCR 부담은 클릭 루프의
    /// 관찰을 3회에서 2회로 줄여(stableObservationCount 1) 상쇄한다.
    static let cycleObservationInterval = Duration.milliseconds(1200)
    /// 폴링 간격을 기준값 둘레로 흩뿌린다. 평균은 그대로라 느려지지 않는다.
    static let pollingJitter = TimingJitter()

    private let defaults: UserDefaults
    private let captureService: WindowCaptureService
    private let preflightService: PreflightService
    private let diagnosticsWriter: DiagnosticsFileWriter?
    private let activityWriter: ActivityLogWriter?
    private let cycleWriter: CycleLogWriter?
    private let stallRecorder: StallSnapshotRecorder?
    private let stallImageWriter: StallImageWriter?
    private let retryPolicy = AutomationRetryPolicy()
    private let clock = ContinuousClock()
    /// 직전에 앱이 누른 입장 방식. 다음 사이클 기록에 한 번 쓰고 비운다.
    private var lastEntry: DungeonEntry?
    private static let logger = Logger(
        subsystem: "MAgent",
        category: "automation"
    )
    private var lastPreflightDiagnostics: PreflightDiagnostics?
    private var lastObservationDiagnostics: ObservationDiagnostics?
    /// 직전 바퀴가 클릭 없이 끝난 이유. 멈춤 안내와 진단 파일에 함께 싣는다.
    private var lastNoActionReason: NoActionReason?
    /// 화면이 흐르는지 본다. 클릭이 없어도 화면이 바뀌면 멈춘 게 아니다.
    private var screenActivity = ScreenActivityTracker()

    private var lifecycleGate = AutomationLifecycleGate()
    private var startPending = false
    private var operationTask: Task<Void, Never>?
    private var loopTask: Task<Void, Never>?
    /// 클릭 루프와 분리된 읽기 전용 관찰 루프. 사용자가 중간에 직접
    /// 버튼을 눌러 넘긴 사이클도 놓치지 않으려면 클릭 여부와 무관하게
    /// 화면을 계속 봐야 한다.
    private var cycleTask: Task<Void, Never>?
    private var coordinator: AutomationCoordinator?
    private var idleMonitor: UserIdleMonitor?
    private var lastPreflightIssue: PreflightIssue?
    /// 아무 버튼도 못 찾는 침묵이 길어지면 멈춤으로 본다.
    private var quietDetector = QuietStallDetector()
    private var quietStallGuidance: String?
    /// 감지기는 경과 시간(Duration)으로 판단하므로 기준 시점을 잡아 둔다.
    private var quietClockOrigin = ContinuousClock.now
    /// 이번에 돌리기 시작한 시각. 정지하면 비운다.
    @Published private(set) var runningSince: Date?
    private var cyclesAtStart = 0

    /// "3시간 12분" 꼴. 돌리는 중이 아니면 nil.
    var uptimeDescription: String? {
        guard let runningSince else {
            return nil
        }
        let elapsed = Date().timeIntervalSince(runningSince)
        let minutes = max(0, Int(elapsed / 60))
        guard minutes >= 60 else {
            return "\(minutes)분"
        }
        return "\(minutes / 60)시간 \(minutes % 60)분"
    }

    /// 이번 세션의 시간당 판 수. 10분은 돌아야 의미가 있다.
    var cycleRateDescription: String? {
        guard let runningSince else {
            return nil
        }
        let hours = Date().timeIntervalSince(runningSince) / 3600
        guard hours >= 10.0 / 60 else {
            return nil
        }
        let cycles = cycleSummary.totalCycles - cyclesAtStart
        return String(format: "시간당 %.1f판", Double(cycles) / hours)
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        bundleIdentifier = defaults.string(
            forKey: Self.bundleIdentifierKey
        ) ?? ""
        usesSilverCoin = defaults.bool(forKey: Self.usesSilverCoinKey)
        usesTribute = defaults.bool(forKey: Self.usesTributeKey)
        titleContains = defaults.string(
            forKey: Self.titleContainsKey
        ) ?? ""

        let captureService = WindowCaptureService()
        self.captureService = captureService
        preflightService = PreflightService(
            permissions: PermissionService(),
            environment: ProductionPreflightEnvironment(
                captureService: captureService
            )
        )
        let directory = Self.diagnosticsDirectory()
        diagnosticsWriter = directory.map {
            DiagnosticsFileWriter(directory: $0)
        }
        // 기록마다 어느 빌드가 남겼는지 찍어 둔다. 배포 전후 비교를 시각으로
        // 자르면, 빌드했지만 앱을 다시 켜지 않은 구간이 새 빌드로 잘못 잡힌다.
        let build = BuildIdentity.current()
        if let directory {
            _ = try? BuildLogWriter(directory: directory)
                .recordIfNeeded(build)
        }
        let activityWriter = directory.map {
            ActivityLogWriter(directory: $0, build: build.id)
        }
        self.activityWriter = activityWriter
        let cycleWriter = directory.map {
            CycleLogWriter(directory: $0, build: build.id)
        }
        self.cycleWriter = cycleWriter
        stallRecorder = directory.map { StallSnapshotRecorder(directory: $0) }
        stallImageWriter = directory.map { StallImageWriter(directory: $0) }
        if let summary = try? activityWriter?.summary() {
            activitySummary = summary
        }
        if let summary = try? cycleWriter?.summary() {
            cycleSummary = summary
        }
        writeDiagnostics()
    }

    var isRunning: Bool {
        loopTask != nil
    }

    var topDungeonSummary: String? {
        guard
            let top = activitySummary.byDungeon.max(by: {
                $0.value < $1.value
            })
        else {
            return nil
        }
        return "\(top.key) \(top.value)회"
    }

    var isTransitioning: Bool {
        status == .stopping
            || (operationTask != nil && !startPending)
    }

    var primaryActionTitle: String {
        isRunning || startPending ? "중지" : "시작"
    }

    var canRequestPermission: Bool {
        permissionCapability(for: lastPreflightIssue) != nil
    }

    var areTargetFieldsLocked: Bool {
        isRunning
            || startPending
            || AutomationTargetFieldPolicy.isLocked(status: status)
    }

    /// 메뉴가 열릴 때 시세 수집기 heartbeat를 다시 읽는다.
    func refreshPlatformStatus() {
        collectorStatus = PlatformStatus.collectorRow()
    }

    func toggleAutomation() {
        guard status != .stopping else {
            return
        }

        if startPending {
            lifecycleGate.invalidate()
            startPending = false
            operationTask?.cancel()
            operationTask = nil
            status = .stopped
            return
        }
        guard operationTask == nil else {
            return
        }

        if loopTask == nil {
            beginStart()
        } else {
            beginStop()
        }
    }

    func requestMissingPermission() {
        guard
            operationTask == nil,
            let capability = permissionCapability(
                for: lastPreflightIssue
            )
        else {
            return
        }

        operationTask = Task { [weak self] in
            guard let self else {
                return
            }
            _ = await self.preflightService.requestPermission(
                capability
            )
            self.operationTask = nil
        }
    }

    func openDiagnosticsFolder() {
        let fileManager = FileManager.default
        guard
            let folder = Self.diagnosticsDirectory(
                fileManager: fileManager
            )
        else {
            status = .needsAttention(
                "진단 폴더 위치를 찾을 수 없습니다."
            )
            return
        }

        do {
            try fileManager.createDirectory(
                at: folder,
                withIntermediateDirectories: true
            )
            NSWorkspace.shared.open(folder)
        } catch {
            status = .needsAttention(
                "진단 폴더를 열 수 없습니다."
            )
        }
    }

    func quit() {
        guard loopTask == nil, !startPending else {
            status = .needsAttention(
                "먼저 자동화를 안전하게 중지해 주세요."
            )
            return
        }
        NSApplication.shared.terminate(nil)
    }

    func resumeAfterRestorationFailure() {
        guard
            status == .pausedRestorationFailure,
            let coordinator
        else {
            return
        }
        status = .observing
        Task {
            await coordinator.resumeAfterRestorationFailure()
        }
    }
}

private extension AppModel {
    static let bundleIdentifierKey =
        "MAgent.targetBundleIdentifier"
    static let titleContainsKey =
        "MAgent.targetTitleContains"
    static let appVersion =
        Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "dev"

    static func diagnosticsDirectory(
        fileManager: FileManager = .default
    ) -> URL? {
        MAgentPaths.supportDirectory(
            fileManager: fileManager
        )
    }

    func writeDiagnostics() {
        let content = DiagnosticsSnapshot.Content(
            schemaVersion: 1,
            appVersion: Self.appVersion,
            processID: ProcessInfo.processInfo.processIdentifier,
            statusDescription: status.koreanDescription,
            preflight: lastPreflightDiagnostics,
            lastActionDescription: lastActionDescription,
            lastActionAt: lastActionAt,
            observation: lastObservationDiagnostics,
            noActionReason: lastNoActionReason
        )
        diagnosticsWriter?.write(content: content)
        // status.json은 매 상태 변화마다 덮어써져 멈춘 화면이 곧 사라진다.
        // 진행이 막힌 순간만 따로 남겨 사후 진단에 쓴다.
        stallRecorder?.record(
            content: content,
            isStalled: status.isStalled
        )
    }

    /// 클릭이 오래 끊기면 메뉴바를 '확인 필요'로 바꾸고 그때 화면을
    /// PNG로 남긴다. 상태가 `.observing`인 채 굳으면 겉보기엔 정상이라
    /// 사용자가 우연히 볼 때까지 몇 분씩 그냥 흘러갔다.
    func applyQuietStall(result: AutomationCycleResult) async {
        // '.action'은 클릭 말고 취소·복원실패·중단에도 붙는다. 그것까지
        // 동작으로 세면 입력 generation이 계속 튀는 상황에서 클릭이 한 번도
        // 안 나가는데 침묵 시계만 살아나, 잡으려던 멈춤을 그대로 놓친다.
        // .clickOutcomeUncertain은 클릭이 실제로 나간 뒤 결과만 불확실한
        // 경우라 함께 센다. 빼면 클릭이 나가는데도 침묵으로 오판한다.
        // 화면이 흐르고 있으면 멈춘 게 아니다. 클릭만 세면 전투가 긴
        // 던전에서 오탐이 난다(실측: 북쪽 폐허 심층 2층은 전투만 최대
        // 241초라 임계값 150초를 그냥 넘긴다). 전투 중에는 체력·알림·채팅이
        // 계속 바뀌고, 진짜로 굳은 화면은 글자가 그대로다.
        let screenMoved = screenActivity.noteTexts(
            lastObservationDiagnostics?.recognizedTexts.map(\.text) ?? []
        )
        let didAct = result == .action(.clicked)
            || result == .action(.clickOutcomeUncertain)
            || screenMoved

        let elapsed = clock.now - quietClockOrigin
        switch quietDetector.note(didAct: didAct, at: elapsed) {
        case .entered:
            quietStallGuidance = Self.quietStallMessage(
                reason: lastNoActionReason
            )
            await captureStallImage()
        case .recovered:
            quietStallGuidance = nil
        case .none:
            break
        }

        // updateAfterCycle이 매 사이클 status를 덮어쓰므로 그 뒤에 다시 씌운다.
        if let quietStallGuidance, !status.isStalled {
            status = .needsAttention(quietStallGuidance)
        }
    }

    /// 안내 문구의 초를 감지 임계값에서 그대로 가져와, 둘이 어긋나
    /// 사용자가 엉뚱한 시간을 기다리는 일이 없게 한다.
    static func quietStallMessage(reason: NoActionReason?) -> String {
        QuietStallMessage.text(
            seconds: Int(
                QuietStallDetector.defaultThreshold.components.seconds
            ),
            reason: reason
        )
    }

    func captureStallImage() async {
        guard
            let stallImageWriter,
            let capture = try? await captureService.captureWindow(
                bundleIdentifier: bundleIdentifier,
                titleContains: titleContains
            )
        else {
            return
        }
        stallImageWriter.write(capture.image, at: Date())
    }

    func beginStart() {
        quietDetector.reset()
        quietStallGuidance = nil
        quietClockOrigin = clock.now
        runningSince = Date()
        cyclesAtStart = cycleSummary.totalCycles
        let session = lifecycleGate.beginStart(
            target: TargetConfiguration(
                bundleIdentifier: bundleIdentifier,
                titleContains: titleContains
            )
        )
        startPending = true
        status = .checkingPreflight
        operationTask = Task { [weak self] in
            guard let self else {
                return
            }
            await self.start(session: session)
            guard
                self.lifecycleGate.isCurrent(session.token)
            else {
                return
            }
            self.startPending = false
            self.operationTask = nil
        }
    }

    func beginStop() {
        _ = lifecycleGate.begin()
        status = .stopping
        operationTask = Task { [weak self] in
            guard let self else {
                return
            }
            await self.stop()
            self.operationTask = nil
        }
    }

    func start(
        session: AutomationLifecycleGate.StartSession
    ) async {
        let token = session.token
        let configuration = session.target
        saveConfiguration(configuration)
        let preflight = await preflightService.check(
            configuration: configuration
        )
        lastPreflightDiagnostics = PreflightDiagnostics(
            result: preflight
        )
        guard
            lifecycleGate.isCurrent(token),
            !Task.isCancelled
        else {
            return
        }
        guard case .ready = preflight else {
            if case let .needsAttention(issue) = preflight {
                lastPreflightIssue = issue
                status = .needsAttention(issue.koreanGuidance)
            }
            return
        }

        do {
            let rules = try RuleLoader().loadDefaultRules(
                usesSilverCoin: usesSilverCoin,
                usesTribute: usesTribute
            )
            let idleMonitor = UserIdleMonitor()
            try idleMonitor.start()

            let observer = CapturedWindowSceneObserver(
                captureService: captureService,
                sceneObserver: SceneObserver(),
                rules: rules,
                bundleIdentifier: configuration.bundleIdentifier,
                titleContains: configuration.titleContains
            )
            let actionPerformer = ForegroundActionCoordinator(
                inputMonitor: idleMonitor
            )
            let coordinator = try AutomationCoordinator(
                rules: rules,
                observer: observer,
                inputMonitor: idleMonitor,
                actionPerformer: actionPerformer,
                statusReporter: { [weak self] status in
                    await MainActor.run {
                        guard
                            let self,
                            self.lifecycleGate.isCurrent(token)
                        else {
                            return
                        }
                        self.status = status
                    }
                }
            )

            await coordinator.start()
            guard
                lifecycleGate.isCurrent(token),
                !Task.isCancelled
            else {
                await coordinator.stop()
                idleMonitor.stop()
                return
            }

            self.idleMonitor = idleMonitor
            self.coordinator = coordinator
            lastPreflightIssue = nil
            status = .observing
            loopTask = Task { [weak self, coordinator] in
                await self?.runLoop(
                    coordinator: coordinator,
                    token: token
                )
            }
            cycleTask = Task { [weak self, observer] in
                await self?.runCycleObservationLoop(
                    observer: observer,
                    token: token
                )
            }
        } catch {
            guard lifecycleGate.isCurrent(token) else {
                return
            }
            idleMonitor?.stop()
            idleMonitor = nil
            coordinator = nil
            status = .needsAttention(
                "자동화를 시작할 수 없습니다: \(error.localizedDescription)"
            )
        }
    }

    func stop() async {
        status = .stopping
        let task = loopTask
        task?.cancel()
        let cycles = cycleTask
        cycles?.cancel()
        await task?.value
        await cycles?.value

        if let coordinator {
            await coordinator.stop()
        }
        idleMonitor?.stop()
        idleMonitor = nil
        coordinator = nil
        loopTask = nil
        cycleTask = nil
        runningSince = nil
        status = .stopped
    }

    /// 화면만 보고 던전 1판(사이클)을 센다. 클릭 루프와 분리돼 있어
    /// 사용자가 중간에 직접 버튼을 눌러 넘긴 사이클도 빠지지 않는다.
    /// 결과 화면이 뜬 '순간'에만 한 줄 남기고, 실패는 조용히 넘긴다 —
    /// 기록이 자동화를 막아서는 안 된다.
    func runCycleObservationLoop(
        observer: any AutomationScreenObserving,
        token: AutomationLifecycleGate.Token
    ) async {
        var tracker = CycleTracker()
        while !Task.isCancelled {
            do {
                let frame = try await observer.observe()
                try Task.checkCancellation()
                guard lifecycleGate.isCurrent(token) else {
                    return
                }
                if
                    let size = frame.observation.imageSize,
                    let record = tracker.observe(
                        texts: frame.observation.recognizedTexts,
                        imageSize: size
                    )
                {
                    recordCycle(record)
                }
            } catch is CancellationError {
                return
            } catch {
                // 창 전환·게임 재시작 등 일시적 실패는 다음 주기에 다시 본다.
            }
            do {
                try await clock.sleep(for: Self.cycleObservationInterval)
            } catch {
                return
            }
        }
    }

    func runLoop(
        coordinator: AutomationCoordinator,
        token: AutomationLifecycleGate.Token
    ) async {
        var consecutiveFailures = 0
        while !Task.isCancelled {
            do {
                let result = try await coordinator.runCycle()
                try Task.checkCancellation()
                guard lifecycleGate.isCurrent(token) else {
                    return
                }
                consecutiveFailures = 0
                let coordinatorState = await coordinator.state
                lastObservationDiagnostics =
                    await coordinator.lastObservation
                lastNoActionReason = await coordinator.lastNoActionReason
                if case .action(.clicked) = result {
                    recordClick(await coordinator.lastClick)
                }
                if case .action(.restorationFailed) = result {
                    recordRestorationFailure(
                        await coordinator.lastRestorationFailures
                    )
                }
                updateAfterCycle(
                    result: result,
                    state: coordinatorState
                )
                await applyQuietStall(result: result)
                // 폴링 간격이 정확히 일정하면 클릭 박자도 일정해진다.
                // 평균은 그대로 두고 흩뿌린다.
                try await clock.sleep(
                    for: Self.pollingJitter.applied(
                        to: AutomationPollingSchedule.delay(for: status)
                    )
                )
            } catch is CancellationError {
                return
            } catch {
                guard lifecycleGate.isCurrent(token) else {
                    return
                }
                consecutiveFailures += 1
                // 시스템이 꺼 버린 입력 감시를 되살린다. 되살리지 않으면
                // 화면도 후보도 멀쩡한데 대기 단계에서만 계속 실패해
                // 사람이 앱을 껐다 켤 때까지 굳는다(실측 2026-08-01
                // 07:52~07:59, 6분 46초). 사람이 멈춘 감시는 안 건드린다.
                try? idleMonitor?.restartIfDisabled()
                // 포기하지 않는다. 맥이 잠들거나 게임이 재시작하면 몇 시간씩
                // 실패하는데, 그때 루프를 벗어나면 깨어나도 스스로 못 돌아온다
                // (실측 2026-07-29: 15초 만에 손을 뗀 뒤 3시간 방치. 그때
                // 접근성은 이미 정상이었다). 상태로 알리되 계속 두드린다.
                status = .needsAttention(
                    "화면 확인에 실패해 다시 시도하는 중입니다: "
                        + error.localizedDescription
                )
                do {
                    try await clock.sleep(
                        for: retryPolicy.backoff(
                            consecutiveFailures: consecutiveFailures
                        )
                    )
                } catch {
                    return
                }
            }
        }
    }

    func updateAfterCycle(
        result: AutomationCycleResult,
        state: AutomationState
    ) {
        if case let .action(outcome) = result {
            switch outcome {
            case .clicked:
                lastActionDescription = "버튼 클릭 완료"
                lastActionAt = Date()
            case .restorationFailed:
                status = .pausedRestorationFailure
                return
            case .cancelled:
                lastActionDescription = "사용자 입력으로 클릭 취소"
                lastActionAt = Date()
            case .failedBeforeClick:
                lastActionDescription = "클릭 전 안전 중단"
                lastActionAt = Date()
            case .clickOutcomeUncertain:
                lastActionDescription = "클릭 결과 확인 필요"
                lastActionAt = Date()
            }
        }
        // 침묵 멈춤 안내를 매 사이클 지웠다 다시 씌우면 status가 false→true로
        // 계속 튀어, 엣지에서만 쓰는 stall-log가 폴링마다 한 줄씩 쌓인다
        // (실측: 멈춤 1회에 14줄, 40줄에 103KB). 안내가 살아 있으면 유지한다.
        guard quietStallGuidance == nil else {
            return
        }
        status = .projecting(state)
    }

    func recordClick(_ click: AutomationCoordinator.ClickRecord?) {
        guard let activityWriter, let click else {
            return
        }
        // 입장 버튼을 누른 규칙이 곧 '이 판을 어떻게 들어갔나'다. 입장 규칙이
        // 아니면 nil이라 컷신 넘기기 같은 클릭이 값을 덮어쓰지 않는다.
        if let entry = DungeonEntry(ruleID: click.ruleID) {
            lastEntry = entry
        }
        try? activityWriter.append(
            ActivityEvent(
                at: Date(),
                outcome: "clicked",
                scene: click.ruleID,
                dungeonName: click.dungeonName,
                phases: click.phases
            )
        )
        if let summary = try? activityWriter.summary() {
            activitySummary = summary
        }
    }

    func recordCycle(_ record: CycleRecord) {
        guard let cycleWriter else {
            return
        }
        try? cycleWriter.append(record.entered(lastEntry))
        // 한 판에 한 번만 쓴다. 앱이 누르지 않은 입장(사용자가 직접 들어간
        // 경우)까지 직전 값으로 채우면 통계가 조용히 틀어진다.
        lastEntry = nil
        if let summary = try? cycleWriter.summary() {
            cycleSummary = summary
        }
    }

    func recordRestorationFailure(
        _ failures: [ForegroundRestorationFailure]
    ) {
        let detail = failures.isEmpty
            ? "원인 불명"
            : failures
                .map(\.koreanDescription)
                .joined(separator: ", ")
        lastActionDescription = "복원 실패: \(detail)"
        lastActionAt = Date()
        Self.logger.error(
            "복원 실패로 일시정지: \(detail, privacy: .public)"
        )
        guard let activityWriter else {
            return
        }
        try? activityWriter.append(
            ActivityEvent(
                at: Date(),
                outcome: "restorationFailed",
                scene: detail,
                dungeonName: nil
            )
        )
    }

    static let usesSilverCoinKey = "usesSilverCoin"
    static let usesTributeKey = "usesTribute"

    func saveConfiguration(_ configuration: TargetConfiguration) {
        defaults.set(
            configuration.bundleIdentifier,
            forKey: Self.bundleIdentifierKey
        )
        defaults.set(
            configuration.titleContains,
            forKey: Self.titleContainsKey
        )
    }

    func permissionCapability(
        for issue: PreflightIssue?
    ) -> PermissionCapability? {
        switch issue {
        case .screenRecordingDenied:
            .screenRecording
        case .accessibilityDenied:
            .accessibility
        case .inputMonitoringUnavailable:
            .inputMonitoring
        default:
            nil
        }
    }
}
