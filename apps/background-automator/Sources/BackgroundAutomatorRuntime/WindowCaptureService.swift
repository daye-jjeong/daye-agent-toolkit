import CoreGraphics
import Foundation
@preconcurrency import ScreenCaptureKit

public protocol WindowCapturing: Sendable {
    func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate

    func capture(windowID: UInt32) async throws -> CGImage

    func captureWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCaptureResult
}

public struct WindowCaptureResult: Sendable {
    public let image: CGImage
    public let candidate: WindowCandidate

    public init(image: CGImage, candidate: WindowCandidate) {
        self.image = image
        self.candidate = candidate
    }
}

public struct WindowVisibilityDiagnostic: Sendable {
    public let candidate: WindowCandidate
    public let accessibilityWindow: AccessibilityWindowState

    public init(
        candidate: WindowCandidate,
        accessibilityWindow: AccessibilityWindowState
    ) {
        self.candidate = candidate
        self.accessibilityWindow = accessibilityWindow
    }
}

public enum WindowCaptureError: Error, Equatable, Sendable {
    case shareableContentUnavailable(reason: String)
    case windowUnavailable(windowID: UInt32)
    case staleWindow(windowID: UInt32)
    case captureFailed(windowID: UInt32, reason: String)
}

extension WindowCaptureError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case let .shareableContentUnavailable(reason):
            "Could not enumerate capturable windows: \(reason)"
        case let .windowUnavailable(windowID):
            "Window \(windowID) is not currently available."
        case let .staleWindow(windowID):
            "Window \(windowID) changed or is no longer capturable. Use captureWindow to select again safely."
        case let .captureFailed(windowID, reason):
            "Could not capture window \(windowID): \(reason)"
        }
    }
}

protocol WindowCaptureBackend: Sendable {
    func listCandidates() async throws -> [WindowCandidate]
    func accessibilityWindow(
        matching candidate: WindowCandidate
    ) async throws -> AccessibilityWindowState
    func capture(expected: WindowCandidate) async throws -> WindowCaptureResult
}

private enum PendingSelection: Sendable {
    case bound(WindowCandidate)
    case stale
}

