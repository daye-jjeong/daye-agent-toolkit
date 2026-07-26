@preconcurrency import CoreGraphics
import Foundation
@preconcurrency import Vision

public struct VisionTextRecognizer: TextRecognizing, Sendable {
    private static let recognitionLanguages = ["ko-KR", "en-US"]
    private static let minimumTextHeight: Float = 0.01

    public init() {}

    /// Vision의 perform은 동기 블로킹 호출이라 async 함수에서 그대로 부르면
    /// 협동 스레드풀(코어 수만큼만 있다) 스레드를 통째로 점유한다. 앱은 클릭
    /// 루프와 사이클 관찰 루프가 각각 화면을 읽어 인식이 늘 겹치므로, 그대로
    /// 두면 풀이 고갈돼 자동화가 통째로 멈춘다. 전용 큐로 넘겨 격리한다.
    private static let queue = DispatchQueue(
        label: "BackgroundAutomator.VisionTextRecognizer",
        qos: .userInitiated,
        attributes: .concurrent
    )

    public func recognizeText(
        in image: CGImage
    ) async throws -> [RecognizedTextObservation] {
        try await withCheckedThrowingContinuation { continuation in
            Self.queue.async {
                continuation.resume(
                    with: Result {
                        try Self.recognizeTextSynchronously(in: image)
                    }
                )
            }
        }
    }

    private static func recognizeTextSynchronously(
        in image: CGImage
    ) throws -> [RecognizedTextObservation] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = Self.recognitionLanguages
        // 보정을 끄면 40% 빨라지지만(실측 392→233ms) 글자가 흔들린다 —
        // 2026-07-26 landscape-scene-skip-clear에서 '장면 넘기기'가
        // '장면 넘기기_'로 읽혀 exact-match가 깨졌다. 이 문자열은 컷신
        // 감지이자 다른 모든 규칙의 컷신 차단 가드라, 어긋나면 컷신을 못
        // 넘기는 데다 컷신 중 오클릭까지 열린다. 판당 1.5초를 주고 켠다.
        //
        // 보정을 켜면 장식 폰트 신뢰도가 1.00에서 0.50으로 내려가지만,
        // 규칙 문턱을 전부 0.45 이하로 낮춰 뒀으므로 전 장면이 잡힌다.
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
