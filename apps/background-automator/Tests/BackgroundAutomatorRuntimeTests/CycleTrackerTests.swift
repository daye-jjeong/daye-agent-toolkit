import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

/// 결과 화면(= 사이클 마커) 텍스트를 흉내낸다.
/// 실측: '• 순수 전투 시간 0:13'(cf 1.0)은 은동전 사용 여부와 무관하게
/// 모든 클리어 결과 화면에 뜬다.
private func resultTexts(
    combat: String = "• 순수 전투 시간 0:13",
    dungeon: String = "룬다 1층 2구역",
    items: [String] = []
) -> [RecognizedTextObservation] {
    var texts = [
        RecognizedTextObservation(
            text: dungeon,
            confidence: 1.0,
            boundingBox: CGRect(x: 683, y: 252, width: 143, height: 31)
        ),
        RecognizedTextObservation(
            text: combat,
            confidence: 1.0,
            boundingBox: CGRect(x: 683, y: 295, width: 140, height: 17)
        ),
    ]
    for (index, item) in items.enumerated() {
        texts.append(
            RecognizedTextObservation(
                text: item,
                confidence: 0.5,
                boundingBox: CGRect(
                    x: 551 + 120 * index,
                    y: 541,
                    width: 32,
                    height: 20
                )
            )
        )
    }
    return texts
}

private func battleTexts() -> [RecognizedTextObservation] {
    [
        RecognizedTextObservation(
            text: "장면 넘기기",
            confidence: 0.5,
            boundingBox: CGRect(x: 1350, y: 60, width: 120, height: 30)
        ),
    ]
}

@Test
func cycleIsRecordedOnceWhenTheResultScreenCloses() {
    // 결과 화면은 여러 프레임 이어진다. 화면이 떠 있는 동안은 아이템을
    // 모으기만 하고, 화면이 닫힐 때 한 판으로 한 줄 남긴다.
    var tracker = CycleTracker()

    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) == nil)
    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) == nil)
    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) == nil)

    let record = tracker.observe(texts: battleTexts(), imageSize: resultSize)
    #expect(record != nil)
    // 닫힌 뒤에는 더 나오지 않는다.
    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) == nil)
}

@Test
func hiddenLootRevealedMidScreenIsIncludedInTheSameCycle() {
    // 실측(은동전 쓴 런): 결과 화면이 처음 뜰 때 전리품 일부가 '?'로
    // 가려져 있고, '발견한 전리품'을 눌러야 장비 드랍이 드러난다.
    // 처음 프레임만 보고 기록하면 가장 값진 드랍을 놓친다.
    var tracker = CycleTracker()

    _ = tracker.observe(
        texts: resultTexts(items: ["골드", "조각난 흑요석"]),
        imageSize: resultSize
    )
    _ = tracker.observe(
        texts: resultTexts(items: ["골드", "조각난 흑요석", "방패의 판금 갑옷 신발"]),
        imageSize: resultSize
    )
    let record = tracker.observe(texts: battleTexts(), imageSize: resultSize)

    let items = record?.items ?? []
    #expect(items.contains("골드"))
    #expect(items.contains("조각난 흑요석"))
    #expect(items.contains("방패의 판금 갑옷 신발"))
    // 같은 아이템이 여러 프레임에 보여도 한 번만 센다.
    #expect(items.filter { $0 == "골드" }.count == 1)
}

@Test
func twoResultScreensRecordTwoCycles() {
    var tracker = CycleTracker()

    _ = tracker.observe(texts: resultTexts(), imageSize: resultSize)
    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) != nil)
    _ = tracker.observe(texts: resultTexts(), imageSize: resultSize)
    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) != nil)
}

@Test
func recordedCycleCarriesDungeonAndCombatSeconds() {
    var tracker = CycleTracker()

    _ = tracker.observe(
        texts: resultTexts(combat: "• 순수 전투 시간 1:05"),
        imageSize: resultSize
    )
    let record = tracker.observe(texts: battleTexts(), imageSize: resultSize)

    #expect(record?.dungeon == "룬다 1층 2구역")
    #expect(record?.combatSeconds == 65)
}

@Test
func recordIsStampedWhenTheResultScreenFirstAppeared() {
    // 사이클이 '끝난 시각'은 결과 화면이 뜬 순간이다. 화면이 닫힐 때까지
    // 기다렸다 남기더라도 시각은 처음 본 시점으로 찍는다.
    var tracker = CycleTracker()
    let appeared = Date(timeIntervalSince1970: 1_800_000_000)

    _ = tracker.observe(
        texts: resultTexts(),
        imageSize: resultSize,
        at: appeared
    )
    let record = tracker.observe(
        texts: battleTexts(),
        imageSize: resultSize,
        at: appeared.addingTimeInterval(6)
    )

    #expect(record?.at == appeared)
}

@Test
func combatTimeVariantsParseToSeconds() {
    #expect(CycleTracker.combatSeconds(in: "• 순수 전투 시간 0:13") == 13)
    #expect(CycleTracker.combatSeconds(in: "C 순수 전투 시간 0:13") == 13)
    #expect(CycleTracker.combatSeconds(in: "순수 전투 시간 12:07") == 727)
    #expect(CycleTracker.combatSeconds(in: "다시 하기") == nil)
}

@Test(arguments: [
    "landscape-reward-detail",        // 은동전 쓴 런
    "landscape-reward-detail-nocoin", // 은동전 안 쓴 런
])
func realResultScreenshotsRecordCycleRegardlessOfCoinUse(
    fixture: String
) async throws {
    // 골든 테스트: 손먹인 값이 아니라 실제 캡처를 진짜 Vision OCR에 돌려
    // 사이클이 잡히는지 본다. 은동전 사용 여부와 무관하게 한 사이클로
    // 기록돼야 한다(코인 없는 런 기록이 이 기능의 핵심 요구).
    let recognizer = VisionTextRecognizer()
    let texts = try await recognizer.recognizeText(
        in: try cycleFixtureImage(named: fixture)
    )
    var tracker = CycleTracker()

    // 결과 화면이 이어지는 동안은 모으기만 하고, 닫힐 때 한 줄 남긴다.
    #expect(tracker.observe(texts: texts, imageSize: resultSize) == nil)
    let recorded = tracker.observe(texts: [], imageSize: resultSize)
    let record = try #require(recorded)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds != nil)
    #expect(!record.items.isEmpty)
}

private func cycleFixtureImage(named name: String) throws -> CGImage {
    let url = try #require(
        Bundle.module.url(
            forResource: name,
            withExtension: "png",
            subdirectory: "Fixtures"
        )
    )
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    return try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
}

private let resultSize = CGSize(width: 1512, height: 949)

@Test(arguments: [
    "룬다 1층 2구역",
    "룬다. 1층 2구역",
    "룬다 '1층 2구역*",
    "  룬다   1층 2구역 ",
])
func dungeonNamesCollapseToOneSpelling(raw: String) {
    // 실측 로그에 같은 던전이 세 가지 철자로 쌓여 통계가 쪼개졌다.
    #expect(DungeonNameExtractor.normalizedName(raw) == "룬다 1층 2구역")
}
