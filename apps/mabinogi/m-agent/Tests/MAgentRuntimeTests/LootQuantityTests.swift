import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import MAgentRuntime

// MARK: - 뱃지 숫자 읽기

@Test(arguments: [
    ("180", 180),
    ("10", 10),
    ("25", 25),
    ("1,382", 1382),
    ("3,983", 3983),
    ("790.8만", 7_908_000),
    ("255.3만", 2_553_000),
    ("1.3만", 13000),
    ("2억", 200_000_000),
])
func quantityBadgeParsesToNumber(badge: String, expected: Int) {
    // 만·억은 한글 단위라 자릿수를 곱해 편다. 소수점이 붙는다('790.8만').
    #expect(CycleTracker.quantityValue(badge) == expected)
}

@Test(arguments: ["골드", "미지의 소울 조각", "", "만병통치약"])
func nonBadgeTextHasNoQuantity(text: String) {
    #expect(CycleTracker.quantityValue(text) == nil)
}

@Test(arguments: ["0", "00", "0만", "0,000"])
func zeroIsNotARealQuantity(badge: String) {
    // 전리품이 나왔는데 0개일 수는 없다. OCR이 뱃지 '10'을 '0'으로 흘려
    // 읽은 것이다(실측 23판 중 7판: '마물 퇴치 증표'에 0이 붙었는데 실제로는
    // 10개다). 0을 그대로 적으면 없는 사실을 기록하는 셈이라 버린다.
    #expect(CycleTracker.quantityValue(badge) == nil)
}

// MARK: - 뱃지↔이름 짝짓기

@Test
func badgeRightAboveTheNameBecomesItsQuantity() {
    // 실측(landscape-tribute-result-deselected): 뱃지 '180'이 이름
    // '모험가 포인트' 바로 위 46px에 있고 가로로 겹친다.
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText("180", midX: 707.7, width: 44.0, midY: 573, height: 24),
            quantityText(
                "모험가 포인트",
                midX: 695.6,
                width: 99.1,
                midY: 617,
                height: 21
            ),
        ] + lootBandAnchors()
    )

    #expect(quantities == ["모험가 포인트": 180])
}

@Test
func equipmentPowerAboveTheIconIsNotAQuantity() {
    // 장비는 아이콘 '위'에 전투력이 붙는다(실측 '1151'·'3860'). 수량
    // 뱃지보다 두 배 멀어서(글자 높이 4.5배 vs 2.3배) 세로 거리로 가른다.
    // 가로로는 둘 다 이름과 완전히 겹쳐 구분되지 않는다.
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText("1151", midX: 183.5, width: 41.8, midY: 451, height: 20),
            quantityText(
                "방패의 판금 갑옷 장갑Z",
                midX: 211.0,
                width: 79.2,
                midY: 541,
                height: 20
            ),
        ] + lootBandAnchors()
    )

    #expect(quantities.isEmpty)
}

@Test
func badgeOfAnotherColumnIsNotBorrowed() {
    // 가로로 안 겹치면 옆 칸 뱃지다. 남의 수량을 가져오면 안 된다.
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText("25", midX: 586.8, width: 30.8, midY: 686, height: 22),
            quantityText(
                "조각난 루비",
                midX: 1281.2,
                width: 83.6,
                midY: 731,
                height: 20
            ),
        ] + lootBandAnchors()
    )

    #expect(quantities.isEmpty)
}

@Test
func badgeBelowTheNameIsIgnored() {
    // 뱃지는 언제나 이름 위에 있다. 아래 있는 숫자는 다음 줄 아이템의 것이다.
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText(
                "룬의 파편",
                midX: 568.1,
                width: 68.3,
                midY: 731,
                height: 20
            ),
            quantityText("13", midX: 570.0, width: 24.2, midY: 776, height: 20),
        ] + lootBandAnchors()
    )

    #expect(quantities.isEmpty)
}

@Test
func nameWithoutABadgeGetsNoEntry() {
    // 뱃지가 없는 아이템이 있다(실측: 갱신권·패션 티켓 조각 보물 상자).
    // '뱃지 없음 = 1개'로 적으면 안 된다 — 모르는 것을 지어내지 않는다.
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText("갱신권", midX: 806.5, width: 48.3, midY: 551, height: 20),
        ] + lootBandAnchors()
    )

    #expect(quantities.isEmpty)
}

@Test
func twoLineNameKeepsTheQuantityOfItsFirstLine() {
    // 이름이 두 줄로 쪼개지면 뱃지는 첫 줄 위에 있다. 이어 붙인 전체
    // 이름에 수량이 달려야 한다(실측 '조각난'/'다이아몬드' + 뱃지 '4').
    let quantities = CycleTracker.itemQuantities(
        in: [
            quantityText("4", midX: 1050.0, width: 15.0, midY: 686, height: 20),
            quantityText("조각난", midX: 1043.9, width: 48.3, midY: 722, height: 20),
            quantityText(
                "다이아몬드",
                midX: 1043.9,
                width: 79.4,
                midY: 742,
                height: 23
            ),
        ] + lootBandAnchors()
    )

    #expect(quantities == ["조각난 다이아몬드": 4])
}

