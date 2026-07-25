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
func markerAppearanceRecordsExactlyOneCycle() {
    // 마커는 여러 프레임 연속으로 보인다. '안 보임 → 보임' 전이에서만
    // 1회 기록해야 한다(같은 사이클을 프레임 수만큼 세면 안 된다).
    var tracker = CycleTracker()

    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) == nil)
    let first = tracker.observe(texts: resultTexts(), imageSize: resultSize)
    #expect(first != nil)
    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) == nil)
    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) == nil)
}

@Test
func markerReappearanceAfterGapRecordsSecondCycle() {
    // 마커가 사라졌다 다시 뜨면 다음 사이클이다.
    var tracker = CycleTracker()

    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) != nil)
    #expect(tracker.observe(texts: battleTexts(), imageSize: resultSize) == nil)
    #expect(tracker.observe(texts: resultTexts(), imageSize: resultSize) != nil)
}

@Test
func recordedCycleCarriesDungeonAndCombatSeconds() {
    var tracker = CycleTracker()

    let record = tracker.observe(
        texts: resultTexts(combat: "• 순수 전투 시간 1:05"),
        imageSize: resultSize
    )

    #expect(record?.dungeon == "룬다 1층 2구역")
    #expect(record?.combatSeconds == 65)
}

@Test
func recordedCycleListsItemPresenceWithoutQuantities() {
    // 지금 범위는 '이 사이클에 나왔나'(등장 여부)만. 정확 수량은 별도 과제.
    var tracker = CycleTracker()

    let record = tracker.observe(
        texts: resultTexts(items: ["골드", "조각난 흑요석"]),
        imageSize: resultSize
    )

    #expect(record?.items.contains("골드") == true)
    #expect(record?.items.contains("조각난 흑요석") == true)
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

    let recorded = tracker.observe(texts: texts, imageSize: resultSize)
    let record = try #require(recorded)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds != nil)
    #expect(!record.items.isEmpty)
    // 같은 화면이 이어지는 동안은 다시 세지 않는다.
    #expect(tracker.observe(texts: texts, imageSize: resultSize) == nil)
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
