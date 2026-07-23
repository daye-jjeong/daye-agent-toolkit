import BackgroundAutomatorCore
@preconcurrency import CoreGraphics
import Foundation

public struct RecognizedTextObservation: Equatable, Sendable {
    public let text: String
    public let confidence: Double
    public let boundingBox: CGRect

    public init(
        text: String,
        confidence: Double,
        boundingBox: CGRect
    ) {
        self.text = text
        self.confidence = confidence
        self.boundingBox = boundingBox
    }
}

public protocol TextRecognizing: Sendable {
    func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation]
}

public struct SceneActionCandidate: Equatable, Sendable {
    public let ruleID: String
    public let targetText: String?
    public let boundingBox: CGRect
    public let confidence: Double

    public init(
        ruleID: String,
        targetText: String?,
        boundingBox: CGRect,
        confidence: Double
    ) {
        self.ruleID = ruleID
        self.targetText = targetText
        self.boundingBox = boundingBox
        self.confidence = confidence
    }
}

public struct RuleAppearanceEvidence: Equatable, Sendable {
    public let contextBoundingBox: CGRect
    public let targetBoundingBox: CGRect
    public let contextStatistics: AppearanceStatistics
    public let targetStatistics: AppearanceStatistics

    public init(
        contextBoundingBox: CGRect,
        targetBoundingBox: CGRect,
        contextStatistics: AppearanceStatistics,
        targetStatistics: AppearanceStatistics
    ) {
        self.contextBoundingBox = contextBoundingBox
        self.targetBoundingBox = targetBoundingBox
        self.contextStatistics = contextStatistics
        self.targetStatistics = targetStatistics
    }
}

public struct SceneObservation: Equatable, Sendable {
    public let captureIdentity: CaptureIdentity?
    public let imageSize: CGSize?
    public let recognizedTexts: [RecognizedTextObservation]
    public let actionCandidates: [SceneActionCandidate]
    public let appearanceEvidence: [String: RuleAppearanceEvidence]

    public init(
        captureIdentity: CaptureIdentity? = nil,
        imageSize: CGSize? = nil,
        recognizedTexts: [RecognizedTextObservation],
        actionCandidates: [SceneActionCandidate],
        appearanceEvidence: [String: RuleAppearanceEvidence] = [:]
    ) {
        self.captureIdentity = captureIdentity
        self.imageSize = imageSize
        self.recognizedTexts = recognizedTexts
        self.actionCandidates = actionCandidates
        self.appearanceEvidence = appearanceEvidence
    }
}

public struct SceneObserver: Sendable {
    private static let blockedActionTexts = ["장면 넘기기"]

    private let textRecognizer: any TextRecognizing
    private let appearanceAnalyzer: any AppearanceAnalyzing

    public init(
        textRecognizer: any TextRecognizing = VisionTextRecognizer(),
        appearanceAnalyzer: any AppearanceAnalyzing =
            PixelAppearanceAnalyzer()
    ) {
        self.textRecognizer = textRecognizer
        self.appearanceAnalyzer = appearanceAnalyzer
    }

    public func observe(
        image: CGImage,
        layout: LayoutProfile,
        rules: [AutomationRule]
    ) async throws -> SceneObservation {
        try await observe(
            image: image,
            captureIdentity: nil,
            layout: layout,
            rules: rules
        )
    }

    public func observe(
        capture: WindowCaptureResult,
        layout: LayoutProfile,
        rules: [AutomationRule]
    ) async throws -> SceneObservation {
        try await observe(
            image: capture.image,
            captureIdentity: capture.captureIdentity,
            layout: layout,
            rules: rules
        )
    }

    func observe(
        image: CGImage,
        captureIdentity: CaptureIdentity,
        layout: LayoutProfile,
        rules: [AutomationRule]
    ) async throws -> SceneObservation {
        try await observe(
            image: image,
            captureIdentity: Optional(captureIdentity),
            layout: layout,
            rules: rules
        )
    }

    private func observe(
        image: CGImage,
        captureIdentity: CaptureIdentity?,
        layout: LayoutProfile,
        rules: [AutomationRule]
    ) async throws -> SceneObservation {
        let observations = try await textRecognizer.recognizeText(in: image)
        let imageSize = CGSize(width: image.width, height: image.height)
        var appearanceEvidence: [String: RuleAppearanceEvidence] = [:]
        for rule in rules {
            if let evidence = Self.appearanceEvidence(
                for: rule,
                observations: observations,
                image: image,
                layout: layout,
                analyzer: appearanceAnalyzer
            ) {
                appearanceEvidence[rule.id] = evidence
            }
        }
        let candidates = rules.compactMap {
            Self.actionCandidate(
                for: $0,
                observations: observations,
                layout: layout,
                imageSize: imageSize,
                appearanceEvidence: appearanceEvidence[$0.id]
            )
        }
        return SceneObservation(
            captureIdentity: captureIdentity,
            imageSize: imageSize,
            recognizedTexts: observations,
            actionCandidates: candidates,
            appearanceEvidence: appearanceEvidence
        )
    }
}

