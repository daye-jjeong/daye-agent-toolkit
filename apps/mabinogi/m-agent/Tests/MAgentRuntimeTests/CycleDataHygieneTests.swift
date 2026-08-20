import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import MAgentRuntime

// MARK: - 전리품에 섞이던 UI 글자

@Test
func resultHeaderIsNotRecordedAsLoot() {
    // 실측(페카 38판): '페카 고분 심층 1층 2구역 • 순수 전투 시간 0:26'이
    // 전리품으로 3판 기록됐다. 구간을 화면 비율로 잡던 시절, 결과 화면이
    // 떠오르는 동안 헤더가 그 구간을 지나가면서 잡혔다.
    // 지금은 '발견한 전리품' 아래부터 모은다. 던전 이름과 전투 시간은 늘
    // 그 글자보다 위에 있어 구조적으로 들어올 수 없다.
    let names = CycleTracker.itemNames(
        in: [
            hygieneText("페카 고분 심층 1층 2구역", x: 640, width: 230, y: 540),
            hygieneText("• 순수 전투 시간 0:26", x: 690, width: 130, y: 566),
            hygieneText("마물 퇴치 증표", x: 880, width: 90, y: 617),
        ] + lootBandAnchors(headerY: 580)
    )

    #expect(names == ["마물 퇴치 증표"])
}

@Test
func confirmDialogFreezesLootCollectionForThatFrame() {
    // 실측(페카 38판 중 33판): '던전 탐험을 계속하시겠습니까?' 다이얼로그가
    // 결과 화면을 덮는데, 그 글자가 수집 구간 한가운데에 떨어져 전리품으로
    // 쌓였다. 가려진 화면은 믿지 않는다 — 전리품은 이미 앞 프레임에서 모였다.
    var tracker = CycleTracker()
    let size = CGSize(width: 1512, height: 949)

    _ = tracker.observe(
        texts: [
            hygieneText("순수 전투 시간 0:31", x: 750, width: 130, y: 303),
            hygieneText("마물 퇴치 증표", x: 880, width: 90, y: 617),
        ] + lootBandAnchors(),
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_000)
    )
    _ = tracker.observe(
        texts: [
            hygieneText("순수 전투 시간 0:31", x: 750, width: 130, y: 303),
            hygieneText("던전 탐험을 계속하시겠습니까?", x: 755, width: 390, y: 653),
            hygieneText(
                "던전 밖에서 진행해야 할 퀘스트가 있습니다.",
                x: 755,
                width: 430,
                y: 717
            ),
        ] + lootBandAnchors(),
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_002)
    )
    let record = tracker.observe(
        texts: [],
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_004)
    )

    let items = try? #require(record).items
    #expect(items == ["마물 퇴치 증표"])
}

@Test
func theAnimatingResultHeaderYieldsNoLootOnTheRealFrame() async throws {
    // 상자가 열리는 중이라 '발견한 전리품'조차 아직 안 떴다. 구간을 여는
    // 글자가 없으면 아무것도 모으지 않는다 — 어림짐작으로 모으면 그 프레임에
    // 보이는 '룬다 1층 2구역'과 '순수 전투 시간 0:20'이 전리품이 된다.
    // (비율로 잡던 시절 실제로 그렇게 기록됐다.)
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Fixtures/landscape-result-early.png")
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    let image = try #require(
        CGImageSourceCreateImageAtIndex(source, 0, nil)
    )
    let texts = try await VisionTextRecognizer().recognizeText(in: image)

    let names = CycleTracker.itemNames(in: texts)

    #expect(names.isEmpty)
}

// MARK: - 띄어쓰기만 다른 던전 이름

@Test
func dungeonNamesThatDifferOnlyBySpacingAreCountedTogether() throws {
    // 실측: OCR이 같은 던전을 '페카 고분 심층 1층 2구역'(8판)과
    // '페카고분 심층 1층 2구역'(27판)으로 갈라 읽어 통계가 쪼개졌다.
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("dungeon-spacing-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)

    for (index, name) in [
        "페카 고분 심층 1층 2구역",
        "페카고분 심층 1층 2구역",
        "페카 고분 심층 1층 2구역",
    ].enumerated() {
        try writer.append(
            CycleRecord(
                at: Date(timeIntervalSince1970: 1_800_000_000 + Double(index)),
                dungeon: name,
                combatSeconds: 31,
                items: []
            )
        )
    }

    let summary = try writer.summary()

    #expect(summary.byDungeon.count == 1)
    // 대표 표기는 처음 읽은 것으로 둔다 — 붙여 쓴 쪽이 이기면 읽기 나쁘다.
    #expect(summary.byDungeon["페카 고분 심층 1층 2구역"] == 3)
}

@Test
func differentDungeonsStayApart() throws {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("dungeon-distinct-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)

    for (index, name) in ["룬다 1층 2구역", "룬다 1층 3구역"].enumerated() {
        try writer.append(
            CycleRecord(
                at: Date(timeIntervalSince1970: 1_800_000_000 + Double(index)),
                dungeon: name,
                combatSeconds: 16,
                items: []
            )
        )
    }

    let summary = try writer.summary()

    #expect(summary.byDungeon.count == 2)
}

// MARK: - 입장 방식 기록

@Test
func cycleRecordsHowTheDungeonWasEntered() throws {
    // 재화를 쓰고 들어간 판인지가 로그에 없어, 지금까지 전리품 칸 수로
    // 짐작해야 했다. 그건 추정이지 기록이 아니다.
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("cycle-entry-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let writer = CycleLogWriter(directory: directory)

    try writer.append(
        CycleRecord(
            at: Date(timeIntervalSince1970: 1_800_000_000),
            dungeon: "페카 고분 심층 1층 2구역",
            combatSeconds: 31,
            items: ["마물 퇴치 증표"]
        )
        .entered(.tribute)
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            CycleLogWriter.fileName
        ),
        encoding: .utf8
    )
    #expect(text.contains("\"entry\":\"tribute\""))
}

@Test(arguments: [
    ("enter_with_coin", DungeonEntry.coin),
    ("enter_with_tribute", DungeonEntry.tribute),
    ("enter_ready", DungeonEntry.free),
])
func entryKindIsDerivedFromTheRuleThatClickedEnter(
    ruleID: String,
    expected: DungeonEntry
) {
    #expect(DungeonEntry(ruleID: ruleID) == expected)
}

@Test
func nonEntryRulesDoNotChangeTheRecordedEntry() {
    // 컷신 넘기기나 다시 하기는 입장이 아니다.
    #expect(DungeonEntry(ruleID: "scene_skip") == nil)
    #expect(DungeonEntry(ruleID: "reward_retry") == nil)
}

// MARK: - Helpers

private func hygieneText(
    _ text: String,
    x: Double,
    width: Double,
    y: Double
) -> RecognizedTextObservation {
    RecognizedTextObservation(
        text: text,
        confidence: 1,
        boundingBox: CGRect(x: x, y: y, width: width, height: 18)
    )
}
