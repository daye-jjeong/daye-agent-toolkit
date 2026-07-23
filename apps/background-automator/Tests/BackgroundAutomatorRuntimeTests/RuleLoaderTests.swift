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
