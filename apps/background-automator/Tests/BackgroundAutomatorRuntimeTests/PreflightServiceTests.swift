import BackgroundAutomatorCore
import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func preflightRejectsUnconfiguredTargetWithoutCheckingPermissions() async {
    let permissions = FakePermissionChecker()
    let environment = FakePreflightEnvironment()
    let service = PreflightService(
        permissions: permissions,
        environment: environment
    )

    let result = await service.check(
        configuration: TargetConfiguration(
            bundleIdentifier: " ",
            titleContains: ""
        )
    )

    #expect(result == .needsAttention(.targetNotConfigured))
    #expect(await permissions.checkedCapabilities.isEmpty)
    #expect(await permissions.requestedCapabilities.isEmpty)
}

@Test
func preflightRejectsBlankExactWindowTitleAsUnconfigured() async {
    let permissions = FakePermissionChecker()
    let service = PreflightService(
        permissions: permissions,
        environment: FakePreflightEnvironment()
    )

    let result = await service.check(
        configuration: TargetConfiguration(
            bundleIdentifier: "com.example.game",
            titleContains: " "
        )
    )

    #expect(result == .needsAttention(.targetNotConfigured))
    #expect(await permissions.checkedCapabilities.isEmpty)
    #expect(
        PreflightIssue.targetNotConfigured.koreanGuidance
            .contains("정확한 창 제목")
    )
}

@Test(arguments: [
    (
        PermissionCapability.screenRecording,
        PreflightIssue.screenRecordingDenied
    ),
    (
        PermissionCapability.accessibility,
        PreflightIssue.accessibilityDenied
    ),
    (
        PermissionCapability.inputMonitoring,
        PreflightIssue.inputMonitoringUnavailable
    ),
])
func preflightReturnsFirstMissingPermissionWithoutPrompting(
    deniedCapability: PermissionCapability,
    expectedIssue: PreflightIssue
) async {
    let permissions = FakePermissionChecker(
        deniedCapability: deniedCapability
    )
    let service = PreflightService(
        permissions: permissions,
        environment: FakePreflightEnvironment()
    )

    let result = await service.check(
        configuration: configuredTarget
    )

    #expect(result == .needsAttention(expectedIssue))
    #expect(await permissions.requestedCapabilities.isEmpty)
}

@Test
func explicitPermissionRequestIsTheOnlyPromptingPath() async {
    let permissions = FakePermissionChecker(
        deniedCapability: .accessibility
    )
    let service = PreflightService(
        permissions: permissions,
        environment: FakePreflightEnvironment()
    )

    _ = await service.check(configuration: configuredTarget)
    let result = await service.requestPermission(.accessibility)

    #expect(result == .denied)
    #expect(
        await permissions.requestedCapabilities
            == [.accessibility]
    )
}

@Test
func preflightRequiresExactTargetApplicationToBeRunning() async {
    let environment = FakePreflightEnvironment(isApplicationRunning: false)
    let service = PreflightService(
        permissions: FakePermissionChecker(),
        environment: environment
    )

    let result = await service.check(configuration: configuredTarget)

    #expect(result == .needsAttention(.targetNotRunning))
    #expect(
        await environment.requestedBundleIdentifiers
            == ["com.example.game"]
    )
}

@Test
func preflightRequiresVisibleNonMinimizedTargetWindow() async {
    let environment = FakePreflightEnvironment(window: nil)
    let service = PreflightService(
        permissions: FakePermissionChecker(),
        environment: environment
    )

    let result = await service.check(configuration: configuredTarget)

    #expect(result == .needsAttention(.targetWindowUnavailable))
}

@Test
func preflightReportsAmbiguousExactWindowsWithCount() async {
    let service = PreflightService(
        permissions: FakePermissionChecker(),
        environment: FakePreflightEnvironment(
            visibleWindowError: WindowTargetError.ambiguous(count: 2)
        )
    )

    let result = await service.check(configuration: configuredTarget)

    #expect(
        result == .needsAttention(
            .ambiguousTargetWindows(count: 2)
        )
    )
    #expect(
        PreflightIssue.ambiguousTargetWindows(count: 2)
            .koreanGuidance.contains("2개")
    )
}

