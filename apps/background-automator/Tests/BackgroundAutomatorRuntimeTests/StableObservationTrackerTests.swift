import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func oneObservationIsEnoughAtTheApprovedMinimum() throws {
    // 하한이 2 → 1로 내려갔다(2026-07-26). 오클릭을 실제로 막는 건
    // 코디네이터가 클릭 직전에 하는 재확인이고 그건 그대로 남는다.
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )

    let result = tracker.record(
        trackerCandidate(),
        requiredObservationCount: RuleSafetyMinimums.stableObservationCount
    )

    #expect(result != nil)
}

@Test
func trackerStillWithholdsUntilTheRequestedCountIsMet() throws {
    // 규칙이 2를 요구하면 여전히 두 번 봐야 한다 — 하한만 내렸지
    // 안정화 장치 자체를 없앤 게 아니다.
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )

    #expect(
        tracker.record(trackerCandidate(), requiredObservationCount: 2)
            == nil
    )
}

@Test
func twoEquivalentObservationsProduceLatestImmutableCandidate() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let first = trackerCandidate(
        captureSequence: 1,
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let second = trackerCandidate(
        captureSequence: 2,
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
    let portrait = trackerCandidate(captureSequence: 1, layout: .portraitMobile)
    let landscape = trackerCandidate(captureSequence: 2, layout: .landscape)
    let nextLandscape = trackerCandidate(captureSequence: 3, layout: .landscape)

    #expect(tracker.record(portrait, requiredObservationCount: 2) == nil)
    #expect(tracker.record(landscape, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nextLandscape, requiredObservationCount: 2) == nextLandscape)
}

@Test
func changedWindowOrCapturedFrameResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate(captureSequence: 1)
    let movedFrame = trackerCandidate(
        captureSequence: 2,
        window: trackerWindow(
            frame: CGRect(x: 10, y: 0, width: 626, height: 949)
        )
    )
    let replacedWindow = trackerCandidate(
        captureSequence: 3,
        window: trackerWindow(windowID: 99)
    )
    let nextReplacedWindow = trackerCandidate(
        captureSequence: 4,
        window: trackerWindow(windowID: 99)
    )

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(movedFrame, requiredObservationCount: 2) == nil)
    #expect(tracker.record(replacedWindow, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nextReplacedWindow, requiredObservationCount: 2) == nextReplacedWindow)
}

@Test
func changedRuleOrSceneFingerprintResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let first = trackerCandidate(captureSequence: 1)
    let otherRule = trackerCandidate(captureSequence: 2, ruleID: "continue")
    let otherScene = trackerCandidate(
        captureSequence: 3,
        fingerprint: SceneFingerprint(
            semanticTexts: ["계속 하기", "추가 문맥"],
            targetText: "계속 하기"
        )
    )
    let nextOtherScene = trackerCandidate(
        captureSequence: 4,
        fingerprint: otherScene.sceneFingerprint
    )

    #expect(tracker.record(first, requiredObservationCount: 2) == nil)
    #expect(tracker.record(otherRule, requiredObservationCount: 2) == nil)
    #expect(tracker.record(otherScene, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nextOtherScene, requiredObservationCount: 2) == nextOtherScene)
}

@Test
func changingBackgroundTextDoesNotResetStreakForSameButton() throws {
    // 실측(2026-07-24 던전 선택 화면): '순수 전투 시간'이 매초 증가해
    // 화면 전체 텍스트가 매 프레임 달라진다. 같은 버튼(같은 ruleID·위치)
    // 이면 배경 텍스트 변동과 무관하게 안정 관측으로 인정해 클릭해야 한다.
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let firstFrame = trackerCandidate(
        captureSequence: 1,
        fingerprint: SceneFingerprint(
            semanticTexts: ["다시 하기", "순수 전투 시간 0:13"],
            targetText: "다시 하기"
        )
    )
    let secondFrame = trackerCandidate(
        captureSequence: 2,
        fingerprint: SceneFingerprint(
            semanticTexts: ["다시 하기", "순수 전투 시간 0:14"],
            targetText: "다시 하기"
        )
    )

    #expect(
        tracker.record(firstFrame, requiredObservationCount: 2) == nil
    )
    #expect(
        tracker.record(secondFrame, requiredObservationCount: 2)
            == secondFrame
    )
}

@Test
func nilObservationResetsStableStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let candidate = trackerCandidate(captureSequence: 1)
    let secondCandidate = trackerCandidate(captureSequence: 2)
    let thirdCandidate = trackerCandidate(captureSequence: 3)

    #expect(tracker.record(candidate, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nil, requiredObservationCount: 2) == nil)
    #expect(tracker.record(secondCandidate, requiredObservationCount: 2) == nil)
    #expect(tracker.record(thirdCandidate, requiredObservationCount: 2) == thirdCandidate)
}

