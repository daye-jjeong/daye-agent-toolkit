import CoreGraphics
import Darwin
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func restorationFailureKoreanDescriptionsAreHumanReadable() {
    #expect(
        ForegroundRestorationFailure
            .pointerRestoreFailed("denied")
            .koreanDescription == "포인터 복원 실패(denied)"
    )
    #expect(
        ForegroundRestorationFailure
            .originalApplicationUnavailable(
                ApplicationIdentity(
                    processIdentifier: 42,
                    bundleIdentifier: "com.game"
                )
            )
            .koreanDescription == "원래 앱 종료됨(com.game)"
    )
    #expect(
        ForegroundRestorationFailure
            .originalApplicationActivationFailed("timeout")
            .koreanDescription == "원래 앱 활성화 실패(timeout)"
    )
    #expect(
        ForegroundRestorationFailure
            .originalApplicationNotFrontmost
            .koreanDescription == "원래 앱이 최전면으로 복귀 실패"
    )
}

@Test
func foregroundActionActivatesClicksWaitsAndRestoresInOrder() async throws {
    let original = ApplicationIdentity(
        processIdentifier: 10,
        bundleIdentifier: "com.example.editor"
    )
    let game = ApplicationIdentity(
        processIdentifier: 20,
        bundleIdentifier: "com.example.game"
    )
    let log = ForegroundActionTestLog()
    let applications = FakeApplicationCoordinator(
        frontmost: original,
        running: [original, game],
        log: log
    )
    let pointer = FakePointerController(
        location: CGPoint(x: 12, y: 34),
        log: log
    )
    let clicker = FakeGlobalClicker(log: log)
    let sleeper = FakeActionSleeper(log: log)
    let monitor = FakeForegroundInputMonitor(
        snapshots: [inputSnapshot(generation: 7)],
        log: log
    )
    let coordinator = ForegroundActionCoordinator(
        applications: applications,
        pointer: pointer,
        clicker: clicker,
        sleeper: sleeper,
        inputMonitor: monitor,
        postActionDelay: .milliseconds(500)
    )

    let result = try await coordinator.perform(
        targetApplication: game,
        targetBox: CGRect(x: 100, y: 200, width: 80, height: 40),
        expectedInputGeneration: 7
    )

    #expect(result.originalApplication == original)
    #expect(result.targetApplication == game)
    #expect(result.pointerBefore == CGPoint(x: 12, y: 34))
    #expect(result.targetPoint == CGPoint(x: 140, y: 220))
    #expect(result.pointerRestored == CGPoint(x: 12, y: 34))
    #expect(result.expectedInputGeneration == 7)
    #expect(result.inputGenerationBeforeClick == 7)
    #expect(result.restoration == .restoredOriginalApplication)
    #expect(
        log.entries == [
            "applications.frontmost",
            "pointer.location",
            "applications.activate:20",
            "applications.isFrontmost:20",
            "input.snapshot",
            "pointer.move:140.0,220.0:\(AutomatorSyntheticEvent.sourceIdentifier)",
            "input.snapshot",
            "applications.isFrontmost:20",
            "click:140.0,220.0:\(AutomatorSyntheticEvent.sourceIdentifier)",
            "sleep:0.5 seconds",
            "pointer.move:12.0,34.0:\(AutomatorSyntheticEvent.sourceIdentifier)",
            "applications.isRunning:10",
            "applications.activate:10",
            "applications.isFrontmost:10",
        ]
    )
    #expect(clicker.clicks.count == 1)
}

@Test
func globalClickPostsOneTaggedDownUpPair() throws {
    let point = CGPoint(x: 140, y: 220)
    let factory = RecordingGlobalClickEventFactory(
        events: try #require(makeForegroundTestClickEvents(at: point))
    )
    let poster = RecordingGlobalEventPoster()
    let service = GlobalClickService(
        eventFactory: factory,
        eventPoster: poster
    )

    try service.click(
        screenPoint: point,
        sourceIdentifier: AutomatorSyntheticEvent.sourceIdentifier
    )

    #expect(factory.requestedPoints == [point])
    #expect(poster.records.map(\.eventType) == [.leftMouseDown, .leftMouseUp])
    #expect(
        poster.records.map(\.sourceIdentifier)
            == [
                AutomatorSyntheticEvent.sourceIdentifier,
                AutomatorSyntheticEvent.sourceIdentifier,
            ]
    )
}

