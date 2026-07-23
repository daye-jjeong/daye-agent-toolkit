import BackgroundAutomatorCore
import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func oneStableObservationIsInsufficient() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )

    let result = tracker.record(
        trackerCandidate(),
        requiredObservationCount: RuleSafetyMinimums.stableObservationCount
    )

    #expect(result == nil)
}

@Test
func twoEquivalentObservationsProduceLatestImmutableCandidate() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let first = trackerCandidate(
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let second = trackerCandidate(
        targetPixelRect: CGRect(x: 101, y: 199, width: 81, height: 31)
    )

    #expect(tracker.record(first, requiredObservationCount: 2) == nil)
    let result = tracker.record(second, requiredObservationCount: 2)

    #expect(result == second)
}

@Test
func changedLayoutResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let portrait = trackerCandidate(layout: .portraitMobile)
    let landscape = trackerCandidate(layout: .landscape)

    #expect(tracker.record(portrait, requiredObservationCount: 2) == nil)
    #expect(tracker.record(landscape, requiredObservationCount: 2) == nil)
    #expect(tracker.record(landscape, requiredObservationCount: 2) == landscape)
}

@Test
func changedWindowOrCapturedFrameResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate()
    let movedFrame = trackerCandidate(
        window: trackerWindow(
            frame: CGRect(x: 10, y: 0, width: 626, height: 949)
        )
    )
    let replacedWindow = trackerCandidate(
        window: trackerWindow(windowID: 99)
    )

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(movedFrame, requiredObservationCount: 2) == nil)
    #expect(tracker.record(replacedWindow, requiredObservationCount: 2) == nil)
    #expect(tracker.record(replacedWindow, requiredObservationCount: 2) == replacedWindow)
}

@Test
func changedRuleOrSceneFingerprintResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let first = trackerCandidate()
    let otherRule = trackerCandidate(ruleID: "continue")
    let otherScene = trackerCandidate(
        fingerprint: SceneFingerprint(
            semanticTexts: ["계속 하기", "추가 문맥"],
            targetText: "계속 하기"
        )
    )

    #expect(tracker.record(first, requiredObservationCount: 2) == nil)
    #expect(tracker.record(otherRule, requiredObservationCount: 2) == nil)
    #expect(tracker.record(otherScene, requiredObservationCount: 2) == nil)
    #expect(tracker.record(otherScene, requiredObservationCount: 2) == otherScene)
}

@Test
func nilObservationResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let candidate = trackerCandidate()

    #expect(tracker.record(candidate, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nil, requiredObservationCount: 2) == nil)
    #expect(tracker.record(candidate, requiredObservationCount: 2) == nil)
    #expect(tracker.record(candidate, requiredObservationCount: 2) == candidate)
}

@Test
func targetRectangleToleranceCoversPositionAndSizeInPixels() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate(
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let inside = trackerCandidate(
        targetPixelRect: CGRect(x: 102, y: 198, width: 82, height: 28)
    )

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(inside, requiredObservationCount: 2) == inside)
}

@Test(arguments: [
    CGRect(x: 102.01, y: 200, width: 80, height: 30),
    CGRect(x: 100, y: 197.99, width: 80, height: 30),
    CGRect(x: 100, y: 200, width: 82.01, height: 30),
    CGRect(x: 100, y: 200, width: 80, height: 27.99),
])
func targetRectangleOutsideToleranceResetsStreak(changedRect: CGRect) throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate(
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let changed = trackerCandidate(targetPixelRect: changedRect)

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(changed, requiredObservationCount: 2) == nil)
    #expect(tracker.record(changed, requiredObservationCount: 2) == changed)
}

@Test(arguments: [
    -1,
    Double.nan,
    Double.infinity,
])
func invalidTargetRectangleToleranceIsRejected(tolerance: Double) {
    #expect(throws: StableObservationTrackerError.invalidTargetRectangleTolerance) {
        try StableObservationTracker(
            targetRectangleTolerancePixels: tolerance
        )
    }
}

@Test(arguments: [
    CGRect(x: CGFloat.nan, y: 10, width: 20, height: 10),
    CGRect(x: 10, y: CGFloat.infinity, width: 20, height: 10),
    CGRect(x: 10, y: 10, width: 0, height: 10),
    CGRect(x: 10, y: 10, width: 20, height: -1),
])
func malformedTargetRectanglesAreRejected(rect: CGRect) {
    #expect(throws: ActionCandidateError.invalidTargetPixelRect) {
        try ActionCandidate(
            ruleID: "retry",
            windowIdentity: trackerWindow(),
            layout: .portraitMobile,
            sceneFingerprint: SceneFingerprint(
                semanticTexts: ["다시 하기"],
                targetText: "다시 하기"
            ),
            targetPixelRect: rect
        )
    }
}

private func trackerCandidate(
    ruleID: String = "retry",
    window: WindowCandidate = trackerWindow(),
    layout: LayoutProfile = .portraitMobile,
    fingerprint: SceneFingerprint = SceneFingerprint(
        semanticTexts: ["다시 하기"],
        targetText: "다시 하기"
    ),
    targetPixelRect: CGRect = CGRect(x: 100, y: 200, width: 80, height: 30)
) -> ActionCandidate {
    try! ActionCandidate(
        ruleID: ruleID,
        windowIdentity: window,
        layout: layout,
        sceneFingerprint: fingerprint,
        targetPixelRect: targetPixelRect
    )
}

private func trackerWindow(
    windowID: UInt32 = 7,
    frame: CGRect = CGRect(x: 0, y: 0, width: 626, height: 949)
) -> WindowCandidate {
    WindowCandidate(
        windowID: windowID,
        processID: 42,
        bundleIdentifier: "com.example.game",
        title: "Mabinogi Mobile",
        frame: frame,
        isOnScreen: true
    )
}
