import CoreGraphics
import Foundation

public enum ProcessLifetimeIdentityError: Error, Equatable, Sendable {
    case invalidLaunchTime
}

public struct ProcessLifetimeIdentity: Equatable, Sendable {
    public let launchTimeIntervalSinceReferenceDate: Double

    public init(
        launchTimeIntervalSinceReferenceDate: Double
    ) throws {
        guard
            launchTimeIntervalSinceReferenceDate.isFinite,
            launchTimeIntervalSinceReferenceDate > 0
        else {
            throw ProcessLifetimeIdentityError.invalidLaunchTime
        }
        self.launchTimeIntervalSinceReferenceDate =
            launchTimeIntervalSinceReferenceDate
    }
}

public struct WindowCandidate: Equatable, Sendable {
    public let windowID: UInt32
    public let processID: Int32
    public let bundleIdentifier: String
    public let title: String
    public let frame: CGRect
    public let isOnScreen: Bool
    public let processLifetimeIdentity: ProcessLifetimeIdentity?

    public init(
        windowID: UInt32,
        processID: Int32,
        bundleIdentifier: String,
        title: String,
        frame: CGRect,
        isOnScreen: Bool,
        processLifetimeIdentity: ProcessLifetimeIdentity?
    ) {
        self.windowID = windowID
        self.processID = processID
        self.bundleIdentifier = bundleIdentifier
        self.title = title
        self.frame = frame
        self.isOnScreen = isOnScreen
        self.processLifetimeIdentity = processLifetimeIdentity
    }
}

public enum WindowTargetError: Error, Equatable, Sendable {
    case notFound
    case ambiguous(count: Int)
    case invalidConfiguration
}

extension WindowTargetError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .notFound:
            "No visible window matched the exact bundle identifier and window title."
        case let .ambiguous(count):
            "\(count) visible windows matched. Enter one exact unique window title."
        case .invalidConfiguration:
            "Bundle identifier and exact window title are required."
        }
    }
}

public enum WindowTarget {
    static func isCurrent(
        _ current: WindowCandidate,
        matching expected: WindowCandidate
    ) -> Bool {
        guard
            let currentLifetime = current.processLifetimeIdentity,
            let expectedLifetime = expected.processLifetimeIdentity
        else {
            return false
        }

        return current.windowID == expected.windowID
            && current.processID == expected.processID
            && currentLifetime == expectedLifetime
            && current.bundleIdentifier == expected.bundleIdentifier
            && current.title == expected.title
            && current.isOnScreen
            && current.frame.size.width > 0
            && current.frame.size.height > 0
    }

    public static func select(
        from candidates: [WindowCandidate],
        bundleIdentifier: String,
        titleContains: String
    ) throws -> WindowCandidate {
        let exactTitle = titleContains.trimmingCharacters(
            in: .whitespacesAndNewlines
        )
        guard
            !bundleIdentifier.trimmingCharacters(
                in: .whitespacesAndNewlines
            ).isEmpty,
            !exactTitle.isEmpty
        else {
            throw WindowTargetError.invalidConfiguration
        }

        let eligible = candidates.filter {
            $0.bundleIdentifier == bundleIdentifier
                && $0.title.compare(
                    exactTitle,
                    options: .caseInsensitive
                ) == .orderedSame
                && $0.isOnScreen
                && $0.processLifetimeIdentity != nil
                && $0.frame.size.width > 0
                && $0.frame.size.height > 0
        }
        guard !eligible.isEmpty else {
            throw WindowTargetError.notFound
        }
        guard eligible.count == 1, let selected = eligible.first else {
            throw WindowTargetError.ambiguous(count: eligible.count)
        }
        return selected
    }
}
