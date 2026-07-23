import Foundation

import BackgroundAutomatorCore

public enum RuleLoaderError: Error, Equatable, Sendable {
    case resourceNotFound
    case unsupportedSchemaVersion(Int)
    case malformedDocument(String)
    case malformedSemantics(ruleID: String, reason: String)
}

public struct RuleSafetyMinimums: Sendable {
    public static let stableObservationCount = 2
    public static let postActionDelaySeconds = 0.1
    public static let cooldownSeconds = 0.5

    private init() {}
}

public struct RuleLoader: Sendable {
    public static let supportedSchemaVersion = 1

    public init() {}

    public func loadDefaultRules() throws -> [AutomationRule] {
        guard let url = Bundle.module.url(
            forResource: "default-rules",
            withExtension: "json"
        ) else {
            throw RuleLoaderError.resourceNotFound
        }

        return try load(data: Data(contentsOf: url))
    }

    public func load(data: Data) throws -> [AutomationRule] {
        try validateDocumentShape(data)

        let document: RuleDocument
        do {
            document = try JSONDecoder().decode(RuleDocument.self, from: data)
        } catch {
            throw RuleLoaderError.malformedDocument(
                "invalid JSON schema: \(error)"
            )
        }

        guard document.schemaVersion == Self.supportedSchemaVersion else {
            throw RuleLoaderError.unsupportedSchemaVersion(
                document.schemaVersion
            )
        }

        try validateSemantics(document.rules)
        return document.rules
    }
}

private extension RuleLoader {
    struct RuleDocument: Codable, Equatable, Sendable {
        let schemaVersion: Int
        let rules: [AutomationRule]
    }

    func validateDocumentShape(_ data: Data) throws {
        let raw: Any
        do {
            raw = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw RuleLoaderError.malformedDocument("invalid JSON")
        }

        guard let document = raw as? [String: Any] else {
            throw RuleLoaderError.malformedDocument(
                "document must be an object"
            )
        }
        guard let schemaVersion = document["schemaVersion"] as? Int else {
            throw RuleLoaderError.malformedDocument(
                "schemaVersion must be an integer"
            )
        }
        guard schemaVersion == Self.supportedSchemaVersion else {
            throw RuleLoaderError.unsupportedSchemaVersion(schemaVersion)
        }

        try rejectUnknownKeys(
            in: document,
            allowed: ["schemaVersion", "rules"]
        )

        guard let rules = document["rules"] as? [[String: Any]] else {
            throw RuleLoaderError.malformedDocument(
                "rules must be an array of objects"
            )
        }

        for rule in rules {
            try rejectUnknownKeys(
                in: rule,
                allowed: [
                    "id",
                    "requiredTexts",
                    "forbiddenTexts",
                    "action",
                    "regions",
                    "minimumOCRConfidence",
                    "stableObservationCount",
                    "postActionDelaySeconds",
                    "cooldownSeconds",
                ]
            )

            if let action = rule["action"] as? [String: Any] {
                try rejectUnknownKeys(
                    in: action,
                    allowed: ["targetText", "safePointRegion"]
                )
                if let safeRegion = action["safePointRegion"] as? [String: Any] {
                    try validateRegionKeys(safeRegion)
                }
            }

            if let regions = rule["regions"] as? [String: Any] {
                for value in regions.values {
                    guard let region = value as? [String: Any] else {
                        throw RuleLoaderError.malformedDocument(
                            "search region must be an object"
                        )
                    }
                    try validateRegionKeys(region)
                }
            }
        }
    }

    func validateRegionKeys(_ region: [String: Any]) throws {
        try rejectUnknownKeys(
            in: region,
            allowed: ["minX", "minY", "maxX", "maxY"]
        )
    }

    func rejectUnknownKeys(
        in object: [String: Any],
        allowed: Set<String>
    ) throws {
        if let unknown = Set(object.keys).subtracting(allowed).sorted().first {
            throw RuleLoaderError.malformedDocument(
                "unknown field: \(unknown)"
            )
        }
    }

