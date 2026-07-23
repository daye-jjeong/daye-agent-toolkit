import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func convertsNormalizedWindowPointToScreenPoint() throws {
    let frame = CGRect(x: 100, y: 200, width: 1_200, height: 800)

    let point = try CoordinateConverter.screenPoint(
        normalizedX: 0.5,
        normalizedY: 0.75,
        windowFrame: frame
    )

    #expect(abs(point.x - 700) < 0.001)
    #expect(abs(point.y - 800) < 0.001)
}

@Test
func acceptsInclusiveNormalizedBoundaries() throws {
    let frame = CGRect(x: 100, y: 200, width: 1_200, height: 800)

    let minimum = try CoordinateConverter.screenPoint(
        normalizedX: 0,
        normalizedY: 0,
        windowFrame: frame
    )
    let maximum = try CoordinateConverter.screenPoint(
        normalizedX: 1,
        normalizedY: 1,
        windowFrame: frame
    )

    #expect(minimum == CGPoint(x: 100, y: 200))
    #expect(maximum == CGPoint(x: 1_300, y: 1_000))
}

@Test(arguments: [-0.001, 1.001])
func rejectsNormalizedXOutsideRange(normalizedX: Double) {
    #expect(throws: CoordinateError.outOfRange) {
        try CoordinateConverter.screenPoint(
            normalizedX: normalizedX,
            normalizedY: 0.5,
            windowFrame: CGRect(x: 100, y: 200, width: 1_200, height: 800)
        )
    }
}

@Test(arguments: [-0.001, 1.001])
func rejectsNormalizedYOutsideRange(normalizedY: Double) {
    #expect(throws: CoordinateError.outOfRange) {
        try CoordinateConverter.screenPoint(
            normalizedX: 0.5,
            normalizedY: normalizedY,
            windowFrame: CGRect(x: 100, y: 200, width: 1_200, height: 800)
        )
    }
}
