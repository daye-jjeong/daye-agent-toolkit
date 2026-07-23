import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func concurrentCapturesAreSerializedInIdentityOrder() async throws {
    let visible = candidate(windowID: 7)
    let backend = ControlledCaptureBackend(candidate: visible)
    let service = WindowCaptureService(backend: backend)

    let firstTask = Task {
        try await service.captureWindow(matching: visible)
    }
    await backend.waitUntilCaptureStarts(1)

    let secondTask = Task {
        try await service.captureWindow(matching: visible)
    }
    let concurrentStart = await waitForQueuedCaptureOrConcurrentStart(
        service: service,
        backend: backend
    )

    #expect(!concurrentStart)
    #expect(await backend.captureStartCount == 1)

    await backend.completeCapture(1)
    let first = try await firstTask.value
    await backend.waitUntilCaptureStarts(2)
    await backend.completeCapture(2)
    let second = try await secondTask.value

    #expect(first.captureIdentity.sequence == 1)
    #expect(second.captureIdentity.sequence == 2)
    #expect(second.captureIdentity.isStrictlyNewer(
        than: first.captureIdentity
    ))
    #expect(!(await backend.concurrentStartDetected))
}

@Test
func cancelledCaptureWaiterReleasesQueueWithoutStartingBackend() async throws {
    let visible = candidate(windowID: 7)
    let backend = ControlledCaptureBackend(candidate: visible)
    let service = WindowCaptureService(backend: backend)

    let firstTask = Task {
        try await service.captureWindow(matching: visible)
    }
    await backend.waitUntilCaptureStarts(1)

    let cancelledTask = Task {
        try await service.captureWindow(matching: visible)
    }
    _ = await waitForQueuedCaptureOrConcurrentStart(
        service: service,
        backend: backend
    )
    cancelledTask.cancel()

    let thirdTask = Task {
        try await service.captureWindow(matching: visible)
    }
    await waitUntilQueuedCaptureCount(
        2,
        service: service,
        backend: backend
    )

    await backend.completeCapture(1)
    let first = try await firstTask.value
    await #expect(throws: CancellationError.self) {
        try await cancelledTask.value
    }
    await backend.waitUntilCaptureStarts(2)
    await backend.completeCapture(2)
    let third = try await thirdTask.value

    #expect(first.captureIdentity.sequence == 1)
    #expect(third.captureIdentity.sequence == 2)
    #expect(await backend.captureStartCount == 2)
    #expect(!(await backend.concurrentStartDetected))
}

@Test
func failedCaptureReleasesQueueForNextWaiter() async throws {
    let visible = candidate(windowID: 7)
    let backend = ControlledCaptureBackend(candidate: visible)
    let service = WindowCaptureService(backend: backend)

    let failingTask = Task {
        try await service.captureWindow(matching: visible)
    }
    await backend.waitUntilCaptureStarts(1)

    let nextTask = Task {
        try await service.captureWindow(matching: visible)
    }
    _ = await waitForQueuedCaptureOrConcurrentStart(
        service: service,
        backend: backend
    )

    await backend.failCapture(1)
    await #expect(throws: ControlledCaptureError.failed) {
        try await failingTask.value
    }
    await backend.waitUntilCaptureStarts(2)
    await backend.completeCapture(2)
    let next = try await nextTask.value

    #expect(next.captureIdentity.sequence == 1)
    #expect(!(await backend.concurrentStartDetected))
}

@Test
func captureResultsReceiveMonotonicSessionBoundIdentities() async throws {
    let visible = candidate(windowID: 7)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible
    )
    let sessionID = UUID(
        uuidString: "12345678-1234-1234-1234-123456789ABC"
    )!
    let service = WindowCaptureService(
        backend: backend,
        captureSessionID: sessionID
    )

    let first = try await service.captureWindow(matching: visible)
    let second = try await service.captureWindow(matching: visible)

    #expect(first.captureIdentity.sessionID == sessionID)
    #expect(first.captureIdentity.sequence == 1)
    #expect(second.captureIdentity.sequence == 2)
    #expect(second.captureIdentity.isStrictlyNewer(
        than: first.captureIdentity
    ))
}

@Test
func captureSessionRestartDoesNotCompareAsNewer() async throws {
    let visible = candidate(windowID: 7)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible
    )
    let firstService = WindowCaptureService(
        backend: backend,
        captureSessionID: UUID(
            uuidString: "AAAAAAAA-1234-1234-1234-123456789ABC"
        )!
    )
    let restartedService = WindowCaptureService(
        backend: backend,
        captureSessionID: UUID(
            uuidString: "BBBBBBBB-1234-1234-1234-123456789ABC"
        )!
    )

    let beforeRestart = try await firstService.captureWindow(
        matching: visible
    )
    let afterRestart = try await restartedService.captureWindow(
        matching: visible
    )

    #expect(!afterRestart.captureIdentity.isStrictlyNewer(
        than: beforeRestart.captureIdentity
    ))
}

