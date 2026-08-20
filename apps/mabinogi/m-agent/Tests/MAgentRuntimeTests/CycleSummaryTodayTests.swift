import Foundation
import Testing

@testable import MAgentRuntime

@Test
func cycleSummaryCountsTodaySeparatelyFromTotal() throws {
    let directory = try makeCycleSummaryDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }

    let writer = CycleLogWriter(directory: directory)
    let now = Date(timeIntervalSince1970: 1_785_030_000) // 2026-07-26 KST 낮
    let yesterday = now.addingTimeInterval(-60 * 60 * 30)
    for at in [yesterday, yesterday, now, now, now] {
        try writer.append(
            CycleRecord(
                at: at,
                dungeon: "룬다 1층 2구역",
                combatSeconds: 16,
                items: []
            )
        )
    }

    let summary = try writer.summary(now: now)
    #expect(summary.totalCycles == 5)
    #expect(summary.todayCycles == 3)
}

@Test
func cycleSummaryUsesLocalCalendarDayBoundary() throws {
    let directory = try makeCycleSummaryDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }

    // 파밍은 자정을 넘겨 이어진다. 어제 23:50과 오늘 00:10은 다른 날이다.
    let writer = CycleLogWriter(directory: directory)
    let calendar = Calendar.current
    let today = calendar.startOfDay(
        for: Date(timeIntervalSince1970: 1_785_030_000)
    )
    try writer.append(
        CycleRecord(
            at: today.addingTimeInterval(-600),
            dungeon: nil,
            combatSeconds: nil,
            items: []
        )
    )
    try writer.append(
        CycleRecord(
            at: today.addingTimeInterval(600),
            dungeon: nil,
            combatSeconds: nil,
            items: []
        )
    )

    let summary = try writer.summary(
        now: today.addingTimeInterval(3600)
    )
    #expect(summary.totalCycles == 2)
    #expect(summary.todayCycles == 1)
}

@Test
func emptyCycleLogHasNoCyclesToday() throws {
    let directory = try makeCycleSummaryDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }

    let summary = try CycleLogWriter(directory: directory).summary()
    #expect(summary.totalCycles == 0)
    #expect(summary.todayCycles == 0)
}

private func makeCycleSummaryDirectory() throws -> URL {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("cycle-summary-\(UUID().uuidString)")
    try FileManager.default.createDirectory(
        at: directory,
        withIntermediateDirectories: true
    )
    return directory
}
