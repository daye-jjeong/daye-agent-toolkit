import Foundation
import Testing

@testable import BackgroundAutomatorCore
@testable import BackgroundAutomatorRuntime

@Test
func decodesPortraitRetryRuleFromBundledDefaults() throws {
    let rules = try RuleLoader().loadDefaultRules()
    let retry = try #require(rules.first { $0.id == "reward_retry" })

    #expect(retry.action.targetText == "다시 하기")
    #expect(retry.regions[.portraitMobile] != nil)
    #expect(retry.stableObservationCount == 2)
}

@Test
func rejectsUnsupportedSchemaVersion() throws {
    let data = try #require(
        """
        {
          "schemaVersion": 2,
          "rules": []
        }
        """.data(using: .utf8)
    )

    #expect(throws: RuleLoaderError.unsupportedSchemaVersion(2)) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsMalformedSemanticAction() throws {
    let data = try #require(
        """
        {
          "schemaVersion": 1,
          "rules": [
            {
              "id": "ambiguous_action",
              "requiredTexts": ["다시 하기"],
              "forbiddenTexts": [],
              "action": {
                "targetText": "다시 하기",
                "safePointRegion": {
                  "minX": 0.30,
                  "minY": 0.70,
                  "maxX": 0.70,
                  "maxY": 0.95
                }
              },
              "regions": {
                "landscape": {
                  "minX": 0.20,
                  "minY": 0.65,
                  "maxX": 0.80,
                  "maxY": 1.00
                }
              },
              "minimumOCRConfidence": 0.8,
              "stableObservationCount": 2,
              "postActionDelaySeconds": 0.5,
              "cooldownSeconds": 2.0
            }
          ]
        }
        """.data(using: .utf8)
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "ambiguous_action",
        reason: "action must define exactly one semantic target"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsOutOfBoundsSearchRegion() throws {
    let data = try #require(
        """
        {
          "schemaVersion": 1,
          "rules": [
            {
              "id": "invalid_region",
              "requiredTexts": ["다시 하기"],
              "forbiddenTexts": [],
              "action": {"targetText": "다시 하기"},
              "regions": {
                "portrait-mobile": {
                  "minX": -0.10,
                  "minY": 0.60,
                  "maxX": 0.90,
                  "maxY": 0.95
                }
              },
              "minimumOCRConfidence": 0.8,
              "stableObservationCount": 2,
              "postActionDelaySeconds": 0.5,
              "cooldownSeconds": 2.0
            }
          ]
        }
        """.data(using: .utf8)
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "invalid_region",
        reason: "portrait-mobile search region must be normalized and non-empty"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsUnknownFieldsForCurrentSchemaVersion() throws {
    let data = try #require(
        """
        {
          "schemaVersion": 1,
          "rules": [],
          "fixedClickCoordinates": {"x": 100, "y": 200}
        }
        """.data(using: .utf8)
    )

    #expect(throws: RuleLoaderError.malformedDocument(
        "unknown field: fixedClickCoordinates"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func exposesApprovedGlobalSafetyMinima() {
    #expect(RuleSafetyMinimums.stableObservationCount == 2)
    #expect(RuleSafetyMinimums.postActionDelaySeconds == 0.1)
    #expect(RuleSafetyMinimums.cooldownSeconds == 0.5)
}

@Test
func rejectsStableObservationCountBelowSafetyMinimum() throws {
    let data = try makeRuleDocument(
        stableObservationCount: 1
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "test_rule",
        reason: "stableObservationCount must be at least 2"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func acceptsStableObservationCountAtSafetyMinimum() throws {
    let data = try makeRuleDocument(
        stableObservationCount: 2
    )

    #expect(try RuleLoader().load(data: data).count == 1)
}

@Test
func rejectsPostActionDelayBelowSafetyMinimum() throws {
    let data = try makeRuleDocument(
        postActionDelaySeconds: 0.099
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "test_rule",
        reason: "postActionDelaySeconds must be at least 0.1"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func acceptsPostActionDelayAtSafetyMinimum() throws {
    let data = try makeRuleDocument(
        postActionDelaySeconds: 0.1
    )

    #expect(try RuleLoader().load(data: data).count == 1)
}

@Test
func rejectsCooldownBelowSafetyMinimum() throws {
    let data = try makeRuleDocument(
        cooldownSeconds: 0.499
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "test_rule",
        reason: "cooldownSeconds must be at least 0.5"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func acceptsCooldownAtSafetyMinimum() throws {
    let data = try makeRuleDocument(
        cooldownSeconds: 0.5
    )

    #expect(try RuleLoader().load(data: data).count == 1)
}

@Test
func rejectsContextFreeSafePointAction() throws {
    let data = try makeRuleDocument(
        requiredTexts: [],
        action: [
            "safePointRegion": validRegion(),
        ]
    )

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: "test_rule",
        reason: "safePointRegion action requires requiredTexts context"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func acceptsContextualSafePointAction() throws {
    let data = try makeRuleDocument(
        requiredTexts: ["던전 클리어", "화면을 터치해 주세요"],
        action: [
            "safePointRegion": validRegion(),
        ]
    )

    let rules = try RuleLoader().load(data: data)

    #expect(rules.first?.action.safePointRegion != nil)
}

@Test
func rejectsRuleIDWithSurroundingWhitespace() throws {
    let data = try makeRuleDocument(id: " test_rule ")

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: " test_rule ",
        reason: "id must not contain leading or trailing whitespace"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsDuplicateCanonicalRuleIDs() throws {
    let first = makeRule(id: "test_rule")
    let second = makeRule(id: " test_rule ")
    let data = try makeRuleDocument(rules: [first, second])

    #expect(throws: RuleLoaderError.malformedSemantics(
        ruleID: " test_rule ",
        reason: "id must be unique"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsUnknownActionField() throws {
    let data = try makeRuleDocument(
        action: [
            "targetText": "다시 하기",
            "fixedClickX": 0.5,
        ]
    )

    #expect(throws: RuleLoaderError.malformedDocument(
        "unknown field: fixedClickX"
    )) {
        try RuleLoader().load(data: data)
    }
}

@Test
func rejectsUnknownRegionField() throws {
    var region = validRegion()
    region["fixedClickY"] = 0.9
    let data = try makeRuleDocument(
        regions: ["landscape": region]
    )

    #expect(throws: RuleLoaderError.malformedDocument(
        "unknown field: fixedClickY"
    )) {
        try RuleLoader().load(data: data)
    }
}

private func validRegion() -> [String: Any] {
    [
        "minX": 0.2,
        "minY": 0.65,
        "maxX": 0.8,
        "maxY": 1.0,
    ]
}

private func makeRule(
    id: String = "test_rule",
    requiredTexts: [String] = ["다시 하기"],
    action: [String: Any] = ["targetText": "다시 하기"],
    regions: [String: Any] = ["landscape": validRegion()],
    stableObservationCount: Int = 2,
    postActionDelaySeconds: Double = 0.1,
    cooldownSeconds: Double = 0.5
) -> [String: Any] {
    [
        "id": id,
        "requiredTexts": requiredTexts,
        "forbiddenTexts": ["장면 넘기기"],
        "action": action,
        "regions": regions,
        "minimumOCRConfidence": 0.8,
        "stableObservationCount": stableObservationCount,
        "postActionDelaySeconds": postActionDelaySeconds,
        "cooldownSeconds": cooldownSeconds,
    ]
}

private func makeRuleDocument(
    id: String = "test_rule",
    requiredTexts: [String] = ["다시 하기"],
    action: [String: Any] = ["targetText": "다시 하기"],
    regions: [String: Any] = ["landscape": validRegion()],
    stableObservationCount: Int = 2,
    postActionDelaySeconds: Double = 0.1,
    cooldownSeconds: Double = 0.5
) throws -> Data {
    try makeRuleDocument(
        rules: [
            makeRule(
                id: id,
                requiredTexts: requiredTexts,
                action: action,
                regions: regions,
                stableObservationCount: stableObservationCount,
                postActionDelaySeconds: postActionDelaySeconds,
                cooldownSeconds: cooldownSeconds
            ),
        ]
    )
}

private func makeRuleDocument(
    rules: [[String: Any]]
) throws -> Data {
    try JSONSerialization.data(
        withJSONObject: [
            "schemaVersion": 1,
            "rules": rules,
        ],
        options: [.sortedKeys]
    )
}
