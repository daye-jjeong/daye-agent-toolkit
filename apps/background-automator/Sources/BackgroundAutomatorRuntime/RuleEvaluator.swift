import BackgroundAutomatorCore
import CoreGraphics
import Foundation

public enum RuleEvaluatorError: Error, Equatable, Sendable {
    case duplicateRuleID(String)
    case invalidRuleConfiguration(ruleID: String)
}

public struct RuleEvaluator: Sendable {
    private let rulesByID: [String: AutomationRule]
    private var tracker: StableObservationTracker

    public init(
        rules: [AutomationRule],
        targetRectangleTolerancePixels: Double = 2
    ) throws {
        var rulesByID: [String: AutomationRule] = [:]
        for rule in rules {
            guard Self.isValid(rule) else {
                throw RuleEvaluatorError.invalidRuleConfiguration(
                    ruleID: rule.id
                )
            }
            guard rulesByID[rule.id] == nil else {
                throw RuleEvaluatorError.duplicateRuleID(rule.id)
            }
            rulesByID[rule.id] = rule
        }

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
            tracker.reset()
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
        return tracker.equivalent(candidate, freshCandidate)
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
            !containsBlockedSceneSkip(observation),
            observation.actionCandidates.count == 1,
            let observedCandidate = observation.actionCandidates.first,
            rulesByID[observedCandidate.ruleID] != nil
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

    static func isValid(_ rule: AutomationRule) -> Bool {
        !rule.id.trimmingCharacters(
            in: .whitespacesAndNewlines
        ).isEmpty
            && rule.id == rule.id.trimmingCharacters(
                in: .whitespacesAndNewlines
            )
            && rule.minimumOCRConfidence.isFinite
            && (0 ... 1).contains(rule.minimumOCRConfidence)
            && rule.stableObservationCount >=
                RuleSafetyMinimums.stableObservationCount
    }
}
