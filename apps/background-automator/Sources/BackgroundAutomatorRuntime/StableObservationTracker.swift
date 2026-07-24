import BackgroundAutomatorCore
import CoreGraphics
import Foundation

public struct SceneFingerprint: Equatable, Sendable {
    public let semanticTexts: [String]
    public let targetText: String?

    public init(
        semanticTexts: [String],
        targetText: String?
    ) {
        self.semanticTexts = semanticTexts
            .map(Self.normalize)
            .filter { !$0.isEmpty }
            .sorted()

        if let targetText {
            let normalizedTarget = Self.normalize(targetText)
            self.targetText = normalizedTarget.isEmpty
                ? nil
                : normalizedTarget
        } else {
            self.targetText = nil
        }
    }

    init(
        observation: SceneObservation,
        actionCandidate: SceneActionCandidate
    ) {
        self.init(
            semanticTexts: observation.recognizedTexts.map(\.text),
            targetText: actionCandidate.targetText
        )
    }

    static func normalize(_ text: String) -> String {
        text.unicodeScalars
            .filter { !CharacterSet.whitespacesAndNewlines.contains($0) }
            .map(String.init)
            .joined()
    }
}

public enum ActionCandidateError: Error, Equatable, Sendable {
    case invalidRuleID
    case invalidWindowIdentity
    case unsupportedLayout
    case invalidTargetPixelRect
}

public struct ActionCandidate: Equatable, Sendable {
    public let ruleID: String
    public let windowIdentity: WindowCandidate
    public let layout: LayoutProfile
    public let sceneFingerprint: SceneFingerprint
    public let captureIdentity: CaptureIdentity
    public let targetPixelRect: CGRect

    public init(
        ruleID: String,
        windowIdentity: WindowCandidate,
        layout: LayoutProfile,
        sceneFingerprint: SceneFingerprint,
        captureIdentity: CaptureIdentity,
        targetPixelRect: CGRect
    ) throws {
        guard
            !ruleID.trimmingCharacters(
                in: .whitespacesAndNewlines
            ).isEmpty
        else {
            throw ActionCandidateError.invalidRuleID
        }
        guard Self.isValid(windowIdentity) else {
            throw ActionCandidateError.invalidWindowIdentity
        }
        guard layout != .unsupported else {
            throw ActionCandidateError.unsupportedLayout
        }
        guard Self.isValid(targetPixelRect) else {
            throw ActionCandidateError.invalidTargetPixelRect
        }

        self.ruleID = ruleID
        self.windowIdentity = windowIdentity
        self.layout = layout
        self.sceneFingerprint = sceneFingerprint
        self.captureIdentity = captureIdentity
        self.targetPixelRect = targetPixelRect
    }

    static func isValid(_ rect: CGRect) -> Bool {
        let values = [
            rect.origin.x,
            rect.origin.y,
            rect.size.width,
            rect.size.height,
            rect.maxX,
            rect.maxY,
        ]
        return values.allSatisfy(\.isFinite)
            && rect.origin.x >= 0
            && rect.origin.y >= 0
            && rect.size.width > 0
            && rect.size.height > 0
    }

    static func isValid(_ window: WindowCandidate) -> Bool {
        let frame = window.frame
        let values = [
            frame.origin.x,
            frame.origin.y,
            frame.size.width,
            frame.size.height,
            frame.maxX,
            frame.maxY,
        ]
        return window.windowID != 0
            && window.processID > 0
            && !window.bundleIdentifier.isEmpty
            && window.processLifetimeIdentity != nil
            && window.isOnScreen
            && values.allSatisfy(\.isFinite)
            && frame.size.width > 0
            && frame.size.height > 0
    }
}

public enum StableObservationTrackerError: Error, Equatable, Sendable {
    case invalidTargetRectangleTolerance
}

public struct StableObservationTracker: Sendable {
    /// Absolute tolerance applied independently to x, y, width, and height.
    /// Values are capture-image pixels, not points or normalized coordinates.
    public let targetRectangleTolerancePixels: Double

