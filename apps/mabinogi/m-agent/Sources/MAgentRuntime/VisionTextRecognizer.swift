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
    ///
    /// 그 큐를 한 줄로 세운다. 겹쳐 돌리면 각자 느려지기만 한다 — 실측
    /// 2026-08-01, 같은 그림 한 장 기준:
    ///
    ///     1개  652ms   1.5건/초
    ///     2개 1991ms   1.0건/초
    ///     3개 3468ms   0.9건/초
    ///
    /// Vision이 쓰는 가속기가 하나뿐이라 나눠 써도 총량이 안 늘고, 오히려
    /// 처리량이 떨어진다. 줄을 세우면 가장 늦게 끝나는 것끼리 비교해도
    /// 순차가 빠르다(3개: 1956ms 대 3468ms).
    ///
    /// 줄을 서도 데드락은 돌아오지 않는다. 기다리는 쪽은 continuation에서
    /// 잠들 뿐 협동 스레드풀 스레드를 잡고 있지 않다 — 2026-07-25에 문제가
    /// 된 것은 스레드를 '점유한 채' 블로킹한 것이었다.
    private static let queue = DispatchQueue(
        label: "MAgent.VisionTextRecognizer",
        qos: .userInitiated
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
