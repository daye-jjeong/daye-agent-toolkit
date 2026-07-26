import Foundation
import Testing

@testable import BackgroundAutomatorCore

@Test
func layoutProfilesUseStableSchemaNames() throws {
    #expect(LayoutProfile.landscape.rawValue == "landscape")
    #expect(LayoutProfile.portraitMobile.rawValue == "portrait-mobile")
    #expect(LayoutProfile.unsupported.rawValue == "unsupported")

    let encoded = try JSONEncoder().encode(LayoutProfile.portraitMobile)
    let decoded = try JSONDecoder().decode(LayoutProfile.self, from: encoded)

    #expect(decoded == .portraitMobile)
}

@Test
func automationRuleRoundTripsSemanticIntent() throws {
    let portraitRegion = NormalizedRegion(
        minX: 0.05,
        minY: 0.72,
        maxX: 0.95,
        maxY: 0.98
    )
    let rule = AutomationRule(
        id: "reward_retry",
        requiredTexts: ["다시 하기"],
        forbiddenTexts: ["장면 넘기기"],
        action: AutomationAction(
            targetText: "다시 하기",
            safePointRegion: nil
        ),
        regions: LayoutRegionMap([
            .landscape: NormalizedRegion(
                minX: 0.25,
                minY: 0.70,
                maxX: 0.75,
                maxY: 0.98
            ),
            .portraitMobile: portraitRegion,
        ]),
        minimumOCRConfidence: 0.80,
        stableObservationCount: 2,
        postActionDelaySeconds: 0.5,
        cooldownSeconds: 2
    )

    let encoded = try JSONEncoder().encode(rule)
    let decoded = try JSONDecoder().decode(AutomationRule.self, from: encoded)

    #expect(decoded == rule)
    #expect(decoded.action.targetText == "다시 하기")
    #expect(decoded.action.safePointRegion == nil)
    #expect(decoded.regions[.portraitMobile] == portraitRegion)
}

@Test
func automationActionCanDescribeASafeSemanticRegion() {
    let safeRegion = NormalizedRegion(
        minX: 0.35,
        minY: 0.65,
        maxX: 0.65,
        maxY: 0.85
    )
    let action = AutomationAction(
        targetText: nil,
        safePointRegion: safeRegion
    )

    #expect(action.targetText == nil)
    #expect(action.safePointRegion == safeRegion)
}
