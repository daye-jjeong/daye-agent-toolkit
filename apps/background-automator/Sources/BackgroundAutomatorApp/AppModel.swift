import AppKit
import BackgroundAutomatorCore
import BackgroundAutomatorRuntime
import Combine
import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published var bundleIdentifier: String
    @Published var titleContains: String
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

    private let defaults: UserDefaults
    private let captureService: WindowCaptureService
    private let preflightService: PreflightService
    private let diagnosticsWriter: DiagnosticsFileWriter?
    private let activityWriter: ActivityLogWriter?
    private let clock = ContinuousClock()
    private var lastPreflightDiagnostics: PreflightDiagnostics?
    private var lastObservationDiagnostics: ObservationDiagnostics?

    private var lifecycleGate = AutomationLifecycleGate()
    private var startPending = false
    private var operationTask: Task<Void, Never>?
    private var loopTask: Task<Void, Never>?
    private var coordinator: AutomationCoordinator?
    private var idleMonitor: UserIdleMonitor?
    private var lastPreflightIssue: PreflightIssue?

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        bundleIdentifier = defaults.string(
            forKey: Self.bundleIdentifierKey
        ) ?? ""
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
        let activityWriter = directory.map {
            ActivityLogWriter(directory: $0)
        }
        self.activityWriter = activityWriter
        if let summary = try? activityWriter?.summary() {
            activitySummary = summary
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
}

private extension AppModel {
    static let bundleIdentifierKey =
        "BackgroundAutomator.targetBundleIdentifier"
    static let titleContainsKey =
        "BackgroundAutomator.targetTitleContains"
    static let appVersion =
        Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "dev"

    static func diagnosticsDirectory(
        fileManager: FileManager = .default
    ) -> URL? {
        BackgroundAutomatorPaths.supportDirectory(
            fileManager: fileManager
        )
    }

    func writeDiagnostics() {
        guard let diagnosticsWriter else {
            return
        }
        diagnosticsWriter.write(
            content: DiagnosticsSnapshot.Content(
                schemaVersion: 1,
                appVersion: Self.appVersion,
                processID: ProcessInfo.processInfo.processIdentifier,
                statusDescription: status.koreanDescription,
                preflight: lastPreflightDiagnostics,
                lastActionDescription: lastActionDescription,
                lastActionAt: lastActionAt,
                observation: lastObservationDiagnostics
            )
        )
    }

    func beginStart() {
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
            let rules = try RuleLoader().loadDefaultRules()
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
        await task?.value

        if let coordinator {
            await coordinator.stop()
        }
        idleMonitor?.stop()
        idleMonitor = nil
        coordinator = nil
        loopTask = nil
        status = .stopped
    }

    func runLoop(
        coordinator: AutomationCoordinator,
        token: AutomationLifecycleGate.Token
    ) async {
        while !Task.isCancelled {
            do {
                let result = try await coordinator.runCycle()
                try Task.checkCancellation()
                guard lifecycleGate.isCurrent(token) else {
                    return
                }
                let coordinatorState = await coordinator.state
                lastObservationDiagnostics =
                    await coordinator.lastObservation
                if case .action(.clicked) = result {
                    recordClick(await coordinator.lastClick)
                }
                updateAfterCycle(
                    result: result,
                    state: coordinatorState
                )
                try await clock.sleep(
                    for: AutomationPollingSchedule.delay(
                        for: status
                    )
                )
            } catch is CancellationError {
                return
            } catch {
                guard lifecycleGate.isCurrent(token) else {
                    return
                }
                status = .needsAttention(
                    "화면 확인에 실패했습니다: \(error.localizedDescription)"
                )
                return
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
        status = .projecting(state)
    }

    func recordClick(_ click: AutomationCoordinator.ClickRecord?) {
        guard let activityWriter, let click else {
            return
        }
        try? activityWriter.append(
            ActivityEvent(
                at: Date(),
                outcome: "clicked",
                scene: click.ruleID,
                dungeonName: click.dungeonName
            )
        )
        if let summary = try? activityWriter.summary() {
            activitySummary = summary
        }
    }

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
