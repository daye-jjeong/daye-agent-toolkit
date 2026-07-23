import Foundation
@preconcurrency import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func idleThresholdIsInclusive() {
    let clock = ContinuousClock()
    let start = clock.now
    let state = UserInputState(
        generation: 0,
        lastInputAt: start
    )

    #expect(
        !state.isIdle(
            at: start.advanced(by: .milliseconds(2_900)),
            for: .seconds(3)
        )
    )
    #expect(
        state.isIdle(
            at: start.advanced(by: .seconds(3)),
            for: .seconds(3)
        )
    )
}

@Test
func genuineInputUpdatesTimestampAndGeneration() {
    let clock = ContinuousClock()
    let start = clock.now
    let inputTime = start.advanced(by: .seconds(2))
    var state = UserInputState(
        generation: 41,
        lastInputAt: start
    )

    state.recordInput(
        at: inputTime,
        sourceIdentifier: nil
    )

    #expect(state.snapshot.generation == 42)
    #expect(state.snapshot.lastInputAt == inputTime)
}

@Test
func syntheticInputDoesNotResetIdleStateOrGeneration() {
    let clock = ContinuousClock()
    let start = clock.now
    var state = UserInputState(
        generation: 12,
        lastInputAt: start
    )

    state.recordInput(
        at: start.advanced(by: .seconds(2)),
        sourceIdentifier: AutomatorSyntheticEvent.sourceIdentifier
    )

    #expect(
        state.snapshot
            == UserInputSnapshot(
                generation: 12,
                lastInputAt: start
            )
    )
}

@Test
func nonMonotonicInputDoesNotMoveLastInputBackward() {
    let clock = ContinuousClock()
    let start = clock.now
    var state = UserInputState(
        generation: 7,
        lastInputAt: start.advanced(by: .seconds(10))
    )

    state.recordInput(
        at: start.advanced(by: .seconds(9)),
        sourceIdentifier: nil
    )

    #expect(state.snapshot.generation == 8)
    #expect(
        state.snapshot.lastInputAt
            == start.advanced(by: .seconds(10))
    )
    #expect(
        !state.isIdle(
            at: start.advanced(by: .seconds(9)),
            for: .zero
        )
    )
    #expect(
        state.timeUntilIdle(
            at: start.advanced(by: .seconds(9)),
            for: .seconds(3)
        ) == .seconds(4)
    )
}

@Test
func generationOverflowSaturatesWithoutTrapping() {
    let clock = ContinuousClock()
    let start = clock.now
    let inputTime = start.advanced(by: .seconds(1))
    var state = UserInputState(
        generation: .max,
        lastInputAt: start
    )

    state.recordInput(
        at: inputTime,
        sourceIdentifier: nil
    )

    #expect(state.snapshot.generation == .max)
    #expect(state.snapshot.lastInputAt == inputTime)
}

@Test
func monitorExposesRequiredSendableAbstraction() async {
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 3,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )
    let abstraction: any UserIdleMonitoring = monitor

    let snapshot = await abstraction.snapshot()

    #expect(snapshot.generation == 3)
}

@Test
func monitoringLifecycleIsExplicitAndStartFailureIsSurfaced() {
    let expected = TestInputEventTapError.permissionDenied
    let tap = RecordingInputEventTap(startError: expected)
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )

    #expect(!monitor.isMonitoring)
    #expect(throws: expected) {
        try monitor.start()
    }
    #expect(!monitor.isMonitoring)
    #expect(tap.startCount == 1)
}

@Test
func stoppingMonitorStopsEventTap() throws {
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )

    try monitor.start()
    #expect(monitor.isMonitoring)

    monitor.stop()

    #expect(!monitor.isMonitoring)
    #expect(tap.stopCount == 1)
}

@Test
func waitingWithoutActiveMonitoringFailsSafe() async {
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: RecordingInputEventTap()
    )

    await #expect(throws: UserIdleMonitorError.notMonitoring) {
        try await monitor.waitUntilIdle(for: .zero)
    }
}

