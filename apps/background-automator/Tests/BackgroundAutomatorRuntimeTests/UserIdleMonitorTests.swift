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
func generationOverflowWrapsWithoutTrappingAndInvalidatesSnapshot() {
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

    #expect(state.snapshot.generation == 0)
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
func delayedFirstStartResetsIdleBaselineAndGeneration() async throws {
    let clock = ContinuousClock()
    let createdAt = clock.now
    let startedAt = createdAt.advanced(by: .seconds(10))
    let nowSource = ControlledNow(startedAt)
    let monitor = UserIdleMonitor(
        initialGeneration: 4,
        lastInputAt: createdAt,
        now: { nowSource.value },
        eventTap: RecordingInputEventTap()
    )

    try monitor.start()
    let snapshot = await monitor.snapshot()

    #expect(snapshot.generation == 5)
    #expect(snapshot.lastInputAt == startedAt)
}

@Test
func restartResetsBaselineAfterUnobservedStoppedGap() async throws {
    let clock = ContinuousClock()
    let firstStart = clock.now
    let nowSource = ControlledNow(firstStart)
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 8,
        lastInputAt: firstStart.advanced(by: .seconds(-10)),
        now: { nowSource.value },
        eventTap: tap
    )

    try monitor.start()
    monitor.stop()
    let restartedAt = firstStart.advanced(by: .seconds(20))
    nowSource.set(restartedAt)
    try monitor.start()
    let snapshot = await monitor.snapshot()

    #expect(snapshot.generation == 10)
    #expect(snapshot.lastInputAt == restartedAt)
}

@Test
func startBaselineDoesNotOverwriteNewerInputRecordedDuringStart() {
    let clock = ContinuousClock()
    let original = clock.now
    let startBaseline = original.advanced(by: .seconds(10))
    let newerInput = original.advanced(by: .seconds(11))
    var state = UserInputState(
        generation: 20,
        lastInputAt: original
    )
    state.recordInput(
        at: newerInput,
        sourceIdentifier: nil
    )

    state.recordMonitoringStart(at: startBaseline)

    #expect(state.snapshot.generation == 22)
    #expect(state.snapshot.lastInputAt == newerInput)
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

    #expect(result.generation == 6)
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

@Test
func invalidExistingTapIsCleanedUpAndRecreatedOnStart() throws {
    let driver = RecordingEventTapLifecycleDriver()
    let tap = PassiveInputEventTap(
        observe: { _ in },
        driver: driver
    )
    #expect(try tap.start())
    driver.setHealth(isValid: false, isEnabled: false)
    #expect(!tap.isRunning)

    let restarted = try tap.start()

    #expect(restarted)
    #expect(tap.isRunning)
    #expect(driver.startCount == 2)
    #expect(driver.stopCount == 2)
}

@Test
func disabledExistingTapIsCleanedUpAndRecreatedOnStart() throws {
    let driver = RecordingEventTapLifecycleDriver()
    let tap = PassiveInputEventTap(
        observe: { _ in },
        driver: driver
    )
    #expect(try tap.start())
    driver.setHealth(isValid: true, isEnabled: false)
    #expect(!tap.isRunning)

    let restarted = try tap.start()

    #expect(restarted)
    #expect(tap.isRunning)
    #expect(driver.startCount == 2)
    #expect(driver.stopCount == 2)
}

@Test
func failedDisabledTapReenableMarksTapUnhealthyAndAllowsRecovery()
    throws
{
    let driver = RecordingEventTapLifecycleDriver(
        reenableSucceeds: false
    )
    let tap = PassiveInputEventTap(
        observe: { _ in },
        driver: driver
    )
    #expect(try tap.start())
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )
    driver.setHealth(isValid: true, isEnabled: false)

    _ = tap.context.handle(
        type: .tapDisabledByTimeout,
        event: event
    )

    #expect(driver.reenableCount == 1)
    #expect(!tap.isRunning)

    driver.setReenableSucceeds(true)
    let restarted = try tap.start()

    #expect(restarted)
    #expect(tap.isRunning)
    #expect(driver.startCount == 2)
}

