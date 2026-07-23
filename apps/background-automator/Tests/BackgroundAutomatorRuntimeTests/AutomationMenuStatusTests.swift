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