@Test
func pointerMovePostsOneTaggedSyntheticMove() throws {
    let point = CGPoint(x: 140, y: 220)
    let event = try #require(
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: point,
            mouseButton: .left
        )
    )
    let factory = RecordingPointerMoveEventFactory(event: event)
    let poster = RecordingGlobalEventPoster()
    let controller = CoreGraphicsPointerController(
        eventFactory: factory,
        eventPoster: poster,
        locationReader: { CGPoint(x: 1, y: 2) }
    )

    try controller.move(
        to: point,
        sourceIdentifier: AutomatorSyntheticEvent.sourceIdentifier
    )

    #expect(factory.requestedPoints == [point])
    #expect(poster.records.map(\.eventType) == [.mouseMoved])
    #expect(
        poster.records.map(\.sourceIdentifier)
            == [AutomatorSyntheticEvent.sourceIdentifier]
    )
}

@Test
func changedInputGenerationCancelsBeforePointerOrClickAndRestoresFocus() async {
    let fixture = makeForegroundFixture(
        initialGeneration: 11,
        observedGeneration: 12
    )

    await expectCoordinatorError(
        primary: .inputGenerationChanged(expected: 11, actual: 12),
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(
        fixture.log.entries.suffix(3) == [
            "applications.isRunning:10",
            "applications.activate:10",
            "applications.isFrontmost:10",
        ]
    )
}

@Test
func inputChangedAfterPointerMoveCancelsImmediatelyBeforeClick() async {
    let fixture = makeForegroundFixture(
        observedGenerations: [11, 12]
    )

    await expectCoordinatorError(
        primary: .inputGenerationChanged(expected: 11, actual: 12),
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.clicker.clicks.isEmpty)
    #expect(
        fixture.pointer.moves.map(\.point)
            == [CGPoint(x: 60, y: 65), CGPoint(x: 12, y: 34)]
    )
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func preCancelledTaskDoesNotActivateMoveOrClick() async {
    let fixture = makeForegroundFixture()

    let outcome = await runCancellableForegroundAction(
        fixture: fixture,
        cancelBeforeStart: true
    )

    expectCancellation(outcome)
    #expect(fixture.applications.activationRequests.isEmpty)
    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
}

@Test
func cancellationDuringActivationPreventsPointerAndClickAndRestoresFocus() async {
    let fixture = makeForegroundFixture()

    let outcome = await runCancellableForegroundAction(
        fixture: fixture
    ) { trigger in
        fixture.applications.activationHook = { application in
            if application == fixture.game {
                trigger.cancel()
            }
        }
    }

    expectCancellation(outcome)
    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func cancellationDuringFailedActivationTakesPrecedenceAndStillCleansUp() async {
    let fixture = makeForegroundFixture()
    fixture.applications.activationBehaviors[fixture.game] =
        .returnFalse

    let outcome = await runCancellableForegroundAction(
        fixture: fixture
    ) { trigger in
        fixture.applications.activationHook = { application in
            if application == fixture.game {
                trigger.cancel()
            }
        }
    }

    expectCancellation(outcome)
    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func cancellationDuringFirstSnapshotPreventsPointerAndClickAndRestoresFocus() async {
    let fixture = makeForegroundFixture()

    let outcome = await runCancellableForegroundAction(
        fixture: fixture
    ) { trigger in
        fixture.monitor.snapshotHook = { snapshotNumber in
            if snapshotNumber == 1 {
                trigger.cancel()
            }
        }
    }

    expectCancellation(outcome)
    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func cancellationDuringFinalSnapshotPreventsClickAndRestoresEverything() async {
    let fixture = makeForegroundFixture()

    let outcome = await runCancellableForegroundAction(
        fixture: fixture
    ) { trigger in
        fixture.monitor.snapshotHook = { snapshotNumber in
            if snapshotNumber == 2 {
                trigger.cancel()
            }
        }
    }

    expectCancellation(outcome)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(
        fixture.pointer.moves.map(\.point)
            == [CGPoint(x: 60, y: 65), CGPoint(x: 12, y: 34)]
    )
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func cancellationReturnedFromWaitStillCleansUpWhenSleeperDoesNotThrow() async {
    let fixture = makeForegroundFixture()

    let outcome = await runCancellableForegroundAction(
        fixture: fixture
    ) { trigger in
        fixture.sleeper.sleepHook = {
            trigger.cancel()
        }
    }

    expectCancellation(
        outcome,
        expected: .cancelledAfterClick
    )
    #expect(fixture.clicker.clicks.count == 1)
    #expect(fixture.pointer.moves.last?.point == CGPoint(x: 12, y: 34))
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func focusChangedAfterFinalSnapshotAbortsBeforeGlobalClick() async {
    let fixture = makeForegroundFixture()
    let intruder = ApplicationIdentity(
        processIdentifier: 30,
        bundleIdentifier: "com.example.intruder"
    )
    fixture.applications.running.insert(intruder)
    fixture.monitor.snapshotHook = { snapshotNumber in
        if snapshotNumber == 2 {
            fixture.applications.setFrontmost(intruder)
        }
    }

    await expectCoordinatorError(
        primary: .targetNotFrontmost,
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.clicker.clicks.isEmpty)
    #expect(
        fixture.pointer.moves.map(\.point)
            == [CGPoint(x: 60, y: 65), CGPoint(x: 12, y: 34)]
    )
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func activationFailureRestoresFocusEvenWhenActivationChangedItFirst() async {
    let fixture = makeForegroundFixture()
    fixture.applications.activationBehaviors[fixture.game] =
        .throwAfterActivation(.activation)

    await expectCoordinatorError(
        primary: .targetActivationFailed("activation"),
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.clicker.clicks.isEmpty)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
    #expect(
        fixture.log.entries.suffix(3) == [
            "applications.isRunning:10",
            "applications.activate:10",
            "applications.isFrontmost:10",
        ]
    )
}

@Test
func targetMustBeFrontmostBeforePointerMovementOrClick() async {
    let fixture = makeForegroundFixture()
    fixture.applications.frontmostAfterSuccessfulActivation = false

    await expectCoordinatorError(
        primary: .targetNotFrontmost,
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.pointer.moves.isEmpty)
    #expect(fixture.clicker.clicks.isEmpty)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func clickFailureStillRestoresPointerAndOriginalApplication() async throws {
    let fixture = makeForegroundFixture()
    fixture.clicker.error = ForegroundTestAdapterError.click

    await expectCoordinatorError(
        primary: .clickFailed("click"),
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(
        fixture.pointer.moves.map(\.point)
            == [CGPoint(x: 60, y: 65), CGPoint(x: 12, y: 34)]
    )
    let restorePointerIndex = fixture.log.entries.firstIndex(
        of: "pointer.move:12.0,34.0:\(AutomatorSyntheticEvent.sourceIdentifier)"
    )
    let restoreAppIndex = fixture.log.entries.firstIndex(
        of: "applications.activate:10"
    )
    let pointerIndex = try #require(restorePointerIndex)
    let appIndex = try #require(restoreAppIndex)
    #expect(pointerIndex < appIndex)
}

@Test
func missingOriginalApplicationRestoresPointerWithoutActivatingAnotherApp() async {
    let fixture = makeForegroundFixture()
    fixture.applications.running.remove(fixture.original)

    await expectCoordinatorError(
        primary: nil,
        restorationFailures: [
            .originalApplicationUnavailable(fixture.original),
        ]
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.pointer.moves.last?.point == CGPoint(x: 12, y: 34))
    #expect(
        !fixture.log.entries.contains("applications.activate:10")
    )
    #expect(
        fixture.applications.activationRequests == [fixture.game]
    )
}

@Test
func alreadyFrontmostGameRestoresOnlyPointerAndDoesNotReactivateGame() async throws {
    let game = ApplicationIdentity(
        processIdentifier: 20,
        bundleIdentifier: "com.example.game"
    )
    let log = ForegroundActionTestLog()
    let applications = FakeApplicationCoordinator(
        frontmost: game,
        running: [game],
        log: log
    )
    let pointer = FakePointerController(
        location: CGPoint(x: 12, y: 34),
        log: log
    )
    let clicker = FakeGlobalClicker(log: log)
    let coordinator = ForegroundActionCoordinator(
        applications: applications,
        pointer: pointer,
        clicker: clicker,
        sleeper: FakeActionSleeper(log: log),
        inputMonitor: FakeForegroundInputMonitor(
            snapshots: [inputSnapshot(generation: 3)],
            log: log
        )
    )

    let result = try await coordinator.perform(
        targetApplication: game,
        targetBox: CGRect(x: 10, y: 20, width: 30, height: 40),
        expectedInputGeneration: 3
    )

    #expect(result.restoration == .gameWasAlreadyFrontmost)
    #expect(applications.activationRequests.isEmpty)
    #expect(
        pointer.moves.map(\.point)
            == [CGPoint(x: 25, y: 40), CGPoint(x: 12, y: 34)]
    )
    #expect(clicker.clicks.count == 1)
}

@Test
func cancellationDuringPostActionWaitStillRestoresPointerAndFocus() async {
    let fixture = makeForegroundFixture()
    fixture.sleeper.error = CancellationError()

    await expectCoordinatorError(
        primary: .cancelledAfterClick,
        restorationFailures: []
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.clicker.clicks.count == 1)
    #expect(fixture.pointer.moves.last?.point == CGPoint(x: 12, y: 34))
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func postClickCancellationPreservesRestorationFailures() async {
    let fixture = makeForegroundFixture()
    fixture.sleeper.error = CancellationError()
    fixture.pointer.failOnMoveNumber = 2

    await expectCoordinatorError(
        primary: .cancelledAfterClick,
        restorationFailures: [.pointerRestoreFailed("pointer")]
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(fixture.clicker.clicks.count == 1)
    #expect(fixture.applications.frontmostIdentity == fixture.original)
}

@Test
func cleanupFailuresAreAggregatedWithoutHidingPrimaryClickFailure() async {
    let fixture = makeForegroundFixture()
    fixture.clicker.error = ForegroundTestAdapterError.click
    fixture.pointer.failOnMoveNumber = 2
    fixture.applications.activationBehaviors[fixture.original] =
        .returnFalse

    await expectCoordinatorError(
        primary: .clickFailed("click"),
        restorationFailures: [
            .pointerRestoreFailed("pointer"),
            .originalApplicationActivationFailed("returned false"),
        ]
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }

    #expect(
        fixture.log.entries.contains("applications.activate:10")
    )
}

@Test
func thrownAppRestorationFailureIsRecordedWithoutLosingPrimaryFailure() async {
    let fixture = makeForegroundFixture()
    fixture.clicker.error = ForegroundTestAdapterError.click
    fixture.applications.activationBehaviors[fixture.original] =
        .throwWithoutActivation(.activation)

    await expectCoordinatorError(
        primary: .clickFailed("click"),
        restorationFailures: [
            .originalApplicationActivationFailed("activation"),
        ]
    ) {
        _ = try await fixture.coordinator.perform(
            targetApplication: fixture.game,
            targetBox: CGRect(x: 50, y: 60, width: 20, height: 10),
            expectedInputGeneration: 11
        )
    }
}

private struct ForegroundFixture {
    let original: ApplicationIdentity
    let game: ApplicationIdentity
    let log: ForegroundActionTestLog
    let applications: FakeApplicationCoordinator
    let pointer: FakePointerController
    let clicker: FakeGlobalClicker
    let sleeper: FakeActionSleeper
    let monitor: FakeForegroundInputMonitor
    let coordinator: ForegroundActionCoordinator
}

private func makeForegroundFixture(
    initialGeneration: UInt64 = 11,
    observedGeneration: UInt64? = nil,
    observedGenerations: [UInt64]? = nil
) -> ForegroundFixture {
    let original = ApplicationIdentity(
        processIdentifier: 10,
        bundleIdentifier: "com.example.editor"
    )
    let game = ApplicationIdentity(
        processIdentifier: 20,
        bundleIdentifier: "com.example.game"
    )
    let log = ForegroundActionTestLog()
    let applications = FakeApplicationCoordinator(
        frontmost: original,
        running: [original, game],
        log: log
    )
    let pointer = FakePointerController(
        location: CGPoint(x: 12, y: 34),
        log: log
    )
    let clicker = FakeGlobalClicker(log: log)
    let sleeper = FakeActionSleeper(log: log)
    let monitor = FakeForegroundInputMonitor(
        snapshots: (
            observedGenerations
                ?? [observedGeneration ?? initialGeneration]
        ).map(inputSnapshot(generation:)),
        log: log
    )
    return ForegroundFixture(
        original: original,
        game: game,
        log: log,
        applications: applications,
        pointer: pointer,
        clicker: clicker,
        sleeper: sleeper,
        monitor: monitor,
        coordinator: ForegroundActionCoordinator(
            applications: applications,
            pointer: pointer,
            clicker: clicker,
            sleeper: sleeper,
            inputMonitor: monitor
        )
    )
}

private enum CancellableActionOutcome: Sendable {
    case succeeded
    case coordinatorError(ForegroundActionCoordinatorError)
    case unexpectedError(String)
}

private func runCancellableForegroundAction(
    fixture: ForegroundFixture,
    cancelBeforeStart: Bool = false,
    configure: (CancellationTrigger) -> Void = { _ in }
) async -> CancellableActionOutcome {
    let trigger = CancellationTrigger()
    let gate = CancellableTestStartGate()
    configure(trigger)

    let task = Task {
        await gate.wait()
        do {
            _ = try await fixture.coordinator.perform(
                targetApplication: fixture.game,
                targetBox: CGRect(
                    x: 50,
                    y: 60,
                    width: 20,
                    height: 10
                ),
                expectedInputGeneration: 11
            )
            return CancellableActionOutcome.succeeded
        } catch let error as ForegroundActionCoordinatorError {
            return .coordinatorError(error)
        } catch {
            return .unexpectedError(String(describing: error))
        }
    }

    trigger.install {
        task.cancel()
    }
    if cancelBeforeStart {
        trigger.cancel()
    }
    await gate.release()
    return await task.value
}

private func expectCancellation(
    _ outcome: CancellableActionOutcome,
    expected: ForegroundActionFailure = .cancelled
) {
    switch outcome {
    case let .coordinatorError(error):
        #expect(
            error.primaryFailure == expected
        )
        #expect(error.restorationFailures.isEmpty)
    case .succeeded:
        Issue.record("Expected cancellation, but action succeeded.")
    case let .unexpectedError(error):
        Issue.record("Unexpected error: \(error)")
    }
}

private final class CancellationTrigger: @unchecked Sendable {
    private let lock = NSLock()
    private var cancellation: (@Sendable () -> Void)?

    func install(_ cancellation: @escaping @Sendable () -> Void) {
        lock.withLock {
            self.cancellation = cancellation
        }
    }

    func cancel() {
        let action: (@Sendable () -> Void)? = lock.withLock {
            self.cancellation
        }
        action?()
    }
}

private actor CancellableTestStartGate {
    private var isReleased = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        guard !isReleased else {
            return
        }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    func release() {
        isReleased = true
        let currentWaiters = waiters
        waiters.removeAll()
        for waiter in currentWaiters {
            waiter.resume()
        }
    }
}

private func expectCoordinatorError(
    primary: ForegroundActionFailure?,
    restorationFailures: [ForegroundRestorationFailure],
    operation: () async throws -> Void
) async {
    do {
        try await operation()
        Issue.record("Expected ForegroundActionCoordinatorError.")
    } catch let error as ForegroundActionCoordinatorError {
        #expect(error.primaryFailure == primary)
        #expect(error.restorationFailures == restorationFailures)
    } catch {
        Issue.record("Unexpected error: \(error)")
    }
}

private func inputSnapshot(generation: UInt64) -> UserInputSnapshot {
    UserInputSnapshot(
        generation: generation,
        lastInputAt: ContinuousClock().now
    )
}

private enum ForegroundTestAdapterError: Error {
    case activation
    case pointer
    case click
}

private final class ForegroundActionTestLog: @unchecked Sendable {
    private let lock = NSLock()
    private var storedEntries: [String] = []

    var entries: [String] {
        lock.withLock { storedEntries }
    }

    func append(_ entry: String) {
        lock.withLock {
            storedEntries.append(entry)
        }
    }
}

private enum FakeActivationBehavior {
    case succeed
    case returnFalse
    case throwAfterActivation(ForegroundTestAdapterError)
    case throwWithoutActivation(ForegroundTestAdapterError)
}

private final class FakeApplicationCoordinator:
    ApplicationCoordinating,
    @unchecked Sendable
{
    private let lock = NSLock()
    private let log: ForegroundActionTestLog
    private var storedFrontmost: ApplicationIdentity?
    private var storedRunning: Set<ApplicationIdentity>
    private var storedActivationBehaviors:
        [ApplicationIdentity: FakeActivationBehavior] = [:]
    private var storedActivationRequests: [ApplicationIdentity] = []
    var frontmostAfterSuccessfulActivation = true
    var activationHook: (@Sendable (ApplicationIdentity) -> Void)?

    init(
        frontmost: ApplicationIdentity?,
        running: Set<ApplicationIdentity>,
        log: ForegroundActionTestLog
    ) {
        storedFrontmost = frontmost
        storedRunning = running
        self.log = log
    }

    var frontmostIdentity: ApplicationIdentity? {
        lock.withLock { storedFrontmost }
    }

    var running: Set<ApplicationIdentity> {
        get { lock.withLock { storedRunning } }
        set { lock.withLock { storedRunning = newValue } }
    }

    var activationBehaviors: [ApplicationIdentity: FakeActivationBehavior] {
        get { lock.withLock { storedActivationBehaviors } }
        set { lock.withLock { storedActivationBehaviors = newValue } }
    }

    var activationRequests: [ApplicationIdentity] {
        lock.withLock { storedActivationRequests }
    }

    func frontmostApplication() -> ApplicationIdentity? {
        log.append("applications.frontmost")
        return lock.withLock { storedFrontmost }
    }

    func activate(_ application: ApplicationIdentity) throws -> Bool {
        log.append("applications.activate:\(application.processIdentifier)")
        let result = try lock.withLock {
            storedActivationRequests.append(application)
            let behavior = storedActivationBehaviors[application] ?? .succeed
            switch behavior {
            case .succeed:
                if frontmostAfterSuccessfulActivation {
                    storedFrontmost = application
                }
                return true
            case .returnFalse:
                return false
            case let .throwAfterActivation(error):
                storedFrontmost = application
                throw error
            case let .throwWithoutActivation(error):
                throw error
            }
        }
        activationHook?(application)
        return result
    }

    func isFrontmost(_ application: ApplicationIdentity) -> Bool {
        log.append("applications.isFrontmost:\(application.processIdentifier)")
        return lock.withLock { storedFrontmost == application }
    }

    func isRunning(_ application: ApplicationIdentity) -> Bool {
        log.append("applications.isRunning:\(application.processIdentifier)")
        return lock.withLock { storedRunning.contains(application) }
    }

    func setFrontmost(_ application: ApplicationIdentity?) {
        lock.withLock {
            storedFrontmost = application
        }
    }
}

private final class FakePointerController:
    PointerControlling,
    @unchecked Sendable
{
    struct Move: Equatable {
        let point: CGPoint
        let sourceIdentifier: Int64
    }

    private let lock = NSLock()
    private let initialLocation: CGPoint
    private let log: ForegroundActionTestLog
    private var storedMoves: [Move] = []
    var failOnMoveNumber: Int?

    init(location: CGPoint, log: ForegroundActionTestLog) {
        initialLocation = location
        self.log = log
    }

    var moves: [Move] {
        lock.withLock { storedMoves }
    }

    func location() throws -> CGPoint {
        log.append("pointer.location")
        return initialLocation
    }

    func move(
        to point: CGPoint,
        sourceIdentifier: Int64
    ) throws {
        log.append(
            "pointer.move:\(point.x),\(point.y):\(sourceIdentifier)"
        )
        try lock.withLock {
            storedMoves.append(
                Move(
                    point: point,
                    sourceIdentifier: sourceIdentifier
                )
            )
            if storedMoves.count == failOnMoveNumber {
                throw ForegroundTestAdapterError.pointer
            }
        }
    }
}

private final class FakeGlobalClicker:
    GlobalClicking,
    @unchecked Sendable
{
    struct Click: Equatable {
        let point: CGPoint
        let sourceIdentifier: Int64
    }

    private let lock = NSLock()
    private let log: ForegroundActionTestLog
    private var storedClicks: [Click] = []
    var error: (any Error)?

    init(log: ForegroundActionTestLog) {
        self.log = log
    }

    var clicks: [Click] {
        lock.withLock { storedClicks }
    }

    func click(
        screenPoint: CGPoint,
        sourceIdentifier: Int64
    ) throws {
        log.append(
            "click:\(screenPoint.x),\(screenPoint.y):\(sourceIdentifier)"
        )
        try lock.withLock {
            storedClicks.append(
                Click(
                    point: screenPoint,
                    sourceIdentifier: sourceIdentifier
                )
            )
            if let error {
                throw error
            }
        }
    }
}

private final class FakeActionSleeper:
    ActionSleeping,
    @unchecked Sendable
{
    private let log: ForegroundActionTestLog
    var error: (any Error)?
    var sleepHook: (@Sendable () -> Void)?

    init(log: ForegroundActionTestLog) {
        self.log = log
    }

    func sleep(for duration: Duration) async throws {
        log.append("sleep:\(duration)")
        sleepHook?()
        if let error {
            throw error
        }
    }
}

private final class FakeForegroundInputMonitor:
    UserIdleMonitoring,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var snapshots: [UserInputSnapshot]
    private var snapshotCount = 0
    private let log: ForegroundActionTestLog
    var snapshotHook: (@Sendable (Int) -> Void)?

    init(
        snapshots: [UserInputSnapshot],
        log: ForegroundActionTestLog
    ) {
        self.snapshots = snapshots
        self.log = log
    }

    func snapshot() async -> UserInputSnapshot {
        log.append("input.snapshot")
        let result = lock.withLock {
            snapshotCount += 1
            if snapshots.count == 1 {
                return (snapshots[0], snapshotCount)
            }
            return (snapshots.removeFirst(), snapshotCount)
        }
        snapshotHook?(result.1)
        return result.0
    }

    func waitUntilIdle(
        for duration: Duration
    ) async throws -> UserInputSnapshot {
        _ = duration
        return await snapshot()
    }
}

private func makeForegroundTestClickEvents(
    at point: CGPoint
) -> ClickEvents? {
    guard
        let down = CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDown,
            mouseCursorPosition: point,
            mouseButton: .left
        ),
        let up = CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseUp,
            mouseCursorPosition: point,
            mouseButton: .left
        )
    else {
        return nil
    }
    return ClickEvents(down: down, up: up)
}