@Test
func successfulTapReenableStartsConservativeMonitoringEpoch()
    throws
{
    let clock = ContinuousClock()
    let original = clock.now
    let recoveryTime = original.advanced(by: .seconds(5))
    let state = LockedTestUserInputState(
        generation: 30,
        lastInputAt: original
    )
    let recorder = InputObservationRecorder()
    let driver = RecordingEventTapLifecycleDriver()
    let tap = PassiveInputEventTap(
        observe: { sourceIdentifier in
            recorder.record(sourceIdentifier)
        },
        onRecovery: {
            state.recordMonitoringStart(at: recoveryTime)
        },
        driver: driver
    )
    #expect(try tap.start())
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )
    driver.setHealth(isValid: true, isEnabled: false)

    _ = tap.context.handle(
        type: .tapDisabledByUserInput,
        event: event
    )

    #expect(tap.isRunning)
    #expect(
        state.snapshot
            == UserInputSnapshot(
                generation: 31,
                lastInputAt: recoveryTime
            )
    )
    #expect(recorder.sourceIdentifiers.isEmpty)
}

@Test
func recoveryEpochDoesNotOverwriteNewerConcurrentInput()
    throws
{
    let clock = ContinuousClock()
    let original = clock.now
    let recoveryTime = original.advanced(by: .seconds(5))
    let newerInput = original.advanced(by: .seconds(6))
    let state = LockedTestUserInputState(
        generation: 40,
        lastInputAt: original
    )
    state.recordInput(at: newerInput)
    let driver = RecordingEventTapLifecycleDriver()
    let tap = PassiveInputEventTap(
        observe: { _ in },
        onRecovery: {
            state.recordMonitoringStart(at: recoveryTime)
        },
        driver: driver
    )
    #expect(try tap.start())
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )
    driver.setHealth(isValid: true, isEnabled: false)

    _ = tap.context.handle(
        type: .tapDisabledByTimeout,
        event: event
    )

    #expect(
        state.snapshot
            == UserInputSnapshot(
                generation: 42,
                lastInputAt: newerInput
            )
    )
}

@Test
func tapStaysUnhealthyUntilRecoveryEpochIsCommitted()
    async throws
{
    let clock = ContinuousClock()
    let original = clock.now
    let recoveryTime = original.advanced(by: .seconds(5))
    let state = LockedTestUserInputState(
        generation: 50,
        lastInputAt: original
    )
    let recoveryGate = RecoveryGate()
    let driver = RecordingEventTapLifecycleDriver()
    let tap = PassiveInputEventTap(
        observe: { _ in },
        onRecovery: {
            recoveryGate.pause()
            state.recordMonitoringStart(at: recoveryTime)
        },
        driver: driver
    )
    #expect(try tap.start())
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: .zero,
            mouseButton: .left
        )
    )
    driver.setHealth(isValid: true, isEnabled: false)

    let recoveryTask = Task.detached {
        _ = tap.context.handle(
            type: .tapDisabledByTimeout,
            event: event
        )
    }
    for _ in 0 ..< 1_000 {
        if recoveryGate.hasPaused {
            break
        }
        try await Task.sleep(for: .milliseconds(1))
    }
    #expect(recoveryGate.hasPaused)

    #expect(!tap.isRunning)
    #expect(
        state.snapshot
            == UserInputSnapshot(
                generation: 50,
                lastInputAt: original
            )
    )

    recoveryGate.resume()
    await recoveryTask.value

    #expect(tap.isRunning)
    #expect(
        state.snapshot
            == UserInputSnapshot(
                generation: 51,
                lastInputAt: recoveryTime
            )
    )
}

@Test
func aTapKilledByTheSystemIsRevivedOnRetry() throws {
    // 회귀(2026-08-01 07:52~07:59, 6분 46초 멈춤): macOS는 이벤트 탭
    // 콜백이 늦으면 탭을 스스로 끈다. 그러면 waitUntilIdle이 매번
    // notMonitoring을 던지는데, 재시도 루프는 runCycle만 다시 부를 뿐
    // 감시를 되살리지 않아 사람이 앱을 껐다 켤 때까지 굳었다.
    // 화면도 후보도 멀쩡했고 감시만 죽어 있었다.
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )

    try monitor.start()
    tap.simulateSystemDisable()
    #expect(!monitor.isMonitoring)

    try monitor.restartIfDisabled()

    #expect(monitor.isMonitoring)
    #expect(tap.startCount == 2)
}