@Test
func negativeIdleDurationIsRejected() async throws {
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: RecordingInputEventTap()
    )
    try monitor.start()

    await #expect(
        throws: UserIdleMonitorError.invalidIdleDuration
    ) {
        try await monitor.waitUntilIdle(
            for: .milliseconds(-1)
        )
    }
}

@Test
func waitUntilIdleWaitsForRequestedDuration() async throws {
    let clock = ContinuousClock()
    let start = clock.now
    let monitor = UserIdleMonitor(
        initialGeneration: 5,
        lastInputAt: start,
        eventTap: RecordingInputEventTap()
    )
    try monitor.start()

    let result = try await monitor.waitUntilIdle(
        for: .milliseconds(30)
    )
    let returnedAt = clock.now

    #expect(result.generation == 5)
    #expect(
        result.lastInputAt.duration(to: returnedAt)
            >= .milliseconds(30)
    )
}

@Test
func waitUntilIdleIsCancellationAware() async throws {
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: RecordingInputEventTap()
    )
    try monitor.start()
    let task = Task {
        try await monitor.waitUntilIdle(for: .seconds(30))
    }

    await Task.yield()
    task.cancel()

    await #expect(throws: CancellationError.self) {
        try await task.value
    }
}

@Test
func eventCallbackObservesUserInputAndReturnsItUnchanged() throws {
    let recorder = InputObservationRecorder()
    let context = InputEventTapContext(
        observe: { sourceIdentifier in
            recorder.record(sourceIdentifier)
        },
        reenable: {}
    )
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )

    let returned = context.handle(
        type: .mouseMoved,
        event: event
    )

    #expect(returned === event)
    #expect(recorder.sourceIdentifiers == [0])
}

@Test
func eventCallbackIgnoresTaggedSyntheticInput() throws {
    let recorder = InputObservationRecorder()
    let context = InputEventTapContext(
        observe: { sourceIdentifier in
            recorder.record(sourceIdentifier)
        },
        reenable: {}
    )
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDown,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )
    event.setIntegerValueField(
        .eventSourceUserData,
        value: AutomatorSyntheticEvent.sourceIdentifier
    )

    let returned = context.handle(
        type: .leftMouseDown,
        event: event
    )

    #expect(returned === event)
    #expect(recorder.sourceIdentifiers.isEmpty)
}

@Test(
    arguments: [
        CGEventType.tapDisabledByTimeout,
        CGEventType.tapDisabledByUserInput,
    ]
)
func disabledEventTapIsReenabledWithoutObservingInput(
    type: CGEventType
) throws {
    let recorder = InputObservationRecorder()
    let reenableCounter = Counter()
    let context = InputEventTapContext(
        observe: { sourceIdentifier in
            recorder.record(sourceIdentifier)
        },
        reenable: {
            reenableCounter.increment()
        }
    )
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )

    let returned = context.handle(type: type, event: event)

    #expect(returned === event)
    #expect(reenableCounter.value == 1)
    #expect(recorder.sourceIdentifiers.isEmpty)
}

private enum TestInputEventTapError: Error {
    case permissionDenied
}

private final class RecordingInputEventTap:
    InputEventTapping,
    @unchecked Sendable
{
    private let lock = NSLock()
    private let startError: (any Error)?
    private var storedIsRunning = false
    private var storedStartCount = 0
    private var storedStopCount = 0

    init(startError: (any Error)? = nil) {
        self.startError = startError
    }

    var isRunning: Bool {
        lock.withLock { storedIsRunning }
    }

    var startCount: Int {
        lock.withLock { storedStartCount }
    }

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    func start() throws {
        try lock.withLock {
            storedStartCount += 1
            if let startError {
                throw startError
            }
            storedIsRunning = true
        }
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
            storedIsRunning = false
        }
    }
}

private final class InputObservationRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var storedSourceIdentifiers: [Int64] = []

    var sourceIdentifiers: [Int64] {
        lock.withLock { storedSourceIdentifiers }
    }

    func record(_ sourceIdentifier: Int64) {
        lock.withLock {
            storedSourceIdentifiers.append(sourceIdentifier)
        }
    }
}

private final class Counter: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue = 0

    var value: Int {
        lock.withLock { storedValue }
    }

    func increment() {
        lock.withLock {
            storedValue += 1
        }
    }
}
