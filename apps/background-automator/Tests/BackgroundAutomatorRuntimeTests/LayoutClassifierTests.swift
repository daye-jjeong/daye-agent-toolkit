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
func minimumDimensionsAreInclusive() throws {
    let configuration = try boundaryConfiguration()

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
func dimensionsBelowEitherMinimumAreUnsupported() throws {
    let configuration = try boundaryConfiguration()

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
func aspectRatioBoundariesAreInclusive() throws {
    let configuration = try boundaryConfiguration()

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
func ratiosImmediatelyOutsideConfiguredBoundariesAreUnsupported() throws {
    let configuration = try boundaryConfiguration()

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
func ambiguousAndExtremeRatiosAreUnsupported() throws {
    let configuration = try boundaryConfiguration()

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

@Test
func configurationRejectsInvalidMinimumWidth() {
    for value in [0, -1, Double.nan, Double.infinity] {
        #expect(
            throws: LayoutClassifier.ConfigurationError.invalidMinimumWidth
        ) {
            try LayoutClassifier.Configuration(
                minimumWidth: value,
                minimumHeight: 100,
                portraitAspectRatio: 0.5 ... 0.75,
                landscapeAspectRatio: 1.25 ... 2.0
            )
        }
    }
}

@Test
func configurationRejectsInvalidMinimumHeight() {
    for value in [0, -1, Double.nan, Double.infinity] {
        #expect(
            throws: LayoutClassifier.ConfigurationError.invalidMinimumHeight
        ) {
            try LayoutClassifier.Configuration(
                minimumWidth: 100,
                minimumHeight: value,
                portraitAspectRatio: 0.5 ... 0.75,
                landscapeAspectRatio: 1.25 ... 2.0
            )
        }
    }
}

@Test
func configurationRejectsInvalidPortraitAspectRatioBounds() {
    for range in [
        0 ... 0.75,
        -1 ... 0.75,
        0.5 ... Double.infinity,
    ] {
        #expect(
            throws: LayoutClassifier.ConfigurationError
                .invalidPortraitAspectRatio
        ) {
            try LayoutClassifier.Configuration(
                minimumWidth: 100,
                minimumHeight: 100,
                portraitAspectRatio: range,
                landscapeAspectRatio: 1.25 ... 2.0
            )
        }
    }
}

@Test
func configurationRejectsInvalidLandscapeAspectRatioBounds() {
    for range in [
        0 ... 2.0,
        -1 ... 2.0,
        1.25 ... Double.infinity,
    ] {
        #expect(
            throws: LayoutClassifier.ConfigurationError
                .invalidLandscapeAspectRatio
        ) {
            try LayoutClassifier.Configuration(
                minimumWidth: 100,
                minimumHeight: 100,
                portraitAspectRatio: 0.5 ... 0.75,
                landscapeAspectRatio: range
            )
        }
    }
}

@Test
func configurationRejectsOverlappingAspectRatios() {
    #expect(
        throws: LayoutClassifier.ConfigurationError.overlappingAspectRatios
    ) {
        try LayoutClassifier.Configuration(
            minimumWidth: 100,
            minimumHeight: 100,
            portraitAspectRatio: 0.5 ... 1.5,
            landscapeAspectRatio: 1.25 ... 2.0
        )
    }
}

@Test
func configurationRejectsAspectRatiosTouchingAtInclusiveEndpoint() {
    #expect(
        throws: LayoutClassifier.ConfigurationError.overlappingAspectRatios
    ) {
        try LayoutClassifier.Configuration(
            minimumWidth: 100,
            minimumHeight: 100,
            portraitAspectRatio: 0.5 ... 1.25,
            landscapeAspectRatio: 1.25 ... 2.0
        )
    }
}

private func boundaryConfiguration() throws
    -> LayoutClassifier.Configuration
{
    try LayoutClassifier.Configuration(
        minimumWidth: 100,
        minimumHeight: 100,
        portraitAspectRatio: 0.5 ... 0.75,
        landscapeAspectRatio: 1.25 ... 2.0
    )
}
