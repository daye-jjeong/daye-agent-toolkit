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

public struct SceneObservation: Equatable, Sendable {
    public let recognizedTexts: [RecognizedTextObservation]
    public let actionCandidates: [SceneActionCandidate]

    public init(
        recognizedTexts: [RecognizedTextObservation],
        actionCandidates: [SceneActionCandidate]
    ) {
        self.recognizedTexts = recognizedTexts
        self.actionCandidates = actionCandidates
    }
}

public struct SceneObserver: Sendable {
    private static let blockedActionTexts = ["장면 넘기기"]

    private let textRecognizer: any TextRecognizing

    public init(textRecognizer: any TextRecognizing = VisionTextRecognizer()) {
        self.textRecognizer = textRecognizer
    }

    public func observe(
        image: CGImage,
        layout: LayoutProfile,
        rules: [AutomationRule]
    ) async throws -> SceneObservation {
        let observations = try await textRecognizer.recognizeText(in: image)
        let imageSize = CGSize(width: image.width, height: image.height)
        let candidates = rules.compactMap {
            actionCandidate(
                for: $0,
                observations: observations,
                layout: layout,
                imageSize: imageSize
            )
        }
        return SceneObservation(
            recognizedTexts: observations,
            actionCandidates: candidates
        )
    }
}

private extension SceneObserver {
    func actionCandidate(
        for rule: AutomationRule,
        observations: [RecognizedTextObservation],
        layout: LayoutProfile,
        imageSize: CGSize
    ) -> SceneActionCandidate? {
        guard
            layout != .unsupported,
            let region = rule.regions[layout]
        else {
            return nil
        }
        if let targetText = rule.action.targetText,
           Self.blockedActionTexts.contains(where: {
               semanticText($0) == semanticText(targetText)
           }) {
            return nil
        }

        let blockingObservations = observations.filter {
            (0 ... 1).contains($0.confidence)
                && isUsable(
                    $0.boundingBox,
                    imageSize: imageSize
                )
        }
        guard !containsForbiddenText(
            rule.forbiddenTexts + Self.blockedActionTexts,
            in: blockingObservations
        ) else {
            return nil
        }

        let confidentObservations = observations.filter {
            $0.confidence.isFinite
                && $0.confidence >= rule.minimumOCRConfidence
        }
        let observationsInRegion = confidentObservations.filter {
            isCentered(
                $0.boundingBox,
                in: region,
                imageSize: imageSize
            )
        }
        var requiredObservations: [RecognizedTextObservation] = []
        for requiredText in rule.requiredTexts {
            let matches = observationsInRegion.filter {
                semanticText($0.text) == semanticText(requiredText)
            }
            guard matches.count == 1, let match = matches.first else {
                return nil
            }
            requiredObservations.append(match)
        }

        if let targetText = rule.action.targetText {
            let targets = observationsInRegion.filter {
                semanticText($0.text) == semanticText(targetText)
            }
            guard targets.count == 1, let target = targets.first else {
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
            let safePointBoundingBox = pixelRect(
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

    func containsForbiddenText(
        _ forbiddenTexts: [String],
        in observations: [RecognizedTextObservation]
    ) -> Bool {
        let forbidden = Set(forbiddenTexts.map(semanticText))
        return observations.contains {
            forbidden.contains(semanticText($0.text))
        }
    }

    func semanticText(_ text: String) -> String {
        text.unicodeScalars
            .filter { !CharacterSet.whitespacesAndNewlines.contains($0) }
            .map(String.init)
            .joined()
    }

    func isCentered(
        _ boundingBox: CGRect,
        in region: NormalizedRegion,
        imageSize: CGSize
    ) -> Bool {
        guard isUsable(boundingBox, imageSize: imageSize) else {
            return false
        }

        let normalizedX = boundingBox.midX / imageSize.width
        let normalizedY = boundingBox.midY / imageSize.height
        return (region.minX ... region.maxX).contains(normalizedX)
            && (region.minY ... region.maxY).contains(normalizedY)
    }

    func isUsable(
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

    func pixelRect(
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
