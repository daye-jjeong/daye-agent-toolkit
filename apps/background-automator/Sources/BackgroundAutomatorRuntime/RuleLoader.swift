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
    public static let postActionDelaySeconds = 0.5
    public static let cooldownSeconds = 0.5

    private init() {}
}

public enum BackgroundAutomatorPaths {
    public static let supportDirectoryName = "BackgroundAutomator"
    public static let overrideRulesFileName = "rules.json"

    public static func supportDirectory(
        fileManager: FileManager = .default
    ) -> URL? {
        fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first?.appendingPathComponent(
            supportDirectoryName,
            isDirectory: true
        )
    }

    public static func overrideRulesURL(
        fileManager: FileManager = .default
    ) -> URL? {
        supportDirectory(fileManager: fileManager)?
            .appendingPathComponent(overrideRulesFileName)
    }
}

struct DefaultRuleResourceContext: Sendable {
    let isPackagedApplication: Bool
    let applicationResourceRoot: URL?
    let developmentFallbackURL: URL?
    let overrideURL: URL?

    init(
        isPackagedApplication: Bool,
        applicationResourceRoot: URL?,
        developmentFallbackURL: URL?,
        overrideURL: URL? = nil
    ) {
        self.isPackagedApplication = isPackagedApplication
        self.applicationResourceRoot = applicationResourceRoot
        self.developmentFallbackURL = developmentFallbackURL
        self.overrideURL = overrideURL
    }
}

public struct RuleLoader: Sendable {
    public static let supportedSchemaVersion = 1
    static let runtimeResourceBundleName =
        "BackgroundAutomator_BackgroundAutomatorRuntime.bundle"

    public init() {}

    /// 임무를 그대로 두고 들어가 전리품을 두 배로 받는 규칙(은동전 10개 소모).
    static let silverCoinRuleID = "enter_with_coin"
    /// 임무를 해제해 은동전을 아끼는 규칙.
    static let silverCoinFreeRuleID = "deselect_double_loot"

    /// - Parameter usesSilverCoin: 켜면 임무를 그대로 두고 들어가 전리품을
    ///   두 배로 받고(은동전 10개 소모), 끄면 임무를 해제해 아낀다.
    ///   두 규칙은 같은 화면에 반응하므로 하나만 남긴다 — 둘 다 두면
    ///   후보가 겹쳐 자동화가 모호성으로 멈춘다.
    public func loadDefaultRules(
        usesSilverCoin: Bool = false
    ) throws -> [AutomationRule] {
        let mainBundle = Bundle.main
        let overrideURL = BackgroundAutomatorPaths.overrideRulesURL()
        let context = Self.isPackagedApplication(mainBundle)
            ? DefaultRuleResourceContext(
                isPackagedApplication: true,
                applicationResourceRoot: mainBundle.resourceURL,
                developmentFallbackURL: nil,
                overrideURL: overrideURL
            )
            : DefaultRuleResourceContext(
                isPackagedApplication: false,
                applicationResourceRoot: mainBundle.resourceURL,
                developmentFallbackURL: Bundle.module.url(
                    forResource: "default-rules",
                    withExtension: "json"
                ),
                overrideURL: overrideURL
            )
        return Self.applyingSilverCoinChoice(
            try loadDefaultRules(context: context),
            usesSilverCoin: usesSilverCoin
        )
    }

    static func applyingSilverCoinChoice(
        _ rules: [AutomationRule],
        usesSilverCoin: Bool
    ) -> [AutomationRule] {
        let excluded = usesSilverCoin
            ? silverCoinFreeRuleID
            : silverCoinRuleID
        return rules.filter { $0.id != excluded }
    }

    func loadDefaultRules(resourceRoot: URL) throws -> [AutomationRule] {
        try loadDefaultRules(
            context: DefaultRuleResourceContext(
                isPackagedApplication: true,
                applicationResourceRoot: resourceRoot,
                developmentFallbackURL: nil
            )
        )
    }