// MARK: - 실제 화면

@Test
func realResultScreenYieldsQuantities() async throws {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent(
            "Fixtures/landscape-tribute-result-deselected.png"
        )
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    let image = try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
    let texts = try await VisionTextRecognizer().recognizeText(in: image)
    let quantities = CycleTracker.itemQuantities(in: texts)

    #expect(quantities["모험가 포인트"] == 180)
    #expect(quantities["마물 퇴치 증표"] == 10)
}

@Test
func realResultScreenDoesNotMistakePowerForQuantity() async throws {
    // 이 화면에는 장비 3개가 있고 전투력이 1151·3860·1111로 붙는다.
    // 그 숫자가 수량으로 새면 '갑옷 장갑Z 1151개'가 된다.
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent(
            "Fixtures/landscape-tribute-result-revealed.png"
        )
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    let image = try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
    let texts = try await VisionTextRecognizer().recognizeText(in: image)
    let quantities = CycleTracker.itemQuantities(in: texts)

    #expect(!quantities.values.contains(1151))
    #expect(!quantities.values.contains(3860))
    #expect(!quantities.values.contains(1111))
    // 같은 화면의 진짜 수량은 살아 있다.
    #expect(quantities["모험가 포인트"] == 180)
    #expect(quantities["경험치"] == 7_908_000)
}

// MARK: - 기록에 남기기

@Test
func recordedCycleCarriesQuantities() {
    var tracker = CycleTracker()
    let size = CGSize(width: 1512, height: 949)

    _ = tracker.observe(
        texts: [
            quantityText(
                "순수 전투 시간 0:31",
                midX: 757,
                width: 130,
                midY: 303,
                height: 20
            ),
            quantityText("180", midX: 707.7, width: 44, midY: 573, height: 24),
            quantityText(
                "모험가 포인트",
                midX: 695.6,
                width: 99.1,
                midY: 617,
                height: 21
            ),
        ] + lootBandAnchors(),
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_000)
    )
    let record = tracker.observe(
        texts: [],
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_002)
    )

    #expect(record?.items == ["모험가 포인트"])
    #expect(record?.quantities == ["모험가 포인트": 180])
}

@Test
func quantitySeenInALaterFrameStillLands() {
    // 이름이 먼저 잡히고 뱃지가 다음 프레임에 잡히는 경우가 있다. 이름은
    // 이미 모았다고 건너뛰면서 수량만 영영 빠지면 안 된다.
    var tracker = CycleTracker()
    let size = CGSize(width: 1512, height: 949)
    let marker = quantityText(
        "순수 전투 시간 0:31",
        midX: 757,
        width: 130,
        midY: 303,
        height: 20
    )
    let name = quantityText(
        "모험가 포인트",
        midX: 695.6,
        width: 99.1,
        midY: 617,
        height: 21
    )

    _ = tracker.observe(
        texts: [marker, name] + lootBandAnchors(),
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_000)
    )
    _ = tracker.observe(
        texts: [
            marker,
            quantityText("180", midX: 707.7, width: 44, midY: 573, height: 24),
            name,
        ] + lootBandAnchors(),
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_002)
    )
    let record = tracker.observe(
        texts: [],
        imageSize: size,
        at: Date(timeIntervalSince1970: 1_800_000_004)
    )

    #expect(record?.quantities == ["모험가 포인트": 180])
}

@Test
func recordsWrittenBeforeQuantitiesStillDecode() throws {
    // 이미 쌓인 550판에는 수량 칸이 없다. 새 필드 때문에 옛 기록을
    // 못 읽으면 그동안의 통계가 통째로 날아간다.
    let line = """
    {"at":"2026-07-27T10:12:28Z","dungeon":"피오드 1층 2구역",\
    "combatSeconds":20,"items":["모험가 포인트"],"build":"de28b2a-0726T2015"}
    """
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .iso8601
    let record = try decoder.decode(
        CycleRecord.self,
        from: try #require(line.data(using: .utf8))
    )

    #expect(record.items == ["모험가 포인트"])
    #expect(record.quantities == nil)
}

private func quantityText(
    _ text: String,
    midX: Double,
    width: Double,
    midY: Double,
    height: Double
) -> RecognizedTextObservation {
    RecognizedTextObservation(
        text: text,
        confidence: 1,
        boundingBox: CGRect(
            x: midX - width / 2,
            y: midY - height / 2,
            width: width,
            height: height
        )
    )
}
