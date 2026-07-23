import AppKit
import BackgroundAutomatorCore
import Foundation

public struct TargetConfiguration: Equatable, Sendable {
    public let bundleIdentifier: String
    public let titleContains: String

    public init(
        bundleIdentifier: String,
        titleContains: String
    ) {
        self.bundleIdentifier = bundleIdentifier
        self.titleContains = titleContains
    }

    public var isConfigured: Bool {
        !bundleIdentifier
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .isEmpty
            && !titleContains
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .isEmpty
    }
}

public enum PreflightIssue: Equatable, Sendable {
    case targetNotConfigured
    case screenRecordingDenied
    case accessibilityDenied
    case inputMonitoringUnavailable
    case targetNotRunning
    case targetWindowUnavailable
    case ambiguousTargetWindows(count: Int)
    case unsupportedLayout

    public var koreanGuidance: String {
        switch self {
        case .targetNotConfigured:
            "번들 ID와 정확한 창 제목을 입력해 주세요."
        case .screenRecordingDenied:
            "시스템 설정에서 화면 기록 권한을 허용해 주세요."
        case .accessibilityDenied:
            "시스템 설정에서 손쉬운 사용 권한을 허용해 주세요."
        case .inputMonitoringUnavailable:
            "시스템 설정에서 입력 모니터링 권한을 허용해 주세요."
        case .targetNotRunning:
            "설정한 대상 앱을 실행해 주세요."
        case .targetWindowUnavailable:
            "정확한 제목의 창 하나만 열고 최소화를 해제해 주세요."
        case let .ambiguousTargetWindows(count):
            "같은 제목의 창이 \(count)개입니다. 고유한 정확한 창 제목을 입력해 주세요."
        case .unsupportedLayout:
            "대상 창을 지원되는 가로 또는 모바일 세로 크기로 조정해 주세요."
        }
    }
}

public struct PreflightReadyContext: Equatable, Sendable {
    public let window: WindowCandidate
    public let layout: LayoutProfile

    public init(window: WindowCandidate, layout: LayoutProfile) {
        self.window = window
        self.layout = layout
    }
}

public enum PreflightResult: Equatable, Sendable {
    case ready(PreflightReadyContext)
    case needsAttention(PreflightIssue)

    public var readyContext: PreflightReadyContext? {
        guard case let .ready(context) = self else {
            return nil
        }
        return context
    }
}

public protocol PreflightEnvironmentChecking: Sendable {
    func isApplicationRunning(
        bundleIdentifier: String
    ) async -> Bool

    func visibleWindow(
        configuration: TargetConfiguration
    ) async throws -> WindowCandidate?
}

public struct ProductionPreflightEnvironment:
    PreflightEnvironmentChecking,
    Sendable
{
    private let captureService: WindowCaptureService

    public init(captureService: WindowCaptureService) {
        self.captureService = captureService
    }

    public func isApplicationRunning(
        bundleIdentifier: String
    ) async -> Bool {
        await MainActor.run {
            NSWorkspace.shared.runningApplications.contains {
                $0.bundleIdentifier == bundleIdentifier
            }
        }
    }

    public func visibleWindow(
        configuration: TargetConfiguration
    ) async throws -> WindowCandidate? {
        try await captureService.findWindow(
            bundleIdentifier: configuration.bundleIdentifier,
            titleContains: configuration.titleContains
        )
    }
}

public struct PreflightService: Sendable {
    private let permissions: any PermissionChecking
    private let environment: any PreflightEnvironmentChecking

    public init(
        permissions: any PermissionChecking,
        environment: any PreflightEnvironmentChecking
    ) {
        self.permissions = permissions
        self.environment = environment
    }

    public func check(
        configuration: TargetConfiguration
    ) async -> PreflightResult {
        guard configuration.isConfigured else {
            return .needsAttention(.targetNotConfigured)
        }

        for (capability, issue) in Self.permissionChecks {
            guard
                await permissions.status(for: capability)
                    == .authorized
            else {
                return .needsAttention(issue)
            }
        }

        guard
            await environment.isApplicationRunning(
                bundleIdentifier: configuration.bundleIdentifier
            )
        else {
            return .needsAttention(.targetNotRunning)
        }
        let window: WindowCandidate?
        do {
            window = try await environment.visibleWindow(
                configuration: configuration
            )
        } catch let error as WindowTargetError {
            switch error {
            case let .ambiguous(count):
                return .needsAttention(
                    .ambiguousTargetWindows(count: count)
                )
            case .invalidConfiguration:
                return .needsAttention(.targetNotConfigured)
            case .notFound:
                return .needsAttention(.targetWindowUnavailable)
            }
        } catch {
            return .needsAttention(.targetWindowUnavailable)
        }
        guard let window else {
            return .needsAttention(.targetWindowUnavailable)
        }

        let layout = LayoutClassifier.classify(
            imageSize: window.frame.size
        )
        guard layout != .unsupported else {
            return .needsAttention(.unsupportedLayout)
        }
        return .ready(
            PreflightReadyContext(window: window, layout: layout)
        )
    }

    public func requestPermission(
        _ capability: PermissionCapability
    ) async -> PermissionAuthorizationStatus {
        await permissions.requestAuthorization(for: capability)
    }

    private static let permissionChecks: [
        (PermissionCapability, PreflightIssue)
    ] = [
        (.screenRecording, .screenRecordingDenied),
        (.accessibility, .accessibilityDenied),
        (.inputMonitoring, .inputMonitoringUnavailable),
    ]
}
