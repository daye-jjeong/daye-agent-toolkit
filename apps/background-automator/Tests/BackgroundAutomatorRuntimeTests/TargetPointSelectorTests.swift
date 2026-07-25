import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func centerSelectorReturnsExactBoxCenter() {
    let selector = CenterTargetPointSelector()

    #expect(
        selector.point(in: CGRect(x: 100, y: 200, width: 80, height: 40))
            == CGPoint(x: 140, y: 220)
    )
    #expect(selector.point(in: .null) == nil)
    #expect(selector.point(in: .infinite) == nil)
}

@Test
func randomSelectorStaysInsideInsetBoxAndVaries() throws {
    // insetFraction 0.2 → 박스 가장자리 20% 여백 안, 중앙 60% 영역에서만
    // 임의 클릭. 매번 정중앙 고정 대신 흩뿌려 '동일 위치 반복'을 없앤다.
    let selector = RandomTargetPointSelector(insetFraction: 0.2)
    let box = CGRect(x: 100, y: 200, width: 80, height: 40)

    var xs: Set<Double> = []
    for _ in 0..<200 {
        let point = try #require(selector.point(in: box))
        // x ∈ [116,164], y ∈ [208,232] (여백 16·8)
        #expect(point.x >= 116 && point.x <= 164)
        #expect(point.y >= 208 && point.y <= 232)
        xs.insert(point.x)
    }
    // 고정이 아니라 실제로 흩어진다.
    #expect(xs.count > 1)
}

@Test
func randomSelectorFallsBackToCenterWhenInsetCollapses() {
    // 여백을 빼면 폭/높이가 사라지는 작은 박스는 중앙으로 폴백(빈 range로
    // Double.random 트랩 방지).
    let selector = RandomTargetPointSelector(insetFraction: 0.2)

    #expect(
        selector.point(in: CGRect(x: 10, y: 10, width: 0, height: 0))
            == CGPoint(x: 10, y: 10)
    )
    #expect(selector.point(in: .null) == nil)
    #expect(selector.point(in: .infinite) == nil)
}
