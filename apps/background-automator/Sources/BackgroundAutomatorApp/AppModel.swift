import AppKit
import BackgroundAutomatorCore
import BackgroundAutomatorRuntime
import Combine
import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published var bundleIdentifier: String
    @Published var titleContains: String
    @Published private(set) var status: AutomationMenuStatus = .stopped
    @Published private(set) var lastActionDescription = "없음"
    @Published private(set) var lastActionAt: Date?

    private let defaults: UserDefaults
    private let captureService: WindowCaptureService
    private let preflightService: PreflightService
    private let clock = ContinuousClock()

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
    }

    var isRunning: Bool {
        loopTask != nil
    }

    var isTransitioning: Bool {
        operationTask != nil || status == .stopping
    }

    var primaryActionTitle: String {
        isRunning ? "중지" : "시작"
    }

    var canRequestPermission: Bool {
        permissionCapability(for: lastPreflightIssue) != nil
    }

    func toggleAutomation() {
        guard operationTask == nil else {
            return
        }

        operationTask = Task { [weak self] in
            guard let self else {
                return
            }
            if self.loopTask == nil {
                await self.start()
            } else {
                await self.stop()
            }
            self.operationTask = nil
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
            let applicationSupport = fileManager.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            ).first
        else {
            status = .needsAttention(
                "진단 폴더 위치를 찾을 수 없습니다."
            )
            return
        }

        let folder = applicationSupport
            .appendingPathComponent(
                "BackgroundAutomator",
                isDirectory: true
            )
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
        guard loopTask == nil else {
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

    func start() async {
        saveConfiguration()
        let configuration = TargetConfiguration(
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        let preflight = await preflightService.check(
            configuration: configuration
        )
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
                        self?.status = status
                    }
                }
            )

            self.idleMonitor = idleMonitor
            self.coordinator = coordinator
            lastPreflightIssue = nil
            status = .observing
            await coordinator.start()
            loopTask = Task { [weak self, coordinator] in
                await self?.runLoop(coordinator: coordinator)
            }
        } catch {
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

    func runLoop(coordinator: AutomationCoordinator) async {
        while !Task.isCancelled {
            do {
                let result = try await coordinator.runCycle()
                try Task.checkCancellation()
                updateAfterCycle(
                    result: result,
                    state: await coordinator.state
                )
                try await clock.sleep(
                    for: AutomationPollingSchedule.delay(
                        for: status
                    )
                )
            } catch is CancellationError {
                return
            } catch {
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

    func saveConfiguration() {
        defaults.set(
            bundleIdentifier,
            forKey: Self.bundleIdentifierKey
        )
        defaults.set(
            titleContains,
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
