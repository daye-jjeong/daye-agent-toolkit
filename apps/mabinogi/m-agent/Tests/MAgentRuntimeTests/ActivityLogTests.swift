import MAgentCore
import CoreGraphics
import Foundation
import Testing

@testable import MAgentRuntime

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
func extractsDungeonNameWhenCoinRunOverlayLowersConfidence() {
    // 실측(2026-07-25 은동전 쓴 런 결과 화면): 같은 '룬다 1층 2구역'이
    // 연출 오버레이 때문에 conf 0.50으로 떨어진다(코인 안 쓴 런은 1.0).
    // 신뢰도만으로 거르면 코인런의 던전 이름을 통째로 잃는다. 난이도
    // 라벨은 던전 이름보다 위에 있어 완화 시 오답이 되므로 함께 막는다.
    let texts = [
        liveText("어려움", conf: 0.50, nx: 0.496, ny: 0.241),
        liveText("룬다 1층 2구역", conf: 0.50, nx: 0.502, ny: 0.281),
        liveText("C 순수 전투 시간 0:13", conf: 1.0, nx: 0.499, ny: 0.319),
    ]

    let name = DungeonNameExtractor.extract(
        from: texts,
        imageSize: CGSize(width: 1_512, height: 949)
    )

    #expect(name == "룬다 1층 2구역")
}

@Test(arguments: ["쉬움", "보통", "어려움", "매우 어려움", "어려움]"])
func neverReturnsDifficultyLabelAsDungeonName(label: String) {
    // 난이도 라벨은 던전 이름 바로 위(더 작은 y)에 뜬다. '가장 위' 규칙만
    // 두면 신뢰도 완화 후 난이도가 이름으로 뽑힌다.
    let texts = [
        liveText(label, conf: 0.50, nx: 0.496, ny: 0.241),
        liveText("룬다 1층 2구역", conf: 0.50, nx: 0.502, ny: 0.281),
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
