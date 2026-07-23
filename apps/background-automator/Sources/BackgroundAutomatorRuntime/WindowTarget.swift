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
}

extension WindowTargetError: LocalizedError {
    public var errorDescription: String? {
        "No visible window matched the exact bundle identifier and title filter."
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
        guard let selected = candidates
            .filter({
                $0.bundleIdentifier == bundleIdentifier
                    && $0.title.range(of: titleContains, options: .caseInsensitive) != nil
                    && $0.isOnScreen
                    && $0.processLifetimeIdentity != nil
                    && $0.frame.size.width > 0
                    && $0.frame.size.height > 0
            })
            .max(by: { area(of: $0) < area(of: $1) })
        else {
            throw WindowTargetError.notFound
        }

        return selected
    }

    private static func area(of candidate: WindowCandidate) -> CGFloat {
        candidate.frame.size.width * candidate.frame.size.height
    }
}
