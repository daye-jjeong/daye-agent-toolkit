import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func clickRecordCarriesPhaseTimingsForSpeedAnalysis() {
    // 실측(2026-07-25, 137판): 한 판 104초 중 89초는 게임 진행 시간이고
    // 앱이 쓰는 시간은 16초다. 그 16초가 관찰·유휴 대기·재관찰·클릭 중
    // 어디에 몰려 있는지 알아야 무엇을 줄일지 정할 수 있다.
    let record = AutomationCoordinator.ClickRecord(
        ruleID: "reward_retry",
        dungeonName: "룬다 1층 2구역",
        phases: ClickPhaseTimings(
            observe: .milliseconds(820),
            idleWait: .milliseconds(1_050),
            reobserve: .milliseconds(760),
            click: .milliseconds(690)
        )
    )

    #expect(record.phases?.observeMilliseconds == 820)
    #expect(record.phases?.idleWaitMilliseconds == 1_050)
    #expect(record.phases?.reobserveMilliseconds == 760)
    #expect(record.phases?.clickMilliseconds == 690)
    // 네 구간을 합치면 클릭 한 번에 든 시간이다.
    #expect(record.phases?.totalMilliseconds == 3_320)
}

@Test
func activityEventKeepsPhaseTimingsInTheLog() throws {
    let event = ActivityEvent(
        at: Date(timeIntervalSince1970: 1_800_000_000),
        outcome: "clicked",
        scene: "reward_retry",
        dungeonName: "룬다 1층 2구역",
        phases: ClickPhaseTimings(
            observe: .milliseconds(820),
            idleWait: .milliseconds(1_050),
            reobserve: .milliseconds(760),
            click: .milliseconds(690)
        )
    )

    let encoder = JSONEncoder()
    encoder.dateEncodingStrategy = .iso8601
    let text = try #require(
        String(data: try encoder.encode(event), encoding: .utf8)
    )

    #expect(text.contains("\"observeMilliseconds\":820"))
    #expect(text.contains("\"idleWaitMilliseconds\":1050"))
    #expect(text.contains("\"reobserveMilliseconds\":760"))
    #expect(text.contains("\"clickMilliseconds\":690"))
}

@Test
func phaseTimingsIgnoreNegativeOrUnfiniteDurations() {
    // 클럭이 뒤로 가거나 측정이 어긋나도 음수 소요가 기록되면 안 된다.
    let phases = ClickPhaseTimings(
        observe: .milliseconds(-5),
        idleWait: .milliseconds(100),
        reobserve: .milliseconds(0),
        click: .milliseconds(50)
    )

    #expect(phases.observeMilliseconds == 0)
    #expect(phases.totalMilliseconds == 150)
}

@Test
func activityEventStaysCompatibleWithLogsWrittenBeforeTimings() throws {
    // 기존 로그(페이즈 없음)도 그대로 읽혀야 한다.
    let line = """
    {"at":"2026-07-25T08:48:22Z","outcome":"clicked",\
    "scene":"reward_retry","dungeonName":"룬다 1층 2구역"}
    """
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .iso8601

    let event = try decoder.decode(
        ActivityEvent.self,
        from: try #require(line.data(using: .utf8))
    )

    #expect(event.scene == "reward_retry")
    #expect(event.phases == nil)
}