extension SceneObserver {
    static func actionCandidate(
        for rule: AutomationRule,
        observations: [RecognizedTextObservation],
        layout: LayoutProfile,
        imageSize: CGSize,
        appearanceEvidence: RuleAppearanceEvidence? = nil
    ) -> SceneActionCandidate? {
        guard
            layout != .unsupported,
            let region = rule.regions[layout]
        else {
            return nil
        }
        if let targetText = rule.action.targetText,
           blockedActionTexts.contains(where: {
               semanticText($0) == semanticText(targetText)
           }) {
            return nil
        }

        let blockingObservations = observations.filter {
            Self.isValidConfidence($0.confidence)
                && Self.isUsable(
                    $0.boundingBox,
                    imageSize: imageSize
                )
        }
        guard !Self.containsForbiddenText(
            rule.forbiddenTexts + blockedActionTexts,
            in: blockingObservations
        ) else {
            return nil
        }

        let confidentObservations = observations.filter {
            Self.isValidConfidence($0.confidence)
                && $0.confidence >= rule.minimumOCRConfidence
        }
        let observationsInRegion = confidentObservations.filter {
            Self.isCentered(
                $0.boundingBox,
                in: region,
                imageSize: imageSize
            )
        }
        var requiredObservations: [RecognizedTextObservation] = []
        for requiredText in rule.requiredTexts {
            let matches = observationsInRegion.filter {
                Self.semanticText($0.text) == Self.semanticText(requiredText)
            }
            guard matches.count == 1, let match = matches.first else {
                return nil
            }
            requiredObservations.append(match)
        }

        if let targetText = rule.action.targetText {
            let targets = observationsInRegion.filter {
                Self.semanticText($0.text) == Self.semanticText(targetText)
            }
            guard targets.count == 1, let target = targets.first else {
                return nil
            }
            guard Self.matchesAppearance(
                rule: rule,
                observations: confidentObservations,
                target: target,
                layout: layout,
                imageSize: imageSize,
                evidence: appearanceEvidence
            ) else {
                return nil
            }

            return SceneActionCandidate(
                ruleID: rule.id,
                targetText: targetText,
                boundingBox: target.boundingBox,
                confidence: target.confidence
            )
        }

        guard
            let safePointRegion = rule.action.safePointRegion,
            let safePointBoundingBox = Self.pixelRect(
                for: safePointRegion,
                imageSize: imageSize
            ),
            let confidence = requiredObservations
                .map(\.confidence)
                .min()
        else {
            return nil
        }

        return SceneActionCandidate(
            ruleID: rule.id,
            targetText: nil,
            boundingBox: safePointBoundingBox,
            confidence: confidence
        )
    }

    private static func appearanceEvidence(
        for rule: AutomationRule,
        observations: [RecognizedTextObservation],
        image: CGImage,
        layout: LayoutProfile,
        analyzer: any AppearanceAnalyzing
    ) -> RuleAppearanceEvidence? {
        guard
            let appearance = rule.appearance,
            let targetText = rule.action.targetText,
            let targetRegion = rule.regions[layout],
            let contextRegion = appearance.contextRegions[layout]
        else {
            return nil
        }
        let imageSize = CGSize(width: image.width, height: image.height)
        let confident = observations.filter {
            Self.isValidConfidence($0.confidence)
                && $0.confidence >= rule.minimumOCRConfidence
                && Self.isUsable($0.boundingBox, imageSize: imageSize)
        }
        let targets = confident.filter {
            Self.semanticText($0.text) == Self.semanticText(targetText)
                && Self.isCentered(
                    $0.boundingBox,
                    in: targetRegion,
                    imageSize: imageSize
                )
        }
        let contexts = confident.filter {
            Self.semanticText($0.text)
                == Self.semanticText(appearance.contextText)
                && Self.isCentered(
                    $0.boundingBox,
                    in: contextRegion,
                    imageSize: imageSize
                )
        }
        guard
            targets.count == 1,
            contexts.count == 1,
            let target = targets.first,
            let context = contexts.first,
            let contextStatistics = analyzer.statistics(
                in: image,
                around: context.boundingBox
            ),
            let targetStatistics = analyzer.statistics(
                in: image,
                around: target.boundingBox
            )
        else {
            return nil
        }
        return RuleAppearanceEvidence(
            contextBoundingBox: context.boundingBox,
            targetBoundingBox: target.boundingBox,
            contextStatistics: contextStatistics,
            targetStatistics: targetStatistics
        )
    }

