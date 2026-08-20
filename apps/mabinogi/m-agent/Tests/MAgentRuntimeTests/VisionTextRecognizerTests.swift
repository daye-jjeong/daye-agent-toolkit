import CoreGraphics
import Foundation
import Testing

@testable import MAgentRuntime

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

@Test(.timeLimit(.minutes(1)))
func unrelatedWorkKeepsRunningWhileRecognitionsPileUp() async throws {
    // 앞 테스트는 인식끼리만 본다. 진짜 위험은 인식이 협동 스레드풀을
    // 붙잡아 '관계없는 다른 일'까지 굶기는 것이다 — 그게 2026-07-25에
    // 자동화를 통째로 멈출 뻔한 모양이었다.
    //
    // 인식을 잔뜩 띄운 채로 짧은 잠을 반복한다. 스레드풀이 살아 있으면
    // 잠이 계속 깨고, 굶으면 여기서 멈춘다.
    let recognizer = VisionTextRecognizer()
    let image = try blankRecognizerImage(width: 800, height: 600)

    async let recognitions: Int = withThrowingTaskGroup(
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

    var ticks = 0
    while ticks < 20 {
        try await Task.sleep(for: .milliseconds(10))
        ticks += 1
    }

    let finished = try await recognitions
    #expect(ticks == 20)
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