@Test
func anIntentionallyStoppedMonitorIsNotRevived() throws {
    // 사람이 멈춘 감시까지 되살리면 중지가 중지가 아니게 된다.
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )

    try monitor.start()
    monitor.stop()

    try monitor.restartIfDisabled()

    #expect(!monitor.isMonitoring)
    #expect(tap.startCount == 1)
}

@Test
func aHealthyMonitorIsLeftAloneByRestart() throws {
    // 멀쩡한 감시를 다시 시작하면 유휴 기준선이 밀려 클릭이 늦어진다.
    let tap = RecordingInputEventTap()
    let monitor = UserIdleMonitor(
        initialGeneration: 0,
        lastInputAt: ContinuousClock().now,
        eventTap: tap
    )

    try monitor.start()
    try monitor.restartIfDisabled()

    #expect(monitor.isMonitoring)
    #expect(tap.startCount == 1)
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

    func start() throws -> Bool {
        try lock.withLock {
            storedStartCount += 1
            if let startError {
                throw startError
            }
            if storedIsRunning {
                return false
            }
            storedIsRunning = true
            return true
        }
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
            storedIsRunning = false
        }
    }

    /// macOS가 탭을 스스로 끈 상황. stop()과 달리 앱은 이 사실을 모른다.
    func simulateSystemDisable() {
        lock.withLock { storedIsRunning = false }
    }
}

private final class RecordingEventTapLifecycleDriver:
    EventTapLifecycleDriving,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var storedIsValid = false
    private var storedIsEnabled = false
    private var storedReenableSucceeds: Bool
    private var storedStartCount = 0
    private var storedStopCount = 0
    private var storedReenableCount = 0

    init(reenableSucceeds: Bool = true) {
        storedReenableSucceeds = reenableSucceeds
    }

    var isValid: Bool {
        lock.withLock { storedIsValid }
    }

    var isEnabled: Bool {
        lock.withLock { storedIsEnabled }
    }

    var startCount: Int {
        lock.withLock { storedStartCount }
    }

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    var reenableCount: Int {
        lock.withLock { storedReenableCount }
    }

    func start(context: InputEventTapContext) throws {
        lock.withLock {
            _ = context
            storedStartCount += 1
            storedIsValid = true
            storedIsEnabled = true
        }
    }

    func reenable() -> Bool {
        lock.withLock {
            storedReenableCount += 1
            if storedReenableSucceeds && storedIsValid {
                storedIsEnabled = true
                return true
            }
            return false
        }
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
            storedIsValid = false
            storedIsEnabled = false
        }
    }

    func setHealth(
        isValid: Bool,
        isEnabled: Bool
    ) {
        lock.withLock {
            storedIsValid = isValid
            storedIsEnabled = isEnabled
        }
    }

    func setReenableSucceeds(_ succeeds: Bool) {
        lock.withLock {
            storedReenableSucceeds = succeeds
        }
    }
}

private final class ControlledNow: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue: ContinuousClock.Instant

    init(_ value: ContinuousClock.Instant) {
        storedValue = value
    }

    var value: ContinuousClock.Instant {
        lock.withLock { storedValue }
    }

    func set(_ value: ContinuousClock.Instant) {
        lock.withLock {
            storedValue = value
        }
    }
}

private final class LockedTestUserInputState: @unchecked Sendable {
    private let lock = NSLock()
    private var state: UserInputState

    init(
        generation: UInt64,
        lastInputAt: ContinuousClock.Instant
    ) {
        state = UserInputState(
            generation: generation,
            lastInputAt: lastInputAt
        )
    }

    var snapshot: UserInputSnapshot {
        lock.withLock { state.snapshot }
    }

    func recordInput(at timestamp: ContinuousClock.Instant) {
        lock.withLock {
            state.recordInput(
                at: timestamp,
                sourceIdentifier: nil
            )
        }
    }

    func recordMonitoringStart(
        at timestamp: ContinuousClock.Instant
    ) {
        lock.withLock {
            state.recordMonitoringStart(at: timestamp)
        }
    }
}

private final class RecoveryGate: @unchecked Sendable {
    private let lock = NSLock()
    private let resumeSemaphore = DispatchSemaphore(value: 0)
    private var storedHasPaused = false

    var hasPaused: Bool {
        lock.withLock { storedHasPaused }
    }

    func pause() {
        lock.withLock {
            storedHasPaused = true
        }
        resumeSemaphore.wait()
    }

    func resume() {
        resumeSemaphore.signal()
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
