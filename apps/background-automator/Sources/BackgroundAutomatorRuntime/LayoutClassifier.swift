import BackgroundAutomatorCore
import CoreGraphics

public enum LayoutClassifier {
    public struct Configuration: Equatable, Sendable {
        public static let `default` = Configuration(
            minimumWidth: 480,
            minimumHeight: 480,
            portraitAspectRatio: 0.5 ... 0.85,
            landscapeAspectRatio: 1.25 ... 2.0
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
        ) {
            self.minimumWidth = minimumWidth
            self.minimumHeight = minimumHeight
            self.portraitAspectRatio = portraitAspectRatio
            self.landscapeAspectRatio = landscapeAspectRatio
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
