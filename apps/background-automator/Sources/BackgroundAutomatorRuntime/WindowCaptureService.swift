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
    case captureFailed(windowID: UInt32, reason: String)
}

extension WindowCaptureError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case let .shareableContentUnavailable(reason):
            "Could not enumerate capturable windows: \(reason)"
        case let .windowUnavailable(windowID):
            "Window \(windowID) is no longer available. Find the target window again."
        case let .captureFailed(windowID, reason):
            "Could not capture window \(windowID): \(reason)"
        }
    }
}

public actor WindowCaptureService: WindowCapturing {
    private var windowsByID: [UInt32: SCWindow] = [:]

    public init() {}

    public func listWindows() async throws -> [WindowCandidate] {
        let windows = try await loadWindows()
        windowsByID.removeAll(keepingCapacity: true)
        for window in windows {
            windowsByID[window.windowID] = window
        }
        return windows.map(Self.candidate(from:))
    }

    public func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate {
        let candidates = try await listWindows()
        return try WindowTarget.select(
            from: candidates,
            bundleIdentifier: bundleIdentifier,
            titleContains: titleContains
        )
    }

    public func capture(windowID: UInt32) async throws -> CGImage {
        guard let window = windowsByID[windowID] else {
            throw WindowCaptureError.windowUnavailable(windowID: windowID)
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
