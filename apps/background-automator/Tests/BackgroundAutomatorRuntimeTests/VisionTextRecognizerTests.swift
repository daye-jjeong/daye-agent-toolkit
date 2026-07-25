import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test(.timeLimit(.minutes(1)))
func concurrentRecognitionsAllFinishWithoutStarvingTheThreadPool() async throws {
    // Vision의 perform은 동기 블로킹 호출이라, async 함수에서 그대로 부르면
    // 협동 스레드풀(코어 수만큼만 있다) 스레드를 통째로 점유한다. 동시 호출이
    // 코어 수를 넘으면 풀이 고갈돼 전부 멈춘다.
    //
    // 앱은 클릭 루프와 사이클 관찰 루프가 각각 화면을 읽으므로 인식이 항상
    // 겹친다. 여기서 막히면 자동화가 통째로 정지한다.
    let recognizer = VisionTextRecognizer()
    let image = try blankRecognizerImage(width: 400, height: 300)

    let finished = try await withThrowingTaskGroup(
        of: Int.self
    ) { group in
        for _ in 0 ..< 12 {
            group.addTask {
                _ = try await recognizer.recognizeText(in: image)
                return 1
            }
        }
        return try await group.reduce(0, +)
    }

    #expect(finished == 12)
}

private func blankRecognizerImage(
    width: Int,
    height: Int
) throws -> CGImage {
    let context = try #require(
        CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )
    )
    return try #require(context.makeImage())
}
