import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

// MARK: - BuildIdentity

@Test
func missingBuildStampReadsAsDevelopment() {
    // `swift run`이나 스탬프를 찍지 않은 번들. 개발 중에 남은 기록이
    // 배포 빌드 통계에 섞이면 비교가 오염된다.
    #expect(BuildIdentity(infoDictionary: nil).id == "dev")
    #expect(BuildIdentity(infoDictionary: [:]).id == "dev")
    #expect(
        BuildIdentity(
            infoDictionary: [BuildIdentity.identifierKey: ""]
        ).id == "dev"
    )
}

@Test
func buildStampCarriesIdentifierAndSummary() {
    let identity = BuildIdentity(infoDictionary: [
        BuildIdentity.identifierKey: "a81ec70-0726T1558",
        BuildIdentity.summaryKey: "OCR 3→2회; 관찰 주기 2s→1.2s",
    ])

    #expect(identity.id == "a81ec70-0726T1558")
    #expect(identity.summary == "OCR 3→2회; 관찰 주기 2s→1.2s")
}

@Test
func blankSummaryIsDroppedRatherThanKeptAsEmptyText() {
    // 커밋 제목을 못 읽으면 빈 문자열이 온다. 비교표에 빈칸을 남기느니
    // '없음'으로 두는 편이 읽기 쉽다.
    let identity = BuildIdentity(infoDictionary: [
        BuildIdentity.identifierKey: "a81ec70-0726T1558",
        BuildIdentity.summaryKey: "   ",
    ])

    #expect(identity.summary == nil)
}

// MARK: - BuildLogWriter

@Test
func buildLogRecordsEachBuildOnlyOnce() throws {
    let directory = uniqueBuildDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = BuildLogWriter(directory: directory)
    let identity = BuildIdentity(
        id: "a81ec70-0726T1558",
        summary: "OCR 3→2회"
    )

    // 앱은 켤 때마다 기록을 시도한다. 하루에 몇 번을 켜도 빌드가 같으면
    // 한 줄이어야 조인 결과가 흔들리지 않는다.
    #expect(
        try writer.recordIfNeeded(
            identity,
            at: Date(timeIntervalSince1970: 1_800_000_000)
        )
    )
    #expect(
        try !writer.recordIfNeeded(
            identity,
            at: Date(timeIntervalSince1970: 1_800_003_600)
        )
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            BuildLogWriter.fileName
        ),
        encoding: .utf8
    )
    #expect(text.split(separator: "\n").count == 1)
    #expect(text.contains("a81ec70-0726T1558"))
    #expect(text.contains("OCR 3→2회"))
}

@Test
func buildLogAppendsWhenTheBuildChanges() throws {
    let directory = uniqueBuildDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = BuildLogWriter(directory: directory)

    #expect(
        try writer.recordIfNeeded(
            BuildIdentity(id: "5ce514d-0726T1430", summary: "리뷰 수정"),
            at: Date(timeIntervalSince1970: 1_800_000_000)
        )
    )
    #expect(
        try BuildLogWriter(directory: directory).recordIfNeeded(
            BuildIdentity(id: "a81ec70-0726T1558", summary: "OCR 3→2회"),
            at: Date(timeIntervalSince1970: 1_800_003_600)
        )
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            BuildLogWriter.fileName
        ),
        encoding: .utf8
    )
    #expect(text.split(separator: "\n").count == 2)
}

// MARK: - 기록에 찍히는 빌드

@Test
func activityLogStampsTheRunningBuild() throws {
    let directory = uniqueBuildDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = ActivityLogWriter(
        directory: directory,
        build: "a81ec70-0726T1558"
    )

    try writer.append(
        ActivityEvent(
            at: Date(timeIntervalSince1970: 1_753_000_000),
            outcome: "clicked",
            scene: "clear_touch",
            dungeonName: nil
        )
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            ActivityLogWriter.fileName
        ),
        encoding: .utf8
    )
    #expect(text.contains("\"build\":\"a81ec70-0726T1558\""))
}

@Test
func cycleLogStampsTheRunningBuild() throws {
    let directory = uniqueBuildDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(
        directory: directory,
        build: "a81ec70-0726T1558"
    )

    try writer.append(
        CycleRecord(
            at: Date(timeIntervalSince1970: 1_800_000_000),
            dungeon: "룬다 1층 2구역",
            combatSeconds: 13,
            items: ["골드"]
        )
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            CycleLogWriter.fileName
        ),
        encoding: .utf8
    )
    #expect(text.contains("\"build\":\"a81ec70-0726T1558\""))
}

@Test
func recordsWrittenBeforeBuildStampingStillCount() throws {
    // 디스크에는 이미 build 필드 없는 기록이 250판 넘게 쌓여 있다.
    // 필드를 더한 뒤 그 줄들이 디코딩에서 탈락하면 과거 기록을 통째로 잃는다.
    let directory = uniqueBuildDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }
    try FileManager.default.createDirectory(
        at: directory,
        withIntermediateDirectories: true
    )
    try """
    {"at":"2026-07-25T05:00:00Z","dungeon":"룬다 1층 2구역","combatSeconds":13,"items":["골드"]}
    {"at":"2026-07-25T05:02:00Z","dungeon":"알비 던전","combatSeconds":21,"items":[]}

    """.write(
        to: directory.appendingPathComponent(CycleLogWriter.fileName),
        atomically: true,
        encoding: .utf8
    )

    let summary = try CycleLogWriter(directory: directory).summary()

    #expect(summary.totalCycles == 2)
    #expect(summary.byDungeon["룬다 1층 2구역"] == 1)
}

// MARK: - Helpers

private func uniqueBuildDirectory() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent("build-identity-\(UUID().uuidString)")
}
