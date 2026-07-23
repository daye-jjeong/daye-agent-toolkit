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
func identityBoundCaptureRejectsReplacementReusingWindowID() async {
    let expected = candidate(
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
        listedCandidates: [replacement],
        currentCandidate: replacement
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.captureWindow(matching: expected)
    }

    #expect(await backend.receivedExpected == expected)
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func identityBoundCaptureReturnsFreshMetadataForSameWindow() async throws {
    let expected = candidate(
        windowID: 7,
        frame: CGRect(x: 0, y: 0, width: 800, height: 600)
    )
    let moved = candidate(
        windowID: 7,
        frame: CGRect(x: 200, y: 100, width: 1_280, height: 720)
    )
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [moved],
        currentCandidate: moved
    )
    let service = WindowCaptureService(backend: backend)

    let result = try await service.captureWindow(matching: expected)

    #expect(result.candidate == moved)
    #expect(await backend.receivedExpected == expected)
    #expect(await backend.imageCaptureCount == 1)
}

@Test
func combinedCaptureRejectsWindowMinimizedAtSelection() async {
    let minimized = candidate(windowID: 7, isOnScreen: false)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [minimized],
        currentCandidate: minimized
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowTargetError.notFound) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func combinedCaptureRejectsWindowMinimizedAfterSelection() async {
    let selected = candidate(windowID: 7, isOnScreen: true)
    let minimized = candidate(windowID: 7, isOnScreen: false)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [selected],
        currentCandidate: minimized
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func combinedCaptureRejectsAccessibilityMinimizedAtSelection() async {
    let visible = candidate(windowID: 7, isOnScreen: true)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible,
        accessibilityMinimizedResponses: [true]
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowTargetError.notFound) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func combinedCaptureRejectsAccessibilityMinimizedBeforeFreshCapture() async {
    let visible = candidate(windowID: 7, isOnScreen: true)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible,
        accessibilityMinimizedResponses: [false, true]
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: WindowCaptureError.staleWindow(windowID: 7)) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    #expect(await backend.imageCaptureCount == 0)
}

@Test
func combinedCaptureFailsSafeWhenAccessibilityIsUnavailable() async {
    let visible = candidate(windowID: 7, processID: 42)
    let expectedError = WindowVisibilityError.accessibilityNotTrusted(
        processID: 42
    )
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible,
        accessibilityError: expectedError
    )
    let service = WindowCaptureService(backend: backend)

    await #expect(throws: expectedError) {
        try await service.captureWindow(
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
    #expect(await backend.imageCaptureCount == 0)
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
    private var accessibilityMinimizedResponses: [Bool]
    private let accessibilityError: WindowVisibilityError?
    private(set) var receivedExpected: WindowCandidate?
    private(set) var imageCaptureCount = 0

    init(
        listedCandidates: [WindowCandidate],
        currentCandidate: WindowCandidate,
        accessibilityMinimizedResponses: [Bool] = [false],
        accessibilityError: WindowVisibilityError? = nil
    ) {
        self.listedCandidates = listedCandidates
        self.currentCandidate = currentCandidate
        self.accessibilityMinimizedResponses =
            accessibilityMinimizedResponses
        self.accessibilityError = accessibilityError
    }

    func listCandidates() async throws -> [WindowCandidate] {
        listedCandidates
    }

    func accessibilityWindow(
        matching candidate: WindowCandidate
    ) async throws -> AccessibilityWindowState {
        if let accessibilityError {
            throw accessibilityError
        }
        return AccessibilityWindowState(
            title: candidate.title,
            frame: candidate.frame,
            isMinimized: nextAccessibilityMinimizedResponse()
        )
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
        guard !nextAccessibilityMinimizedResponse() else {
            throw WindowCaptureError.staleWindow(windowID: expected.windowID)
        }

        imageCaptureCount += 1
        return WindowCaptureResult(
            image: makeImage(),
            candidate: currentCandidate
        )
    }

    private func nextAccessibilityMinimizedResponse() -> Bool {
        guard accessibilityMinimizedResponses.count > 1 else {
            return accessibilityMinimizedResponses.first ?? false
        }
        return accessibilityMinimizedResponses.removeFirst()
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
