import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func convertsVisionBottomLeftRectToTopLeftPixels() {
    let converted = ObservationGeometry.topLeftPixelRect(
        fromVisionNormalizedRect: CGRect(
            x: 0.1,
            y: 0.2,
            width: 0.3,
            height: 0.4
        ),
        imageSize: CGSize(width: 1_000, height: 500)
    )

    expectRect(
        converted,
        equals: CGRect(x: 100, y: 200, width: 300, height: 200)
    )
}

@Test
func clampsPartiallyOutOfBoundsVisionRect() {
    let converted = ObservationGeometry.topLeftPixelRect(
        fromVisionNormalizedRect: CGRect(
            x: -0.1,
            y: 0.8,
            width: 0.3,
            height: 0.4
        ),
        imageSize: CGSize(width: 1_000, height: 500)
    )

    expectRect(
        converted,
        equals: CGRect(x: 0, y: 0, width: 200, height: 100)
    )
}

@Test(arguments: [
    CGRect(x: 0.2, y: 0.2, width: 0, height: 0.2),
    CGRect(x: 0.2, y: 0.2, width: 0.2, height: 0),
    CGRect(x: 0.2, y: 0.2, width: -0.1, height: 0.2),
    CGRect(x: 0.2, y: 0.2, width: 0.2, height: -0.1),
    CGRect(x: 1.1, y: 0.2, width: 0.2, height: 0.2),
    CGRect(x: 0.2, y: -0.3, width: 0.2, height: 0.2),
    CGRect(x: .nan, y: 0.2, width: 0.2, height: 0.2),
    CGRect(x: 0.2, y: 0.2, width: .infinity, height: 0.2),
])
func rejectsMalformedOrFullyOutOfBoundsVisionRect(rect: CGRect) {
    #expect(
        ObservationGeometry.topLeftPixelRect(
            fromVisionNormalizedRect: rect,
            imageSize: CGSize(width: 1_000, height: 500)
        ) == nil
    )
}

@Test(arguments: [
    CGSize(width: 0, height: 500),
    CGSize(width: 1_000, height: 0),
    CGSize(width: -1, height: 500),
    CGSize(width: 1_000, height: -1),
    CGSize(width: CGFloat.infinity, height: 500),
    CGSize(width: 1_000, height: CGFloat.nan),
])
func rejectsInvalidImageSizeForGeometry(imageSize: CGSize) {
    #expect(
        ObservationGeometry.topLeftPixelRect(
            fromVisionNormalizedRect: CGRect(
                x: 0.1,
                y: 0.2,
                width: 0.3,
                height: 0.4
            ),
            imageSize: imageSize
        ) == nil
    )
}

private func expectRect(
    _ actual: CGRect?,
    equals expected: CGRect,
    tolerance: CGFloat = 0.000_001
) {
    #expect(actual != nil)
    guard let actual else {
        return
    }
    #expect(abs(actual.origin.x - expected.origin.x) < tolerance)
    #expect(abs(actual.origin.y - expected.origin.y) < tolerance)
    #expect(abs(actual.size.width - expected.size.width) < tolerance)
    #expect(abs(actual.size.height - expected.size.height) < tolerance)
}
