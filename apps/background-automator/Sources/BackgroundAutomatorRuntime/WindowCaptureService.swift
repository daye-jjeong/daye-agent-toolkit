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
            "Window \(windowID) has not been selected. Find the target window first."
        case let .staleWindow(windowID):
            "Window \(windowID) changed or is no longer capturable. Find the target window again."
        case let .captureFailed(windowID, reason):
            "Could not capture window \(windowID): \(reason)"
        }
    }
}

public actor WindowCaptureService: WindowCapturing {
    private var selectedCandidatesByID: [UInt32: WindowCandidate] = [:]

    public init() {}

    public func listWindows() async throws -> [WindowCandidate] {
        let windows = try await loadWindows()
        return windows.map(Self.candidate(from:))
    }

    public func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate {
        let candidates = try await listWindows()
        let selected = try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
        selectedCandidatesByID[selected.windowID] = selected
        return selected
    }

    public func capture(windowID: UInt32) async throws -> CGImage {
        guard let expected = selectedCandidatesByID[windowID] else {
            throw WindowCaptureError.windowUnavailable(windowID: windowID)
        }

        let currentWindows = try await loadWindows()
        guard
            let latestExpected = selectedCandidatesByID[windowID],
            WindowTarget.isCurrent(latestExpected, matching: expected)
        else {
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }
        guard let window = currentWindows.first(where: { $0.windowID == windowID }) else {
            selectedCandidatesByID.removeValue(forKey: windowID)
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }

        let current = Self.candidate(from: window)
        guard WindowTarget.isCurrent(current, matching: expected) else {
            selectedCandidatesByID.removeValue(forKey: windowID)
            throw WindowCaptureError.staleWindow(windowID: windowID)
        }

        let configuration = SCStreamConfiguration()
        configuration.showsCursor = false
        configuration.width = max(
            1,
            Int(window.frame.size.width.rounded(.up))
        )
        configuration.height = max(
            1,
            Int(window.frame.size.height.rounded(.up))
        )

        let filter = SCContentFilter(desktopIndependentWindow: window)

        do {
            return try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: configuration
            )
        } catch {
            throw WindowCaptureError.captureFailed(
                windowID: windowID,
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