@Test
func captureSequenceOverflowFailsSafeWithoutWrapping() async throws {
    let visible = candidate(windowID: 7)
    let backend = FakeWindowCaptureBackend(
        listedCandidates: [visible],
        currentCandidate: visible
    )
    let service = WindowCaptureService(
        backend: backend,
        nextCaptureSequence: .max
    )

    let final = try await service.captureWindow(matching: visible)
    #expect(final.captureIdentity.sequence == .max)
    await #expect(throws: WindowCaptureError.captureSequenceExhausted) {
        try await service.captureWindow(matching: visible)
    }
}

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

    func capture(expected: WindowCandidate) async throws -> WindowCaptureFrame {
        receivedExpected = expected
        guard WindowTarget.isCurrent(currentCandidate, matching: expected) else {
            throw WindowCaptureError.staleWindow(windowID: expected.windowID)
        }
        guard !nextAccessibilityMinimizedResponse() else {
            throw WindowCaptureError.staleWindow(windowID: expected.windowID)
        }

        imageCaptureCount += 1
        return WindowCaptureFrame(
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

private enum ControlledCaptureError: Error {
    case failed
}

private actor ControlledCaptureBackend: WindowCaptureBackend {
    private let candidate: WindowCandidate
    private var activeCaptureCount = 0
    private var captureContinuations: [
        Int: CheckedContinuation<WindowCaptureFrame, any Error>
    ] = [:]
    private var startWaiters: [
        (count: Int, continuation: CheckedContinuation<Void, Never>)
    ] = []

    private(set) var captureStartCount = 0
    private(set) var concurrentStartDetected = false

    init(candidate: WindowCandidate) {
        self.candidate = candidate
    }

    func listCandidates() async throws -> [WindowCandidate] {
        [candidate]
    }

    func accessibilityWindow(
        matching candidate: WindowCandidate
    ) async throws -> AccessibilityWindowState {
        AccessibilityWindowState(
            title: candidate.title,
            frame: candidate.frame,
            isMinimized: false
        )
    }

    func capture(
        expected: WindowCandidate
    ) async throws -> WindowCaptureFrame {
        captureStartCount += 1
        let captureNumber = captureStartCount
        if activeCaptureCount > 0 {
            concurrentStartDetected = true
        }
        activeCaptureCount += 1
        defer {
            activeCaptureCount -= 1
        }

        return try await withCheckedThrowingContinuation {
            continuation in
            captureContinuations[captureNumber] = continuation
            resumeStartWaiters()
        }
    }

    func waitUntilCaptureStarts(_ count: Int) async {
        guard captureStartCount < count else {
            return
        }
        await withCheckedContinuation { continuation in
            startWaiters.append((count, continuation))
        }
    }

    func completeCapture(_ number: Int) {
        captureContinuations.removeValue(forKey: number)?.resume(
            returning: WindowCaptureFrame(
                image: makeImage(),
                candidate: candidate
            )
        )
    }

    func failCapture(_ number: Int) {
        captureContinuations.removeValue(forKey: number)?.resume(
            throwing: ControlledCaptureError.failed
        )
    }

    private func resumeStartWaiters() {
        var pending: [
            (count: Int, continuation: CheckedContinuation<Void, Never>)
        ] = []
        for waiter in startWaiters {
            if captureStartCount >= waiter.count {
                waiter.continuation.resume()
            } else {
                pending.append(waiter)
            }
        }
        startWaiters = pending
    }
}

private func waitForQueuedCaptureOrConcurrentStart(
    service: WindowCaptureService,
    backend: ControlledCaptureBackend
) async -> Bool {
    while true {
        if await service.queuedCaptureCount > 0 {
            return false
        }
        if await backend.captureStartCount > 1 {
            return true
        }
        await Task.yield()
    }
}

private func waitUntilQueuedCaptureCount(
    _ count: Int,
    service: WindowCaptureService,
    backend: ControlledCaptureBackend
) async {
    while await service.queuedCaptureCount < count {
        if await backend.concurrentStartDetected {
            return
        }
        await Task.yield()
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
        isOnScreen: isOnScreen,
        processLifetimeIdentity: try! ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: 1_000
        )
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