@Test
func targetRectangleToleranceCoversPositionAndSizeInPixels() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate(
        captureSequence: 1,
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let inside = trackerCandidate(
        captureSequence: 2,
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
        captureSequence: 1,
        targetPixelRect: CGRect(x: 100, y: 200, width: 80, height: 30)
    )
    let changed = trackerCandidate(
        captureSequence: 2,
        targetPixelRect: changedRect
    )
    let nextChanged = trackerCandidate(
        captureSequence: 3,
        targetPixelRect: changedRect
    )

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(changed, requiredObservationCount: 2) == nil)
    #expect(tracker.record(nextChanged, requiredObservationCount: 2) == nextChanged)
}

@Test
func stableCandidateEmitsOnceUntilSceneChangeOrExplicitReset() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let first = trackerCandidate(captureSequence: 1)
    let second = trackerCandidate(captureSequence: 2)
    let third = trackerCandidate(captureSequence: 3)
    // 화면 전환은 다른 버튼(다른 ruleID)으로 나타난다.
    let changed = trackerCandidate(
        captureSequence: 4,
        ruleID: "continue_dialog"
    )
    let changedAgain = trackerCandidate(
        captureSequence: 5,
        ruleID: "continue_dialog"
    )

    #expect(tracker.record(first, requiredObservationCount: 2) == nil)
    #expect(tracker.record(second, requiredObservationCount: 2) == second)
    #expect(tracker.record(third, requiredObservationCount: 2) == nil)
    #expect(tracker.record(changed, requiredObservationCount: 2) == nil)
    #expect(tracker.record(changedAgain, requiredObservationCount: 2) == changedAgain)

    tracker.resetForRetry()
    let retryFirst = trackerCandidate(
        captureSequence: 6,
        ruleID: "continue_dialog"
    )
    let retrySecond = trackerCandidate(
        captureSequence: 7,
        ruleID: "continue_dialog"
    )
    #expect(tracker.record(retryFirst, requiredObservationCount: 2) == nil)
    #expect(tracker.record(retrySecond, requiredObservationCount: 2) == retrySecond)
}

@Test
func theSameButtonIsRetriedWhenTheClickNeverLanded() throws {
    // 걸쇠는 같은 버튼을 두 번 누르지 않으려는 장치다. 클릭이 먹히면 화면이
    // 바뀌므로 정상 흐름에선 문제가 없다. 그런데 클릭이 게임에 안 들어가면
    // 화면이 그대로고, 같은 버튼이 계속 보이니 걸쇠가 영영 안 풀렸다.
    // 실측(2026-07-30 12:33): '발견한 전리품'을 누른 뒤 화면이 안 바뀌어
    // 같은 후보를 계속 거부했고, 사람이 손대야만 풀렸다.
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    var sequence: UInt64 = 1
    func observe() -> ActionCandidate? {
        defer { sequence += 1 }
        return tracker.record(
            trackerCandidate(captureSequence: sequence),
            requiredObservationCount: 1
        )
    }

    // 첫 클릭이 나간다.
    #expect(observe() != nil)
    // 화면이 안 바뀐 채 같은 버튼이 계속 보인다 — 잠시는 참는다.
    #expect(observe() == nil)
    // 충분히 오래 그대로면 클릭이 안 먹힌 것이므로 다시 내보낸다.
    var retried: ActionCandidate?
    for _ in 0 ..< StableObservationTracker.latchRetryObservations {
        if let candidate = observe() {
            retried = candidate
            break
        }
    }
    #expect(retried != nil, "같은 화면이 이어지면 언젠가 다시 눌러야 한다")
}

