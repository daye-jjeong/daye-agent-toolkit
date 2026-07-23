import CoreGraphics
import Foundation

public struct WindowCandidate: Equatable, Sendable {
    public let windowID: UInt32
    public let processID: Int32
    public let bundleIdentifier: String
    public let title: String
    public let frame: CGRect
    public let isOnScreen: Bool

    public init(
        windowID: UInt32,
        processID: Int32,
        bundleIdentifier: String,
        title: String,
        frame: CGRect,
        isOnScreen: Bool
    ) {
        self.windowID = windowID
        self.processID = processID
        self.bundleIdentifier = bundleIdentifier
        self.title = title
        self.frame = frame
        self.isOnScreen = isOnScreen
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
        current.windowID == expected.windowID
            && current.processID == expected.processID
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
