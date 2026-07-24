import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

// MARK: - DungeonNameExtractor

@Test
func extractsDungeonNameFromLiveResultScreenTopCenter() {
    // 실측(2026-07-24 선택 화면, 1512×949): 난이도 '어려움'(conf 0.50)과
    // '순수 전투 시간'은 걸러지고 '룬다 1층 2구역'(conf 1.0)만 남아야 한다.
    let texts = [
        liveText("어려움", conf: 0.50, nx: 0.499, ny: 0.251),
        liveText("룬다 1층 2구역", conf: 1.0, nx: 0.499, ny: 0.283),
        liveText("• 순수 전투 시간 0:26", conf: 1.0, nx: 0.499, ny: 0.321),
        liveText("발견한 전리품", conf: 0.50, nx: 0.500, ny: 0.473),
        liveText("마비노기 모바일", conf: 1.0, nx: 0.082, ny: 0.017),
    ]

    let name = DungeonNameExtractor.extract(
        from: texts,
        imageSize: CGSize(width: 1_512, height: 949)
    )

    #expect(name == "룬다 1층 2구역")
}

@Test
func returnsNilWhenNoDungeonNameInTopCenter() {
    let texts = [
        liveText("마비노기 모바일", conf: 1.0, nx: 0.082, ny: 0.017),
        liveText("화면을 터치해 주세요", conf: 1.0, nx: 0.500, ny: 0.919),
    ]

    let name = DungeonNameExtractor.extract(
        from: texts,
        imageSize: CGSize(width: 1_512, height: 949)
    )

    #expect(name == nil)
}

@Test
func ignoresDescriptionKeywordsEvenWhenHighConfidenceAndCentered() {
    let texts = [
        liveText("순수 전투 시간 0:14", conf: 1.0, nx: 0.50, ny: 0.28),
        liveText("오염됨 장비의 내구도가 빨리 감소합니다", conf: 1.0, nx: 0.50, ny: 0.30),
    ]

    let name = DungeonNameExtractor.extract(
        from: texts,
        imageSize: CGSize(width: 1_512, height: 949)
    )

    #expect(name == nil)
}

// MARK: - ActivityLogWriter

@Test
func activityLogAppendsEventsAndSummarizesDungeonRuns() throws {
    let directory = uniqueActivityDirectory()
    defer { removeActivityDirectory(directory) }
    let writer = ActivityLogWriter(directory: directory)

    try writer.append(
        ActivityEvent(
            at: Date(timeIntervalSince1970: 1_753_000_000),
            outcome: "clicked",
            scene: "clear_touch",
            dungeonName: "룬다 1층 2구역"
        )
    )
    try writer.append(
        ActivityEvent(
            at: Date(timeIntervalSince1970: 1_753_000_100),
            outcome: "clicked",
            scene: "reward_retry",
            dungeonName: "룬다 1층 2구역"
        )
    )
    try writer.append(
        ActivityEvent(
            at: Date(timeIntervalSince1970: 1_753_000_200),
            outcome: "clicked",
            scene: "clear_touch",
            dungeonName: "알비 던전"
        )
    )

    let summary = try writer.summary()
    #expect(summary.totalClicks == 3)
    #expect(summary.dungeonRuns == 2) // clear_touch 클릭만 1판 완료로 집계
    #expect(summary.byDungeon["룬다 1층 2구역"] == 1)
    #expect(summary.byDungeon["알비 던전"] == 1)
}

@Test
func activitySummaryOnMissingLogIsZero() throws {
    let directory = uniqueActivityDirectory()
    defer { removeActivityDirectory(directory) }
    let writer = ActivityLogWriter(directory: directory)

    let summary = try writer.summary()

    #expect(summary.totalClicks == 0)
    #expect(summary.dungeonRuns == 0)
    #expect(summary.byDungeon.isEmpty)
}

@Test
func activityLogSurvivesReopeningFromDisk() throws {
    let directory = uniqueActivityDirectory()
    defer { removeActivityDirectory(directory) }
    try ActivityLogWriter(directory: directory).append(
        ActivityEvent(
            at: Date(timeIntervalSince1970: 1_753_000_000),
            outcome: "clicked",
            scene: "clear_touch",
            dungeonName: nil
        )
    )

    let reopened = ActivityLogWriter(directory: directory)
    let summary = try reopened.summary()

    #expect(summary.totalClicks == 1)
    #expect(summary.dungeonRuns == 1)
}

// MARK: - Helpers

private func liveText(
    _ text: String,
    conf: Double,
    nx: Double,
    ny: Double
) -> RecognizedTextObservation {
    let width = 100.0
    let height = 24.0
    return RecognizedTextObservation(
        text: text,
        confidence: conf,
        boundingBox: CGRect(
            x: nx * 1_512 - width / 2,
            y: ny * 949 - height / 2,
            width: width,
            height: height
        )
    )
}

private func uniqueActivityDirectory() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent(
            "activity-tests-\(UUID().uuidString)",
            isDirectory: true
        )
}

private func removeActivityDirectory(_ directory: URL) {
    try? FileManager.default.removeItem(at: directory)
}