    func validateSemantics(_ rules: [AutomationRule]) throws {
        var identifiers: Set<String> = []

        for rule in rules {
            let trimmedID = rule.id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmedID.isEmpty else {
                throw malformed(rule, "id must not be empty")
            }
            guard identifiers.insert(trimmedID).inserted else {
                throw malformed(rule, "id must be unique")
            }
            guard trimmedID == rule.id else {
                throw malformed(
                    rule,
                    "id must not contain leading or trailing whitespace"
                )
            }

            try validateTexts(rule)
            try validateAction(rule)
            try validateRegions(rule)

            guard rule.minimumOCRConfidence.isFinite,
                  (0 ... 1).contains(rule.minimumOCRConfidence) else {
                throw malformed(
                    rule,
                    "minimumOCRConfidence must be between 0 and 1"
                )
            }
            guard rule.stableObservationCount >=
                    RuleSafetyMinimums.stableObservationCount else {
                throw malformed(
                    rule,
                    "stableObservationCount must be at least \(RuleSafetyMinimums.stableObservationCount)"
                )
            }
            guard rule.postActionDelaySeconds.isFinite,
                  rule.postActionDelaySeconds >=
                    RuleSafetyMinimums.postActionDelaySeconds else {
                throw malformed(
                    rule,
                    "postActionDelaySeconds must be at least \(RuleSafetyMinimums.postActionDelaySeconds)"
                )
            }
            guard rule.cooldownSeconds.isFinite,
                  rule.cooldownSeconds >=
                    RuleSafetyMinimums.cooldownSeconds else {
                throw malformed(
                    rule,
                    "cooldownSeconds must be at least \(RuleSafetyMinimums.cooldownSeconds)"
                )
            }
        }
    }

    func validateTexts(_ rule: AutomationRule) throws {
        let texts = rule.requiredTexts + rule.forbiddenTexts
        guard texts.allSatisfy({
            !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }) else {
            throw malformed(rule, "OCR texts must not be empty")
        }
    }

    func validateAction(_ rule: AutomationRule) throws {
        let hasTargetText = rule.action.targetText != nil
        let hasSafePoint = rule.action.safePointRegion != nil
        guard hasTargetText != hasSafePoint else {
            throw malformed(
                rule,
                "action must define exactly one semantic target"
            )
        }

        if let targetText = rule.action.targetText {
            guard !targetText.trimmingCharacters(
                in: .whitespacesAndNewlines
            ).isEmpty else {
                throw malformed(rule, "action targetText must not be empty")
            }
        }

        if let safePoint = rule.action.safePointRegion,
           !isValid(safePoint) {
            throw malformed(
                rule,
                "safePointRegion must be normalized and non-empty"
            )
        }
        if rule.action.safePointRegion != nil,
           rule.requiredTexts.isEmpty {
            throw malformed(
                rule,
                "safePointRegion action requires requiredTexts context"
            )
        }
    }

    func validateRegions(_ rule: AutomationRule) throws {
        guard !rule.regions.entries.isEmpty else {
            throw malformed(rule, "at least one search region is required")
        }

        for (layout, region) in rule.regions.entries {
            guard layout != .unsupported else {
                throw malformed(
                    rule,
                    "unsupported layout cannot define a search region"
                )
            }
            guard isValid(region) else {
                throw malformed(
                    rule,
                    "\(layout.rawValue) search region must be normalized and non-empty"
                )
            }
        }
    }

    func isValid(_ region: NormalizedRegion) -> Bool {
        let values = [region.minX, region.minY, region.maxX, region.maxY]
        return values.allSatisfy { $0.isFinite && (0 ... 1).contains($0) }
            && region.minX < region.maxX
            && region.minY < region.maxY
    }

    func malformed(
        _ rule: AutomationRule,
        _ reason: String
    ) -> RuleLoaderError {
        .malformedSemantics(ruleID: rule.id, reason: reason)
    }
}