    func loadDefaultRules(
        context: DefaultRuleResourceContext
    ) throws -> [AutomationRule] {
        // 로컬 오버라이드 우선: 존재하면 그대로 로드하고, 손상됐으면
        // 조용히 기본값으로 내려가지 않고 오류를 던진다(오탐 방지).
        if
            let overrideURL = context.overrideURL,
            FileManager.default.fileExists(atPath: overrideURL.path)
        {
            return try load(data: Data(contentsOf: overrideURL))
        }

        if
            let resourceRoot = context.applicationResourceRoot,
            let packagedURL = packagedRulesURL(
                resourceRoot: resourceRoot
            )
        {
            return try load(data: Data(contentsOf: packagedURL))
        }

        guard
            !context.isPackagedApplication,
            let fallbackURL = context.developmentFallbackURL
        else {
            throw RuleLoaderError.resourceNotFound
        }

        return try load(data: Data(contentsOf: fallbackURL))
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
    static func isPackagedApplication(_ bundle: Bundle) -> Bool {
        if bundle.bundleURL.pathExtension
            .caseInsensitiveCompare("app") == .orderedSame
        {
            return true
        }

        return bundle.object(
            forInfoDictionaryKey: "CFBundlePackageType"
        ) as? String == "APPL"
    }

    func packagedRulesURL(resourceRoot: URL) -> URL? {
        let url = resourceRoot
            .appendingPathComponent(
                Self.runtimeResourceBundleName,
                isDirectory: true
            )
            .appendingPathComponent("default-rules.json")

        return FileManager.default.fileExists(atPath: url.path)
            ? url
            : nil
    }

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
                    "appearance",
                    "minimumOCRConfidence",
                    "stableObservationCount",
                    "postActionDelaySeconds",
                    "cooldownSeconds",
                ]
            )

            if let action = rule["action"] as? [String: Any] {
                try rejectUnknownKeys(
                    in: action,
                    allowed: [
                        "targetText",
                        "safePointRegion",
                        "targetTextSuffix",
                        "targetBelowText",
                    ]
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

            if let appearance = rule["appearance"] as? [String: Any] {
                try rejectUnknownKeys(
                    in: appearance,
                    allowed: [
                        "contextText",
                        "contextRegions",
                        "contextRange",
                        "targetRange",
                    ]
                )
                if let contextRegions =
                    appearance["contextRegions"] as? [String: Any]
                {
                    for value in contextRegions.values {
                        guard let region = value as? [String: Any] else {
                            throw RuleLoaderError.malformedDocument(
                                "appearance context region must be an object"
                            )
                        }
                        try validateRegionKeys(region)
                    }
                }
                for key in ["contextRange", "targetRange"] {
                    if let range = appearance[key] as? [String: Any] {
                        try rejectUnknownKeys(
                            in: range,
                            allowed: [
                                "minimumSaturation",
                                "maximumSaturation",
                                "minimumLuminance",
                                "maximumLuminance",
                            ]
                        )
                    }
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
        do {
            try AutomationRuleValidator.validate(rules)
        } catch let error as AutomationRuleValidationError {
            switch error {
            case let .duplicateRuleID(ruleID):
                throw RuleLoaderError.malformedSemantics(
                    ruleID: ruleID,
                    reason: "id must be unique"
                )
            case let .malformed(ruleID, reason):
                throw RuleLoaderError.malformedSemantics(
                    ruleID: ruleID,
                    reason: reason
                )
            }
        }
    }
}

enum AutomationRuleValidationError: Error, Equatable, Sendable {
    case duplicateRuleID(String)
    case malformed(ruleID: String, reason: String)
}

enum AutomationRuleValidator {
    static func validate(_ rules: [AutomationRule]) throws {
        var identifiers: Set<String> = []

        for rule in rules {
            let trimmedID = rule.id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmedID.isEmpty else {
                throw malformed(rule, "id must not be empty")
            }
            guard identifiers.insert(trimmedID).inserted else {
                throw AutomationRuleValidationError
                    .duplicateRuleID(rule.id)
            }
            guard trimmedID == rule.id else {
                throw malformed(
                    rule,
                    "id must not contain leading or trailing whitespace"
                )
            }

            try Self.validateTexts(rule)
            try Self.validateAction(rule)
            try Self.validateRegions(rule)
            try Self.validateAppearance(rule)

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

    private static func validateTexts(_ rule: AutomationRule) throws {
        let texts = rule.requiredTexts + rule.forbiddenTexts
        guard texts.allSatisfy({
            !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }) else {
            throw malformed(rule, "OCR texts must not be empty")
        }
    }

    private static func validateAction(_ rule: AutomationRule) throws {
        let hasTargetText = rule.action.targetText != nil
        let hasSafePoint = rule.action.safePointRegion != nil
        if !hasTargetText, !hasSafePoint, rule.id == "running" {
            guard !rule.requiredTexts.isEmpty else {
                throw malformed(
                    rule,
                    "running detector requires requiredTexts context"
                )
            }
            return
        }
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
           !Self.isValid(safePoint) {
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

    private static func validateRegions(_ rule: AutomationRule) throws {
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
            guard Self.isValid(region) else {
                throw malformed(
                    rule,
                    "\(layout.rawValue) search region must be normalized and non-empty"
                )
            }
        }
    }

    private static func validateAppearance(
        _ rule: AutomationRule
    ) throws {
        guard let appearance = rule.appearance else {
            return
        }
        guard rule.action.targetText != nil else {
            throw malformed(
                rule,
                "appearance constraint requires a text target action"
            )
        }
        guard !appearance.contextText.trimmingCharacters(
            in: .whitespacesAndNewlines
        ).isEmpty else {
            throw malformed(
                rule,
                "appearance contextText must not be empty"
            )
        }
        guard Self.isValid(appearance.contextRange) else {
            throw malformed(
                rule,
                "appearance context range must use normalized coherent bounds"
            )
        }
        guard Self.isValid(appearance.targetRange) else {
            throw malformed(
                rule,
                "appearance target range must use normalized coherent bounds"
            )
        }
        guard
            Set(rule.regions.entries.keys).isSubset(
                of: Set(appearance.contextRegions.entries.keys)
            )
        else {
            throw malformed(
                rule,
                "appearance context region is required for every action layout"
            )
        }
        for (layout, region) in appearance.contextRegions.entries {
            guard layout != .unsupported, Self.isValid(region) else {
                throw malformed(
                    rule,
                    "\(layout.rawValue) appearance context region must be normalized and non-empty"
                )
            }
        }
    }

    private static func isValid(
        _ range: AppearanceRange
    ) -> Bool {
        let values = [
            range.minimumSaturation,
            range.maximumSaturation,
            range.minimumLuminance,
            range.maximumLuminance,
        ]
        return values.allSatisfy {
            $0.isFinite && (0 ... 1).contains($0)
        }
            && range.minimumSaturation <= range.maximumSaturation
            && range.minimumLuminance <= range.maximumLuminance
    }

    private static func isValid(_ region: NormalizedRegion) -> Bool {
        let values = [region.minX, region.minY, region.maxX, region.maxY]
        return values.allSatisfy { $0.isFinite && (0 ... 1).contains($0) }
            && region.minX < region.maxX
            && region.minY < region.maxY
    }

    private static func malformed(
        _ rule: AutomationRule,
        _ reason: String
    ) -> AutomationRuleValidationError {
        .malformed(ruleID: rule.id, reason: reason)
    }
}
