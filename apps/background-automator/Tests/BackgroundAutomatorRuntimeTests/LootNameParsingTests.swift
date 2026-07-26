import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

@Test(arguments: [
    "255.3만", "1.3만", "1,382", "691", "100", "2", "252.8만", "3,423",
])
func quantityBadgesAreNotRecordedAsItems(badge: String) {
    // 뱃지는 아이콘 위에 얹힌 수량이다. '만'이 한글이라 한글 필터를
    // 그냥 통과해 전리품 목록에 섞였다(실측 로그: '255.3만', '1.3만').
    #expect(CycleTracker.isQuantityBadge(badge))
}

@Test(arguments: [
    "골드", "조각난 루비", "미지의 소울 조각", "공명의 영혼석",
    "만병통치약", "천옥의 돌",
])
func realItemNamesAreNotMistakenForQuantities(name: String) {
    // '만'·'천'으로 시작하거나 끝나는 진짜 아이템 이름을 죽이면 안 된다.
    #expect(!CycleTracker.isQuantityBadge(name))
}

@Test
func twoLineItemNamesAreJoinedIntoOne() {
    // 아이콘 하나 밑에 이름이 두 줄로 쌓이면 OCR은 두 덩어리로 준다.
    // 실측(landscape-loot-double-revealed): '세공된 블루' / '스피넬Z'.
    let size = CGSize(width: 1512, height: 949)
    let names = CycleTracker.itemNames(
        in: [
            lootText("세공된 블루", x: 169, width: 84, y: 540),
            lootText("스피넬Z", x: 182, width: 60, y: 560),
            lootText("골드", x: 433, width: 33, y: 550),
        ],
        imageSize: size
    )
    #expect(names == ["세공된 블루 스피넬Z", "골드"])
}

@Test
func labelsInDifferentRowsAreNeverJoined() {
    // 같은 x라도 줄이 다르면 서로 다른 아이템이다.
    let size = CGSize(width: 1512, height: 949)
    let names = CycleTracker.itemNames(
        in: [
            lootText("룬의 파편", x: 246, width: 66, y: 540),
            lootText("조각난 루비", x: 246, width: 66, y: 730),
        ],
        imageSize: size
    )
    #expect(names == ["룬의 파편", "조각난 루비"])
}

@Test
func realDoubleLootScreenshotYieldsCleanNames() async throws {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent(
            "Fixtures/landscape-loot-double-revealed.png"
        )
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    let image = try #require(
        CGImageSourceCreateImageAtIndex(source, 0, nil)
    )
    let texts = try await VisionTextRecognizer().recognizeText(in: image)
    let names = CycleTracker.itemNames(
        in: texts,
        imageSize: CGSize(width: image.width, height: image.height)
    )

    // 붙어야 할 이름이 붙었다.
    #expect(names.contains("세공된 블루 스피넬Z"))
    #expect(names.contains("미지의 소울 조각"))
    #expect(names.contains("조각난 다이아몬드"))
    // 수량 뱃지가 사라졌다.
    #expect(!names.contains { CycleTracker.isQuantityBadge($0) })
    #expect(!names.contains("255.3만"))
    #expect(!names.contains("1.3만"))
    // 단독 이름은 그대로다.
    #expect(names.contains("골드"))
    #expect(names.contains("마물 퇴치 증표"))
}

private func lootText(
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