public actor WindowCaptureService: WindowCapturing {
    private let backend: any WindowCaptureBackend
    private var pendingSelectionsByID: [UInt32: PendingSelection] = [:]

    public init() {
        backend = ScreenCaptureKitBackend()
    }

    init(backend: any WindowCaptureBackend) {
        self.backend = backend
    }

    public func listWindows() async throws -> [WindowCandidate] {
        try await backend.listCandidates()
    }

    public func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate {
        let candidates = try await backend.listCandidates()
        let selected = try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        let accessibilityWindow = try await backend.accessibilityWindow(
            matching: selected
        )
        guard WindowVisibilityValidator.isVisible(
            accessibilityWindow: accessibilityWindow
        ) else {
            throw WindowTargetError.notFound
        }
        try bindForRawCapture(selected)
        return selected
    }

    public func capture(windowID: UInt32) async throws -> CGImage {
        guard let pending = pendingSelectionsByID[windowID] else {
            throw WindowCaptureError.windowUnavailable(windowID: windowID)
        }
        guard case let .bound(expected) = pending else {
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }

        let result: WindowCaptureResult
        do {
            result = try await backend.capture(expected: expected)
        } catch let error as WindowCaptureError {
            if case .staleWindow = error {
                pendingSelectionsByID[windowID] = .stale
            }
            throw error
        }

        guard
            case let .bound(latestExpected) = pendingSelectionsByID[windowID],
            WindowTarget.isCurrent(latestExpected, matching: expected)
        else {
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }
        return result.image
    }

    public func captureWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCaptureResult {
        let candidates = try await backend.listCandidates()
        let expected = try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        let accessibilityWindow = try await backend.accessibilityWindow(
            matching: expected
        )
        guard WindowVisibilityValidator.isVisible(
            accessibilityWindow: accessibilityWindow
        ) else {
            throw WindowTargetError.notFound
        }
        return try await backend.capture(expected: expected)
    }

    public func visibilityDiagnostic(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowVisibilityDiagnostic {
        let candidates = try await backend.listCandidates()
        let candidate = try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        let accessibilityWindow = try await backend.accessibilityWindow(
            matching: candidate
        )
        return WindowVisibilityDiagnostic(
            candidate: candidate,
            accessibilityWindow: accessibilityWindow
        )
    }

    private func bindForRawCapture(_ selected: WindowCandidate) throws {
        switch pendingSelectionsByID[selected.windowID] {
        case nil:
            pendingSelectionsByID[selected.windowID] = .bound(selected)

        case let .bound(existing):
            guard WindowTarget.isCurrent(selected, matching: existing) else {
                pendingSelectionsByID[selected.windowID] = .stale
                throw WindowCaptureError.staleWindow(
                    windowID: selected.windowID
                )
            }
            pendingSelectionsByID[selected.windowID] = .bound(selected)

        case .stale:
            throw WindowCaptureError.staleWindow(
                windowID: selected.windowID
            )
        }
    }
}

private actor ScreenCaptureKitBackend: WindowCaptureBackend {
    private let visibilityProvider: any WindowVisibilityProviding
    private let accessibilityProvider: any AccessibilityWindowProviding

    init(
        visibilityProvider: any WindowVisibilityProviding =
            CoreGraphicsWindowVisibilityProvider(),
        accessibilityProvider: any AccessibilityWindowProviding =
            AXAccessibilityWindowProvider()
    ) {
        self.visibilityProvider = visibilityProvider
        self.accessibilityProvider = accessibilityProvider
    }

    func listCandidates() async throws -> [WindowCandidate] {
        let windows = try await loadWindows()
        let visibility = visibilityProvider.snapshot()
        return windows.map {
            Self.candidate(
                from: $0,
                coreGraphicsWindow: visibility[$0.windowID]
            )
        }
    }

    func accessibilityWindow(
        matching candidate: WindowCandidate
    ) async throws -> AccessibilityWindowState {
        let windows = try accessibilityProvider.windows(
            processID: candidate.processID
        )
        return try WindowVisibilityValidator.accessibilityWindow(
            matching: candidate,
            from: windows
        )
    }

    func capture(expected: WindowCandidate) async throws -> WindowCaptureResult {
        let currentWindows = try await loadWindows()
        guard
            let window = currentWindows.first(where: {
                $0.windowID == expected.windowID
            })
        else {
            throw WindowCaptureError.staleWindow(
                windowID: expected.windowID
            )
        }

        let visibility = visibilityProvider.snapshot()
        let current = Self.candidate(
            from: window,
            coreGraphicsWindow: visibility[window.windowID]
        )
        guard WindowTarget.isCurrent(current, matching: expected) else {
            throw WindowCaptureError.staleWindow(
                windowID: expected.windowID
            )
        }
        let accessibilityWindow = try await accessibilityWindow(
            matching: current
        )
        guard WindowVisibilityValidator.isVisible(
            accessibilityWindow: accessibilityWindow
        ) else {
            throw WindowCaptureError.staleWindow(
                windowID: expected.windowID
            )
        }

        let configuration = SCStreamConfiguration()
        configuration.showsCursor = false
        configuration.width = max(
            1,
            Int(current.frame.size.width.rounded(.up))
        )
        configuration.height = max(
            1,
            Int(current.frame.size.height.rounded(.up))
        )

        let filter = SCContentFilter(desktopIndependentWindow: window)

        do {
            let image = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: configuration
            )
            return WindowCaptureResult(image: image, candidate: current)
        } catch {
            throw WindowCaptureError.captureFailed(
                windowID: expected.windowID,
                reason: error.localizedDescription
            )
        }
    }

    private func loadWindows() async throws -> [SCWindow] {
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: false
            )
            return content.windows
        } catch {
            throw WindowCaptureError.shareableContentUnavailable(
                reason: error.localizedDescription
            )
        }
    }

    private static func candidate(
        from window: SCWindow,
        coreGraphicsWindow: CoreGraphicsWindowState?
    ) -> WindowCandidate {
        let processID = window.owningApplication?.processID ?? 0
        return WindowCandidate(
            windowID: window.windowID,
            processID: processID,
            bundleIdentifier: window.owningApplication?.bundleIdentifier ?? "",
            title: window.title ?? "",
            frame: window.frame,
            isOnScreen: WindowVisibilityValidator.isVisible(
                screenCaptureKitIsOnScreen: window.isOnScreen,
                processID: processID,
                coreGraphicsWindow: coreGraphicsWindow
            )
        )
    }
}
