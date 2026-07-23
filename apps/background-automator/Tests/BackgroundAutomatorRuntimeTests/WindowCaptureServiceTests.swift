import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func combinedCaptureRejectsReplacementReusingWindowID() async {
    let selected = candidate(
        windowID: 7,
        processID: 42,
        title: "Game"
    )
    let replacement = candidate(
        windowID: 7,
        processID: 99,
        title: "Game"
    )
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: replacement
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }

    let receivedExpected = await backend.receivedExpected
    #expect(receivedExpected == selected)
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func combinedCaptureReturnsFreshWindowMetadata() async throws {
    let selected = candidate(
        windowID: 7,
        frame: CGRect(x: 0, y: 0, width: 800, height: 600)
    )
    let movedAndResized = candidate(
        windowID: 7,
        frame: CGRect(x: 250, y: 100, width: 1280, height: 720)
    )
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: movedAndResized
    )
    let service = WindowCaptureService(backend: backend)

    let result = try await service.captureWindow(
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )

    #expect(result.candidate == movedAndResized)
    #expect(result.image.width == 1)
    #expect(result.image.height == 1)
}

@Test
func rawCaptureRejectsReplacementAfterFind() async throws {
    let selected = candidate(windowID: 7, processID: 42)
    let replacement = candidate(windowID: 7, processID: 99)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: selected
    )
    let service = WindowCaptureService(backend: backend)

    let found = try await service.findWindow(
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )
    #expect(found == selected)

    await backend.replaceCandidates(
        listedCandidates: [replacement],
        currentCandidate: replacement
    )

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.capture(windowID: 7)
    }
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func rawCaptureUsesBoundIdentityWhenWindowIsStable() async throws {
    let selected = candidate(windowID: 7, processID: 42)
    let moved = candidate(
        windowID: 7,
        processID: 42,
        frame: CGRect(x: 100, y: 50, width: 1280, height: 720)
    )
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: moved
    )
    let service = WindowCaptureService(backend: backend)

    _ = try await service.findWindow(
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )
    let image = try await service.capture(windowID: 7)

    #expect(image.width == 1)
    #expect(await backend.receivedExpected == selected)
    #expect(await backend.imageCaptureCount == 1)
}

@Test
func secondFindCannotRebindReplacementToExistingWindowID() async throws {
    let selected = candidate(windowID: 7, processID: 42)
    let replacement = candidate(windowID: 7, processID: 99)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: selected
    )
    let service = WindowCaptureService(backend: backend)

    _ = try await service.findWindow(
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )
    await backend.replaceCandidates(
        listedCandidates: [replacement],
        currentCandidate: replacement
    )

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.findWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.capture(windowID: 7)
    }
    #expect(await backend.imageCaptureCount == 0)
}

private actor FakeWindowCaptureBackend: WindowCaptureBackend {
    private var listedCandidates: [WindowCandidate]
    private var currentCandidate: WindowCandidate
    private(set) var receivedExpected: WindowCandidate?
    private(set) var imageCaptureCount = 0

    init(
        listedCandidates: [WindowCandidate],
        currentCandidate: WindowCandidate
    ) {
        self.listedCandidates = listedCandidates
        self.currentCandidate = currentCandidate
    }

    func listCandidates() async throws -> [WindowCandidate] {
        listedCandidates
    }

    func replaceCandidates(
        listedCandidates: [WindowCandidate],
        currentCandidate: WindowCandidate
    ) {
        self.listedCandidates = listedCandidates
        self.currentCandidate = currentCandidate
    }

    func capture(expected: WindowCandidate) async throws -> WindowCaptureResult {
        receivedExpected = expected
        guard WindowTarget.isCurrent(currentCandidate, matching: expected) else {
            throw WindowCaptureError.staleWindow(windowID: expected.windowID)
        }

        imageCaptureCount += 1
        return WindowCaptureResult(
            image: makeImage(),
            candidate: currentCandidate
        )
    }
}

private func candidate(
    windowID: UInt32,
    processID: Int32 = 42,
    bundleIdentifier: String = "com.example.target",
    title: String = "Game",
    frame: CGRect = CGRect(x: 0, y: 0, width: 800, height: 600),
    isOnScreen: Bool = true
) -> WindowCandidate {
    WindowCandidate(
        windowID: windowID,
        processID: processID,
        bundleIdentifier: bundleIdentifier,
        title: title,
        frame: frame,
        isOnScreen: isOnScreen
    )
}

private func makeImage() -> CGImage {
    let context = CGContext(
        data: nil,
        width: 1,
        height: 1,
        bitsPerComponent: 8,
        bytesPerRow: 4,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )
    return context!.makeImage()!
}