    private static func matchesAppearance(
        rule: AutomationRule,
        observations: [RecognizedTextObservation],
        target: RecognizedTextObservation,
        layout: LayoutProfile,
        imageSize: CGSize,
        evidence: RuleAppearanceEvidence?
    ) -> Bool {
        guard let appearance = rule.appearance else {
            return true
        }
        guard
            let contextRegion = appearance.contextRegions[layout],
            let evidence,
            evidence.targetBoundingBox == target.boundingBox
        else {
            return false
        }
        let contexts = observations.filter {
            Self.semanticText($0.text)
                == Self.semanticText(appearance.contextText)
                && Self.isCentered(
                    $0.boundingBox,
                    in: contextRegion,
                    imageSize: imageSize
                )
        }
        guard
            contexts.count == 1,
            contexts.first?.boundingBox
                == evidence.contextBoundingBox,
            evidence.contextStatistics.sampleCount > 0,
            evidence.targetStatistics.sampleCount > 0,
            appearance.contextRange.contains(
                saturation:
                    evidence.contextStatistics.medianSaturation,
                luminance:
                    evidence.contextStatistics.medianLuminance
            ),
            appearance.targetRange.contains(
                saturation:
                    evidence.targetStatistics.medianSaturation,
                luminance:
                    evidence.targetStatistics.medianLuminance
            )
        else {
            return false
        }
        return true
    }

    private static func containsForbiddenText(
        _ forbiddenTexts: [String],
        in observations: [RecognizedTextObservation]
    ) -> Bool {
        let forbidden = Set(forbiddenTexts.map(Self.semanticText))
        return observations.contains {
            forbidden.contains(Self.semanticText($0.text))
        }
    }

    private static func isValidConfidence(_ confidence: Double) -> Bool {
        confidence.isFinite && (0 ... 1).contains(confidence)
    }

    private static func semanticText(_ text: String) -> String {
        text.unicodeScalars
            .filter { !CharacterSet.whitespacesAndNewlines.contains($0) }
            .map(String.init)
            .joined()
    }

    private static func isCentered(
        _ boundingBox: CGRect,
        in region: NormalizedRegion,
        imageSize: CGSize
    ) -> Bool {
        guard Self.isUsable(boundingBox, imageSize: imageSize) else {
            return false
        }

        let normalizedX = boundingBox.midX / imageSize.width
        let normalizedY = boundingBox.midY / imageSize.height
        return (region.minX ... region.maxX).contains(normalizedX)
            && (region.minY ... region.maxY).contains(normalizedY)
    }

    private static func isUsable(
        _ boundingBox: CGRect,
        imageSize: CGSize
    ) -> Bool {
        guard
            imageSize.width.isFinite,
            imageSize.height.isFinite,
            imageSize.width > 0,
            imageSize.height > 0,
            boundingBox.origin.x.isFinite,
            boundingBox.origin.y.isFinite,
            boundingBox.size.width.isFinite,
            boundingBox.size.height.isFinite,
            boundingBox.size.width > 0,
            boundingBox.size.height > 0
        else {
            return false
        }

        let maxX = boundingBox.origin.x + boundingBox.size.width
        let maxY = boundingBox.origin.y + boundingBox.size.height
        return maxX.isFinite
            && maxY.isFinite
            && maxX > 0
            && maxY > 0
            && boundingBox.origin.x < imageSize.width
            && boundingBox.origin.y < imageSize.height
    }

    private static func pixelRect(
        for region: NormalizedRegion,
        imageSize: CGSize
    ) -> CGRect? {
        let values = [
            region.minX,
            region.minY,
            region.maxX,
            region.maxY,
            Double(imageSize.width),
            Double(imageSize.height),
        ]
        guard
            values.allSatisfy(\.isFinite),
            imageSize.width > 0,
            imageSize.height > 0,
            (0 ... 1).contains(region.minX),
            (0 ... 1).contains(region.minY),
            (0 ... 1).contains(region.maxX),
            (0 ... 1).contains(region.maxY),
            region.minX < region.maxX,
            region.minY < region.maxY
        else {
            return nil
        }

        return CGRect(
            x: region.minX * imageSize.width,
            y: region.minY * imageSize.height,
            width: (region.maxX - region.minX) * imageSize.width,
            height: (region.maxY - region.minY) * imageSize.height
        )
    }
}
