@preconcurrency import CoreGraphics
import Foundation
@preconcurrency import Vision

public struct VisionTextRecognizer: TextRecognizing, Sendable {
    private static let recognitionLanguages = ["ko-KR", "en-US"]
    private static let minimumTextHeight: Float = 0.01

    public init() {}

    public func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = Self.recognitionLanguages
        request.usesLanguageCorrection = true
        request.minimumTextHeight = Self.minimumTextHeight

        let handler = VNImageRequestHandler(
            cgImage: image,
            orientation: .up,
            options: [:]
        )
        try handler.perform([request])

        let imageSize = CGSize(width: image.width, height: image.height)
        return (request.results ?? []).compactMap { observation in
            guard
                let candidate = observation.topCandidates(1).first,
                let boundingBox = ObservationGeometry.topLeftPixelRect(
                    fromVisionNormalizedRect: observation.boundingBox,
                    imageSize: imageSize
                )
            else {
                return nil
            }
            return RecognizedTextObservation(
                text: candidate.string,
                confidence: Double(candidate.confidence),
                boundingBox: boundingBox
            )
        }
    }
}