@Test
func preflightRejectsUnsupportedWindowLayout() async {
    let environment = FakePreflightEnvironment(
        window: preflightWindow(
            frame: CGRect(x: 0, y: 0, width: 300, height: 300)
        )
    )
    let service = PreflightService(
        permissions: FakePermissionChecker(),
        environment: environment
    )

    let result = await service.check(configuration: configuredTarget)

    #expect(result == .needsAttention(.unsupportedLayout))
}

@Test
func preflightReturnsReadyContextForSupportedVisibleWindow() async throws {
    let window = preflightWindow(
        frame: CGRect(x: 0, y: 0, width: 626, height: 949)
    )
    let service = PreflightService(
        permissions: FakePermissionChecker(),
        environment: FakePreflightEnvironment(window: window)
    )

    let result = await service.check(configuration: configuredTarget)
    let context = try #require(result.readyContext)

    #expect(context.window == window)
    #expect(context.layout == .portraitMobile)
}

@Test(arguments: [
    PreflightIssue.targetNotConfigured,
    .screenRecordingDenied,
    .accessibilityDenied,
    .inputMonitoringUnavailable,
    .targetNotRunning,
    .targetWindowUnavailable,
    .ambiguousTargetWindows(count: 2),
    .unsupportedLayout,
])
func everyPreflightIssueHasConciseKoreanGuidance(
    issue: PreflightIssue
) {
    #expect(!issue.koreanGuidance.isEmpty)
    #expect(issue.koreanGuidance.count < 100)
}

private let configuredTarget = TargetConfiguration(
    bundleIdentifier: "com.example.game",
    titleContains: "Mabinogi"
)

private func preflightWindow(frame: CGRect) -> WindowCandidate {
    WindowCandidate(
        windowID: 7,
        processID: 44,
        bundleIdentifier: "com.example.game",
        title: "Mabinogi",
        frame: frame,
        isOnScreen: true,
        processLifetimeIdentity: try? ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: 10
        )
    )
}

private actor FakePermissionChecker: PermissionChecking {
    private(set) var checkedCapabilities: [PermissionCapability] = []
    private(set) var requestedCapabilities: [PermissionCapability] = []
    private let deniedCapability: PermissionCapability?

    init(deniedCapability: PermissionCapability? = nil) {
        self.deniedCapability = deniedCapability
    }

    func status(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus {
        checkedCapabilities.append(capability)
        return capability == deniedCapability ? .denied : .authorized
    }

    func requestAuthorization(
        for capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus {
        requestedCapabilities.append(capability)
        return capability == deniedCapability ? .denied : .authorized
    }
}

private actor FakePreflightEnvironment:
    PreflightEnvironmentChecking
{
    private(set) var requestedBundleIdentifiers: [String] = []
    private let applicationRunning: Bool
    private let window: WindowCandidate?
    private let visibleWindowError: (any Error)?

    init(
        isApplicationRunning: Bool = true,
        window: WindowCandidate? = preflightWindow(
            frame: CGRect(x: 0, y: 0, width: 626, height: 949)
        ),
        visibleWindowError: (any Error)? = nil
    ) {
        applicationRunning = isApplicationRunning
        self.window = window
        self.visibleWindowError = visibleWindowError
    }

    func isApplicationRunning(
        bundleIdentifier: String
    ) async -> Bool {
        requestedBundleIdentifiers.append(bundleIdentifier)
        return applicationRunning
    }

    func visibleWindow(
        configuration: TargetConfiguration
    ) async throws -> WindowCandidate? {
        if let visibleWindowError {
            throw visibleWindowError
        }
        return window
    }
}