private final class RecordingGlobalClickEventFactory:
    GlobalClickEventCreating,
    @unchecked Sendable
{
    private let events: ClickEvents?
    private let lock = NSLock()
    private var storedRequestedPoints: [CGPoint] = []

    init(events: ClickEvents?) {
        self.events = events
    }

    var requestedPoints: [CGPoint] {
        lock.withLock { storedRequestedPoints }
    }

    func makeEvents(at screenPoint: CGPoint) -> ClickEvents? {
        lock.withLock {
            storedRequestedPoints.append(screenPoint)
        }
        return events
    }
}

private final class RecordingPointerMoveEventFactory:
    PointerMoveEventCreating,
    @unchecked Sendable
{
    private let event: CGEvent?
    private let lock = NSLock()
    private var storedRequestedPoints: [CGPoint] = []

    init(event: CGEvent?) {
        self.event = event
    }

    var requestedPoints: [CGPoint] {
        lock.withLock { storedRequestedPoints }
    }

    func makeMoveEvent(at screenPoint: CGPoint) -> CGEvent? {
        lock.withLock {
            storedRequestedPoints.append(screenPoint)
        }
        return event
    }
}

private final class RecordingGlobalEventPoster:
    GlobalEventPosting,
    @unchecked Sendable
{
    struct Record: Equatable {
        let eventType: CGEventType
        let sourceIdentifier: Int64
    }

    private let lock = NSLock()
    private var storedRecords: [Record] = []

    var records: [Record] {
        lock.withLock { storedRecords }
    }

    func post(_ event: CGEvent) {
        lock.withLock {
            storedRecords.append(
                Record(
                    eventType: event.type,
                    sourceIdentifier: event.getIntegerValueField(
                        .eventSourceUserData
                    )
                )
            )
        }
    }
}
