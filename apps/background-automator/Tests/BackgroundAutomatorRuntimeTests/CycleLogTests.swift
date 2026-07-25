import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func cycleLogAppendsOneJSONLineWithCycleFields() throws {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("cycle-log-append-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)

    try writer.append(
        CycleRecord(
            at: Date(timeIntervalSince1970: 1_800_000_000),
            dungeon: "룬다 1층 2구역",
            combatSeconds: 13,
            items: ["골드", "조각난 흑요석"]
        )
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            CycleLogWriter.fileName
        ),
        encoding: .utf8
    )
    let lines = text.split(separator: "\n")
    #expect(lines.count == 1)
    #expect(text.contains("\"dungeon\":\"룬다 1층 2구역\""))
    #expect(text.contains("\"combatSeconds\":13"))
    #expect(text.contains("조각난 흑요석"))
}

@Test
func cycleLogSummaryCountsRunsPerDungeon() throws {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("cycle-log-summary-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)
    let now = Date(timeIntervalSince1970: 1_800_000_000)

    try writer.append(
        CycleRecord(at: now, dungeon: "룬다", combatSeconds: 13, items: ["골드"])
    )
    try writer.append(
        CycleRecord(at: now, dungeon: "룬다", combatSeconds: 15, items: [])
    )
    try writer.append(
        CycleRecord(at: now, dungeon: "피오드", combatSeconds: 20, items: [])
    )

    let summary = try writer.summary()

    #expect(summary.totalCycles == 3)
    #expect(summary.byDungeon["룬다"] == 2)
    #expect(summary.byDungeon["피오드"] == 1)
}

@Test
func cycleLogSummaryIsEmptyBeforeAnyCycle() throws {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("cycle-log-empty-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }

    let summary = try CycleLogWriter(directory: directory).summary()

    #expect(summary.totalCycles == 0)
    #expect(summary.byDungeon.isEmpty)
}
