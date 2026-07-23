import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func classifiesObservedMobilePortraitSize() {
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 626, height: 949)
        ) == .portraitMobile
    )
}

@Test
func classifiesObservedLandscapeSize() {
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 1_512, height: 949)
        ) == .landscape
    )
}

@Test
func minimumDimensionsAreInclusive() {
    let configuration = boundaryConfiguration()

    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 100, height: 200),
            configuration: configuration
        ) == .portraitMobile
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 200, height: 100),
            configuration: configuration
        ) == .landscape
    )
}

@Test
func dimensionsBelowEitherMinimumAreUnsupported() {
    let configuration = boundaryConfiguration()

    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 99, height: 198),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 198, height: 99),
            configuration: configuration
        ) == .unsupported
    )
}

@Test
func aspectRatioBoundariesAreInclusive() {
    let configuration = boundaryConfiguration()

    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 500, height: 1_000),
            configuration: configuration
        ) == .portraitMobile
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 750, height: 1_000),
            configuration: configuration
        ) == .portraitMobile
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 1_250, height: 1_000),
            configuration: configuration
        ) == .landscape
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 2_000, height: 1_000),
            configuration: configuration
        ) == .landscape
    )
}

@Test
func ratiosImmediatelyOutsideConfiguredBoundariesAreUnsupported() {
    let configuration = boundaryConfiguration()

    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(
                width: CGFloat(0.5.nextDown * 1_000),
                height: 1_000
            ),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(
                width: CGFloat(0.75.nextUp * 1_000),
                height: 1_000
            ),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(
                width: CGFloat(1.25.nextDown * 1_000),
                height: 1_000
            ),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(
                width: CGFloat(2.0.nextUp * 1_000),
                height: 1_000
            ),
            configuration: configuration
        ) == .unsupported
    )
}

@Test
func ambiguousAndExtremeRatiosAreUnsupported() {
    let configuration = boundaryConfiguration()

    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 1_000, height: 1_000),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 100, height: 1_000),
            configuration: configuration
        ) == .unsupported
    )
    #expect(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 3_000, height: 1_000),
            configuration: configuration
        ) == .unsupported
    )
}

@Test(
    arguments: [
        CGSize(width: 0, height: 949),
        CGSize(width: 626, height: 0),
        CGSize(width: -626, height: 949),
        CGSize(width: 626, height: -949),
        CGSize(width: CGFloat.infinity, height: 949),
        CGSize(width: 626, height: CGFloat.infinity),
        CGSize(width: CGFloat.nan, height: 949),
        CGSize(width: 626, height: CGFloat.nan),
    ]
)
func invalidDimensionsAreUnsupported(imageSize: CGSize) {
    #expect(
        LayoutClassifier.classify(imageSize: imageSize) == .unsupported
    )
}

private func boundaryConfiguration() -> LayoutClassifier.Configuration {
    LayoutClassifier.Configuration(
        minimumWidth: 100,
        minimumHeight: 100,
        portraitAspectRatio: 0.5 ... 0.75,
        landscapeAspectRatio: 1.25 ... 2.0
    )
}
