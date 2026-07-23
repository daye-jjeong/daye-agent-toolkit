import CoreGraphics
import Foundation
@preconcurrency import ScreenCaptureKit

public protocol WindowCapturing: Sendable {
    func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate

    func capture(windowID: UInt32) async throws -> CGImage
}

public struct WindowCaptureResult: Sendable {
    public let image: CGImage
    public let candidate: WindowCandidate

    public init(image: CGImage, candidate: WindowCandidate) {
        self.image = image
        self.candidate = candidate
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
            "Window \(windowID) changed or is no longer capturable. Find the target window again."
        case let .captureFailed(windowID, reason):
            "Could not capture window \(windowID): \(reason)"
        }
    }
}

protocol WindowCaptureBackend: Sendable {
    func listCandidates() async throws -> [WindowCandidate]
    func capture(expected: WindowCandidate) async throws -> WindowCaptureResult
}

public actor WindowCaptureService: WindowCapturing {
    private let backend: any WindowCaptureBackend

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
        return try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
    }

    public func capture(windowID: UInt32) async throws -> CGImage {
        let candidates = try await backend.listCandidates()
        guard let expected = candidates.first(where: { $0.windowID == windowID }) else {
            throw WindowCaptureError.windowUnavailable(windowID: windowID)
        }
        guard WindowTarget.isCurrent(expected, matching: expected) else {
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }

        return try await backend.capture(expected: expected).image
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
        return try await backend.capture(expected: expected)
    }
}

private actor ScreenCaptureKitBackend: WindowCaptureBackend {
    func listCandidates() async throws -> [WindowCandidate] {
        let windows = try await loadWindows()
        return windows.map(Self.candidate(from:))
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

        let current = Self.candidate(from: window)
        guard WindowTarget.isCurrent(current, matching: expected) else {
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

    private static func candidate(from window: SCWindow) -> WindowCandidate {
        WindowCandidate(
            windowID: window.windowID,
            processID: window.owningApplication?.processID ?? 0,
            bundleIdentifier: window.owningApplication?.bundleIdentifier ?? "",
            title: window.title ?? "",
            frame: window.frame,
            isOnScreen: window.isOnScreen
        )
    }
}
