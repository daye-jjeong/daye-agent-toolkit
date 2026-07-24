import BackgroundAutomatorCore
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test(arguments: [
    (AutomationMenuStatus.stopped, "중지됨"),
    (.checkingPreflight, "준비 상태 확인 중"),
    (.needsAttention("권한 필요"), "확인 필요: 권한 필요"),
    (.observing, "화면 확인 중"),
    (.combatWait, "전투 완료 대기 중"),
    (.buttonDetected, "버튼 감지됨"),
    (.waitingForUserIdle, "사용자 입력 대기 중"),
    (.clicking, "클릭 및 화면 복원 중"),
    (.cooldown, "다음 확인 대기 중"),
    (.pausedRestorationFailure, "복원 실패로 일시정지"),
    (.stopping, "안전하게 중지 중"),
])
func menuStatusHasKoreanPresentation(
    status: AutomationMenuStatus,
    expected: String
) {
    #expect(status.koreanDescription == expected)
}

@Test(arguments: [
    (AutomationMenuStatus.stopped, "pause.circle"),
    (.checkingPreflight, "hourglass"),
    (.needsAttention("권한 필요"), "exclamationmark.triangle.fill"),
    (.observing, "eye"),
    (.combatWait, "hourglass"),
    (.buttonDetected, "cursorarrow.rays"),
    (.waitingForUserIdle, "hand.raised"),
    (.clicking, "cursorarrow.click.2"),
    (.cooldown, "clock"),
    (.pausedRestorationFailure, "exclamationmark.triangle.fill"),
    (.stopping, "stop.circle"),
])
func menuStatusMapsToDistinctMenuBarSymbol(
    status: AutomationMenuStatus,
    expected: String
) {
    #expect(status.symbolName == expected)
}

@Test
func idleWaitAndObservingUseDifferentSymbolsSoUserCanTellAtAGlance() {
    // 사용자가 아이콘만 보고 '내가 손 떼길 기다리는 중'과
    // '그냥 관찰 중'을 구분할 수 있어야 한다.
    #expect(
        AutomationMenuStatus.waitingForUserIdle.symbolName
            != AutomationMenuStatus.observing.symbolName
    )
    #expect(
        AutomationMenuStatus.clicking.symbolName
            != AutomationMenuStatus.observing.symbolName
    )
}

@Test
func menuStatusProjectsCoordinatorStates() {
    #expect(
        AutomationMenuStatus.projecting(.stopped) == .stopped
    )
    #expect(
        AutomationMenuStatus.projecting(.unknown) == .observing
    )
    #expect(
        AutomationMenuStatus.projecting(.observing(.running))
            == .combatWait
    )
    #expect(
        AutomationMenuStatus.projecting(
            .cooldown(scene: .running, until: .seconds(100))
        ) == .cooldown
    )
    #expect(
        AutomationMenuStatus.projecting(.pausedRestorationFailure)
            == .pausedRestorationFailure
    )
}

@Test
func pollingScheduleUsesFastAndLongIntervalsWithoutBusySpin() {
    #expect(AutomationPollingSchedule.delay(for: .observing) == .milliseconds(500))
    #expect(AutomationPollingSchedule.delay(for: .buttonDetected) == .milliseconds(500))
    #expect(AutomationPollingSchedule.delay(for: .cooldown) == .seconds(120))
    #expect(AutomationPollingSchedule.delay(for: .combatWait) == .seconds(120))
    #expect(AutomationPollingSchedule.delay(for: .stopped) >= .milliseconds(500))
}

@Test
func lifecycleGateRejectsCompletionFromInvalidatedStart() {
    var gate = AutomationLifecycleGate()
    let staleStart = gate.begin()

    gate.invalidate()
    let restarted = gate.begin()

    #expect(!gate.isCurrent(staleStart))
    #expect(gate.isCurrent(restarted))
}

@Test
func lifecycleGateInvalidatesPendingStartWhenStopped() {
    var gate = AutomationLifecycleGate()
    let pendingStart = gate.begin()

    gate.invalidate()

    #expect(!gate.isCurrent(pendingStart))
}

@Test
func startSessionFreezesTargetAndRestartUsesNewSnapshot() {
    var gate = AutomationLifecycleGate()
    var bundleIdentifier = "com.example.first"
    var exactTitle = "First Window"
    let first = gate.beginStart(
        target: TargetConfiguration(
            bundleIdentifier: bundleIdentifier,
            titleContains: exactTitle
        )
    )

    bundleIdentifier = "com.example.second"
    exactTitle = "Second Window"
    let second = gate.beginStart(
        target: TargetConfiguration(
            bundleIdentifier: bundleIdentifier,
            titleContains: exactTitle
        )
    )

    #expect(first.target.bundleIdentifier == "com.example.first")
    #expect(first.target.titleContains == "First Window")
    #expect(second.target.bundleIdentifier == "com.example.second")
    #expect(second.target.titleContains == "Second Window")
    #expect(!gate.isCurrent(first.token))
    #expect(gate.isCurrent(second.token))
}

@Test(arguments: [
    AutomationMenuStatus.checkingPreflight,
    .observing,
    .combatWait,
    .buttonDetected,
    .waitingForUserIdle,
    .clicking,
    .cooldown,
    .stopping,
])
func targetFieldsStayLockedWhileStartOrRunOwnsSnapshot(
    status: AutomationMenuStatus
) {
    #expect(AutomationTargetFieldPolicy.isLocked(status: status))
}

@Test(arguments: [
    AutomationMenuStatus.stopped,
    .needsAttention("설정 필요"),
])
func targetFieldsUnlockOnlyInSafeEditableStates(
    status: AutomationMenuStatus
) {
    #expect(!AutomationTargetFieldPolicy.isLocked(status: status))
}