    private var previousCandidate: ActionCandidate?
    private var consecutiveObservationCount = 0
    private var lastSeenCaptureIdentity: CaptureIdentity?
    private var latchedCandidate: ActionCandidate?

    public init(
        targetRectangleTolerancePixels: Double = 2
    ) throws {
        guard
            targetRectangleTolerancePixels.isFinite,
            targetRectangleTolerancePixels >= 0
        else {
            throw StableObservationTrackerError
                .invalidTargetRectangleTolerance
        }
        self.targetRectangleTolerancePixels =
            targetRectangleTolerancePixels
    }

    public mutating func record(
        _ candidate: ActionCandidate?,
        requiredObservationCount: Int
    ) -> ActionCandidate? {
        guard
            requiredObservationCount >=
                RuleSafetyMinimums.stableObservationCount,
            let candidate
        else {
            resetStreak()
            return nil
        }

        guard acceptCaptureIdentity(candidate.captureIdentity) else {
            resetStreak()
            return nil
        }

        if let latchedCandidate {
            guard !equivalentTarget(latchedCandidate, candidate) else {
                resetStreak()
                return nil
            }
            self.latchedCandidate = nil
            resetStreak()
        }

        if let previousCandidate,
           equivalentTarget(previousCandidate, candidate) {
            consecutiveObservationCount += 1
        } else {
            previousCandidate = candidate
            consecutiveObservationCount = 1
        }

        guard consecutiveObservationCount >= requiredObservationCount else {
            return nil
        }
        latchedCandidate = candidate
        resetStreak()
        return candidate
    }

    public mutating func resetForRetry() {
        latchedCandidate = nil
        resetStreak()
    }

    private mutating func resetStreak() {
        previousCandidate = nil
        consecutiveObservationCount = 0
    }

    public func revalidationMatches(
        _ first: ActionCandidate,
        _ second: ActionCandidate
    ) -> Bool {
        second.captureIdentity.isStrictlyNewer(
            than: first.captureIdentity
        ) && equivalentTarget(first, second)
    }

    private func equivalentTarget(
        _ first: ActionCandidate,
        _ second: ActionCandidate
    ) -> Bool {
        // sceneFingerprint(화면 전체 텍스트)는 비교하지 않는다. 결과 화면의
        // '순수 전투 시간' 등 매초 변하는 배경 텍스트 때문에 같은 버튼도
        // 절대 안정되지 않기 때문. 버튼 정체성(ruleID·창·레이아웃·위치)만
        // 검사한다. 화면 전환은 ruleID·위치 변화로 이미 감지된다.
        first.ruleID == second.ruleID
            && first.windowIdentity == second.windowIdentity
            && first.layout == second.layout
            && rectanglesAreWithinTolerance(
                first.targetPixelRect,
                second.targetPixelRect
            )
    }

    private mutating func acceptCaptureIdentity(
        _ captureIdentity: CaptureIdentity
    ) -> Bool {
        guard let lastSeenCaptureIdentity else {
            self.lastSeenCaptureIdentity = captureIdentity
            return true
        }
        guard
            captureIdentity.sessionID ==
                lastSeenCaptureIdentity.sessionID
        else {
            resetForRetry()
            self.lastSeenCaptureIdentity = captureIdentity
            return true
        }
        guard captureIdentity.isStrictlyNewer(
            than: lastSeenCaptureIdentity
        ) else {
            return false
        }
        self.lastSeenCaptureIdentity = captureIdentity
        return true
    }

    private func rectanglesAreWithinTolerance(
        _ first: CGRect,
        _ second: CGRect
    ) -> Bool {
        guard
            ActionCandidate.isValid(first),
            ActionCandidate.isValid(second)
        else {
            return false
        }

        let tolerance = CGFloat(targetRectangleTolerancePixels)
        return abs(first.origin.x - second.origin.x) <= tolerance
            && abs(first.origin.y - second.origin.y) <= tolerance
            && abs(first.size.width - second.size.width) <= tolerance
            && abs(first.size.height - second.size.height) <= tolerance
    }
}