@Test
func productionToleranceAbsorbsRewardScreenSlide() throws {
    // 실측(2026-07-24): 보상화면 '다시 하기'는 전리품 연출로 프레임 간
    // 최대 35px(y축) 이동한다. 프로덕션 관용도가 이 이동을 흡수해야
    // 애니메이션 중에도 안정 판정이 나 클릭 지연(3~14초)이 사라진다.
    // 다음 버튼과 202px 떨어져 있어 100px 미만이면 오탐 없이 안전하다.
    #expect(AutomationCoordinator.targetRectangleTolerancePixels >= 36)
    #expect(AutomationCoordinator.targetRectangleTolerancePixels <= 100)

    let first = trackerCandidate(
        captureSequence: 1,
        targetPixelRect: CGRect(x: 703, y: 865, width: 104, height: 29)
    )
    let slid = trackerCandidate(
        captureSequence: 2,
        targetPixelRect: CGRect(x: 703, y: 900, width: 104, height: 29)
    )

    // 프로덕션 관용도(50px)로는 35px 이동한 같은 버튼이 안정으로 인정된다.
    var lenient = try StableObservationTracker(
        targetRectangleTolerancePixels:
            AutomationCoordinator.targetRectangleTolerancePixels
    )
    #expect(lenient.record(first, requiredObservationCount: 2) == nil)
    #expect(lenient.record(slid, requiredObservationCount: 2) == slid)

    // 회귀 방어: 기존 2px였다면 35px 이동은 안정 판정을 못 받아 churn한다.
    var strict = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    #expect(strict.record(first, requiredObservationCount: 2) == nil)
    #expect(strict.record(slid, requiredObservationCount: 2) == nil)
}

@Test
func reusedPIDAndWindowIDWithDifferentProcessLifetimeResetsStreak() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )
    let original = trackerCandidate(
        captureSequence: 1,
        window: trackerWindow(launchTime: 1_000)
    )
    let relaunched = trackerCandidate(
        captureSequence: 2,
        window: trackerWindow(launchTime: 2_000)
    )
    let relaunchedAgain = trackerCandidate(
        captureSequence: 3,
        window: trackerWindow(launchTime: 2_000)
    )

    #expect(tracker.record(original, requiredObservationCount: 2) == nil)
    #expect(tracker.record(relaunched, requiredObservationCount: 2) == nil)
    #expect(tracker.record(relaunchedAgain, requiredObservationCount: 2) == relaunchedAgain)
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

@Test
func captureIdentityRejectsZeroAndOrdersOnlyWithinOneSession() throws {
    #expect(throws: CaptureIdentityError.invalidSequence) {
        try CaptureIdentity(
            sessionID: trackerCaptureSessionID,
            sequence: 0
        )
    }

    let first = try CaptureIdentity(
        sessionID: trackerCaptureSessionID,
        sequence: 1
    )
    let second = try CaptureIdentity(
        sessionID: trackerCaptureSessionID,
        sequence: 2
    )
    let restarted = try CaptureIdentity(
        sessionID: UUID(
            uuidString: "AAAAAAAA-1111-2222-3333-BBBBBBBBBBBB"
        )!,
        sequence: 3
    )

    #expect(second.isStrictlyNewer(than: first))
    #expect(!first.isStrictlyNewer(than: second))
    #expect(!first.isStrictlyNewer(than: first))
    #expect(!restarted.isStrictlyNewer(than: first))
}

@Test
func duplicateOrOlderCaptureDoesNotAdvanceStability() throws {
    var tracker = try StableObservationTracker(
        targetRectangleTolerancePixels: 2
    )

    #expect(tracker.record(
        trackerCandidate(captureSequence: 2),
        requiredObservationCount: 2
    ) == nil)
    #expect(tracker.record(
        trackerCandidate(captureSequence: 2),
        requiredObservationCount: 2
    ) == nil)
    #expect(tracker.record(
        trackerCandidate(captureSequence: 1),
        requiredObservationCount: 2
    ) == nil)
    #expect(tracker.record(
        trackerCandidate(captureSequence: 3),
        requiredObservationCount: 2
    ) == nil)
    #expect(tracker.record(
        trackerCandidate(captureSequence: 4),
        requiredObservationCount: 2
    ) != nil)
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
            captureIdentity: try CaptureIdentity(
                sessionID: trackerCaptureSessionID,
                sequence: 1
            ),
            targetPixelRect: rect
        )
    }
}

private func trackerCandidate(
    captureSequence: UInt64 = 1,
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
        captureIdentity: try! CaptureIdentity(
            sessionID: trackerCaptureSessionID,
            sequence: captureSequence
        ),
        targetPixelRect: targetPixelRect
    )
}

private func trackerWindow(
    windowID: UInt32 = 7,
    frame: CGRect = CGRect(x: 0, y: 0, width: 626, height: 949),
    launchTime: Double = 1_000
) -> WindowCandidate {
    WindowCandidate(
        windowID: windowID,
        processID: 42,
        bundleIdentifier: "com.example.game",
        title: "Mabinogi Mobile",
        frame: frame,
        isOnScreen: true,
        processLifetimeIdentity: try! ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: launchTime
        )
    )
}

private let trackerCaptureSessionID = UUID(
    uuidString: "99999999-8888-7777-6666-555555555555"
)!
