import Foundation
import Testing

@testable import MAgentRuntime

/// '오늘 몇 판'만으로는 얼마나 붙잡고 있었는지 모른다. 가동 시간은 이번에
/// 시작한 뒤부터라, 중간에 멈췄다 다시 켜면 0으로 돌아간다.

@Test
func todayActiveTimeSumsTheGapsBetweenConsecutiveCycles() throws {
    let directory = uniqueActiveDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)
    let noon = Date(timeIntervalSince1970: 1_800_000_000)

    // 120초 간격으로 네 판.
    for step in 0 ..< 4 {
        try writer.append(
            CycleRecord(
                at: noon.addingTimeInterval(Double(step) * 120),
                dungeon: "룬다 1층 2구역",
                combatSeconds: 16,
                items: []
            )
        )
    }

    let summary = try writer.summary(
        now: noon.addingTimeInterval(400),
        calendar: calendarForTest()
    )

    #expect(summary.todayCycles == 4)
    #expect(summary.todayActiveSeconds == 360)
}

@Test
func longBreaksAreNotCountedAsFarmingTime() throws {
    // 자리를 비운 두 시간까지 '돌린 시간'에 넣으면 시간당 판 수가 거짓이 된다.
    let directory = uniqueActiveDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)
    let noon = Date(timeIntervalSince1970: 1_800_000_000)

    for offset in [0.0, 120.0, 240.0, 7_440.0, 7_560.0] {
        try writer.append(
            CycleRecord(
                at: noon.addingTimeInterval(offset),
                dungeon: "룬다 1층 2구역",
                combatSeconds: 16,
                items: []
            )
        )
    }

    let summary = try writer.summary(
        now: noon.addingTimeInterval(7_600),
        calendar: calendarForTest()
    )

    // 240초(앞 세 판) + 120초(뒤 두 판). 두 시간의 공백은 빠진다.
    #expect(summary.todayActiveSeconds == 360)
}

@Test
func yesterdayDoesNotLeakIntoTodaysActiveTime() throws {
    let directory = uniqueActiveDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)
    let noon = Date(timeIntervalSince1970: 1_800_000_000)

    for offset in [-86_400.0, -86_280.0, 0.0, 120.0] {
        try writer.append(
            CycleRecord(
                at: noon.addingTimeInterval(offset),
                dungeon: "룬다 1층 2구역",
                combatSeconds: 16,
                items: []
            )
        )
    }

    let summary = try writer.summary(
        now: noon.addingTimeInterval(200),
        calendar: calendarForTest()
    )

    #expect(summary.todayCycles == 2)
    #expect(summary.todayActiveSeconds == 120)
}

@Test
func aSingleCycleHasNoMeasurableSpan() throws {
    let directory = uniqueActiveDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)
    let noon = Date(timeIntervalSince1970: 1_800_000_000)

    try writer.append(
        CycleRecord(at: noon, dungeon: nil, combatSeconds: nil, items: [])
    )

    let summary = try writer.summary(
        now: noon.addingTimeInterval(60),
        calendar: calendarForTest()
    )

    #expect(summary.todayActiveSeconds == 0)
}

private func uniqueActiveDirectory() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent("today-active-\(UUID().uuidString)")
}

private func calendarForTest() -> Calendar {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    return calendar
}
