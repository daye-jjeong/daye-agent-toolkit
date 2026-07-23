import BackgroundAutomatorCore
import CoreGraphics
import Foundation

public enum RuleEvaluatorError: Error, Equatable, Sendable {
    case duplicateRuleID(String)
    case invalidRuleConfiguration(ruleID: String)
}

public struct RuleEvaluator: Sendable {
    private let rules: [AutomationRule]
    private let rulesByID: [String: AutomationRule]
    private var tracker: StableObservationTracker

    public init(
        rules: [AutomationRule],
        targetRectangleTolerancePixels: Double = 2
    ) throws {
        do {
            try AutomationRuleValidator.validate(rules)
        } catch let error as AutomationRuleValidationError {
            switch error {
            case let .duplicateRuleID(ruleID):
                throw RuleEvaluatorError.duplicateRuleID(ruleID)
            case let .malformed(ruleID, _):
                throw RuleEvaluatorError.invalidRuleConfiguration(
                    ruleID: ruleID
                )
            }
        }

        var rulesByID: [String: AutomationRule] = [:]
        for rule in rules {
            rulesByID[rule.id] = rule
        }

        self.rules = rules
        self.rulesByID = rulesByID
        tracker = try StableObservationTracker(
            targetRectangleTolerancePixels:
                targetRectangleTolerancePixels
        )
    }

    public mutating func evaluate(
        observation: SceneObservation?,
        windowIdentity: WindowCandidate,
        layout: LayoutProfile
    ) -> ActionCandidate? {
        guard
            let candidate = eligibleCandidate(
                observation: observation,
                windowIdentity: windowIdentity,
                layout: layout
            ),
            let rule = rulesByID[candidate.ruleID]
        else {
            _ = tracker.record(
                nil,
                requiredObservationCount:
                    RuleSafetyMinimums.stableObservationCount
            )
            return nil
        }

        return tracker.record(
            candidate,
            requiredObservationCount: rule.stableObservationCount
        )
    }

    public func revalidate(
        _ candidate: ActionCandidate,
        freshObservation: SceneObservation?,
        windowIdentity: WindowCandidate,
        layout: LayoutProfile
    ) -> Bool {
        guard let freshCandidate = eligibleCandidate(
            observation: freshObservation,
            windowIdentity: windowIdentity,
            layout: layout
        ) else {
            return false
        }
        return tracker.revalidationMatches(candidate, freshCandidate)
    }

    public mutating func resetForRetry() {
        tracker.resetForRetry()
    }
}

private extension RuleEvaluator {
    func eligibleCandidate(
        observation: SceneObservation?,
        windowIdentity: WindowCandidate,
        layout: LayoutProfile
    ) -> ActionCandidate? {
        guard
            layout != .unsupported,
            ActionCandidate.isValid(windowIdentity),
            let observation,
            let captureIdentity = observation.captureIdentity,
            let imageSize = observation.imageSize,
            Self.isValid(imageSize),
            !containsBlockedSceneSkip(observation),
            observation.actionCandidates.count == 1,
            let observedCandidate = observation.actionCandidates.first,
            rulesByID[observedCandidate.ruleID] != nil,
            Self.validatedCandidates(
                rules: rules,
                observation: observation,
                layout: layout,
                imageSize: imageSize
            ) == [observedCandidate]
        else {
            return nil
        }

        return try? ActionCandidate(
            ruleID: observedCandidate.ruleID,
            windowIdentity: windowIdentity,
            layout: layout,
            sceneFingerprint: SceneFingerprint(
                observation: observation,
                actionCandidate: observedCandidate
            ),
            captureIdentity: captureIdentity,
            targetPixelRect: observedCandidate.boundingBox
        )
    }

    func containsBlockedSceneSkip(
        _ observation: SceneObservation
    ) -> Bool {
        observation.recognizedTexts.contains {
            SceneFingerprint.normalize($0.text) == "장면넘기기"
        }
    }

    static func validatedCandidates(
        rules: [AutomationRule],
        observation: SceneObservation,
        layout: LayoutProfile,
        imageSize: CGSize
    ) -> [SceneActionCandidate] {
        rules.compactMap {
            SceneObserver.actionCandidate(
                for: $0,
                observations: observation.recognizedTexts,
                layout: layout,
                imageSize: imageSize
            )
        }
    }

    static func isValid(_ imageSize: CGSize) -> Bool {
        imageSize.width.isFinite
            && imageSize.height.isFinite
            && imageSize.width > 0
            && imageSize.height > 0
    }
}
