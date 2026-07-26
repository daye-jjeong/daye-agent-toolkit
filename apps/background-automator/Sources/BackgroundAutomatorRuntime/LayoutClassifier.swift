import BackgroundAutomatorCore
import CoreGraphics

public enum LayoutClassifier {
    public enum ConfigurationError: Error, Equatable, Sendable {
        case invalidMinimumWidth
        case invalidMinimumHeight
        case invalidPortraitAspectRatio
        case invalidLandscapeAspectRatio
        case overlappingAspectRatios
    }

    public struct Configuration: Equatable, Sendable {
        // landscape 하한 1.05: 마비노기 모바일(iPad 래퍼)은 near-square
        // 창(실측 1098×949, 비율 1.157)에서도 landscape UI를 렌더링한다.
        // 0.85...1.05 구간은 세로/가로 판별이 모호해 unsupported로 유지.
        public static let `default` = Configuration(
            validatedMinimumWidth: 480,
            validatedMinimumHeight: 480,
            portraitAspectRatio: 0.5 ... 0.85,
            landscapeAspectRatio: 1.05 ... 2.0
        )

        public let minimumWidth: Double
        public let minimumHeight: Double
        public let portraitAspectRatio: ClosedRange<Double>
        public let landscapeAspectRatio: ClosedRange<Double>

        public init(
            minimumWidth: Double,
            minimumHeight: Double,
            portraitAspectRatio: ClosedRange<Double>,
            landscapeAspectRatio: ClosedRange<Double>
        ) throws {
            guard minimumWidth.isFinite, minimumWidth > 0 else {
                throw ConfigurationError.invalidMinimumWidth
            }
            guard minimumHeight.isFinite, minimumHeight > 0 else {
                throw ConfigurationError.invalidMinimumHeight
            }
            guard Self.isValid(aspectRatio: portraitAspectRatio) else {
                throw ConfigurationError.invalidPortraitAspectRatio
            }
            guard Self.isValid(aspectRatio: landscapeAspectRatio) else {
                throw ConfigurationError.invalidLandscapeAspectRatio
            }
            guard !portraitAspectRatio.overlaps(landscapeAspectRatio) else {
                throw ConfigurationError.overlappingAspectRatios
            }

            self.init(
                validatedMinimumWidth: minimumWidth,
                validatedMinimumHeight: minimumHeight,
                portraitAspectRatio: portraitAspectRatio,
                landscapeAspectRatio: landscapeAspectRatio
            )
        }

        private init(
            validatedMinimumWidth minimumWidth: Double,
            validatedMinimumHeight minimumHeight: Double,
            portraitAspectRatio: ClosedRange<Double>,
            landscapeAspectRatio: ClosedRange<Double>
        ) {
            self.minimumWidth = minimumWidth
            self.minimumHeight = minimumHeight
            self.portraitAspectRatio = portraitAspectRatio
            self.landscapeAspectRatio = landscapeAspectRatio
        }

        private static func isValid(
            aspectRatio: ClosedRange<Double>
        ) -> Bool {
            aspectRatio.lowerBound.isFinite
                && aspectRatio.upperBound.isFinite
                && aspectRatio.lowerBound > 0
                && aspectRatio.upperBound > 0
        }
    }

    public static func classify(
        imageSize: CGSize,
        configuration: Configuration = .default
    ) -> LayoutProfile {
        let width = Double(imageSize.width)
        let height = Double(imageSize.height)

        guard width.isFinite,
              height.isFinite,
              width > 0,
              height > 0,
              width >= configuration.minimumWidth,
              height >= configuration.minimumHeight
        else {
            return .unsupported
        }

        let aspectRatio = width / height
        if configuration.portraitAspectRatio.contains(aspectRatio) {
            return .portraitMobile
        }
        if configuration.landscapeAspectRatio.contains(aspectRatio) {
            return .landscape
        }
        return .unsupported
    }
}
