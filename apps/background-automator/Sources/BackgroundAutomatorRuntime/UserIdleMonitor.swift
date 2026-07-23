@preconcurrency import CoreGraphics
import Foundation

public enum AutomatorSyntheticEvent {
    public static let sourceIdentifier: Int64 = 0x4241_5554_4F4D
}

public struct UserInputSnapshot: Equatable, Sendable {
    public let generation: UInt64
    public let lastInputAt: ContinuousClock.Instant

    public init(
        generation: UInt64,
        lastInputAt: ContinuousClock.Instant
    ) {
        self.generation = generation
        self.lastInputAt = lastInputAt
    }
}

public protocol UserIdleMonitoring: Sendable {
    func snapshot() async -> UserInputSnapshot
    func waitUntilIdle(
        for duration: Duration
    ) async throws -> UserInputSnapshot
}

public enum UserIdleMonitorError: Error, Equatable, Sendable {
    case invalidIdleDuration
    case notMonitoring
    case cannotCreateEventTap
    case cannotCreateRunLoopSource
    case cannotAccessRunLoop
    case cannotEnableEventTap
}

struct UserInputState {
    private(set) var generation: UInt64
    private(set) var lastInputAt: ContinuousClock.Instant

    var snapshot: UserInputSnapshot {
        UserInputSnapshot(
            generation: generation,
            lastInputAt: lastInputAt
        )
    }

    mutating func recordInput(
        at timestamp: ContinuousClock.Instant,
        sourceIdentifier: Int64?
    ) {
        guard
            sourceIdentifier
                != AutomatorSyntheticEvent.sourceIdentifier
        else {
            return
        }

        generation &+= 1
        if timestamp > lastInputAt {
            lastInputAt = timestamp
        }
    }

    mutating func recordMonitoringStart(
        at timestamp: ContinuousClock.Instant
    ) {
        recordInput(
            at: timestamp,
            sourceIdentifier: nil
        )
    }

    func isIdle(
        at timestamp: ContinuousClock.Instant,
        for duration: Duration
    ) -> Bool {
        guard duration >= .zero else {
            return false
        }
        return timeUntilIdle(
            at: timestamp,
            for: duration
        ) == nil
    }

    func timeUntilIdle(
        at timestamp: ContinuousClock.Instant,
        for duration: Duration
    ) -> Duration? {
        guard duration >= .zero else {
            return nil
        }
        if timestamp < lastInputAt {
            return timestamp.duration(to: lastInputAt)
                + duration
        }

        let elapsed = lastInputAt.duration(to: timestamp)
        return elapsed >= duration
            ? nil
            : duration - elapsed
    }
}

protocol InputEventTapping: Sendable {
    var isRunning: Bool { get }

    func start() throws -> Bool
    func stop()
}

public final class UserIdleMonitor: UserIdleMonitoring {
    private let clock: ContinuousClock
    private let now: @Sendable () -> ContinuousClock.Instant
    private let stateStore: UserInputStateStore
    private let eventTap: any InputEventTapping

    public convenience init() {
        let clock = ContinuousClock()
        let stateStore = UserInputStateStore(
            state: UserInputState(
                generation: 0,
                lastInputAt: clock.now
            )
        )
        let eventTap = PassiveInputEventTap(
            observe: { sourceIdentifier in
                stateStore.recordInput(
                    at: clock.now,
                    sourceIdentifier: sourceIdentifier
                )
            }
        )
        self.init(
            clock: clock,
            now: { clock.now },
            stateStore: stateStore,
            eventTap: eventTap
        )
    }

    init(
        initialGeneration: UInt64,
        lastInputAt: ContinuousClock.Instant,
        now: @escaping @Sendable () -> ContinuousClock.Instant = {
            ContinuousClock().now
        },
        eventTap: any InputEventTapping
    ) {
        self.clock = ContinuousClock()
        self.now = now
        self.stateStore = UserInputStateStore(
            state: UserInputState(
                generation: initialGeneration,
                lastInputAt: lastInputAt
            )
        )
        self.eventTap = eventTap
    }

    private init(
        clock: ContinuousClock,
        now: @escaping @Sendable () -> ContinuousClock.Instant,
        stateStore: UserInputStateStore,
        eventTap: any InputEventTapping
    ) {
        self.clock = clock
        self.now = now
        self.stateStore = stateStore
        self.eventTap = eventTap
    }

    public var isMonitoring: Bool {
        eventTap.isRunning
    }

    public func start() throws {
        guard try eventTap.start() else {
            return
        }

        stateStore.recordMonitoringStart(at: now())
    }

    public func stop() {
        eventTap.stop()
    }

    public func snapshot() async -> UserInputSnapshot {
        stateStore.snapshot()
    }

    public func waitUntilIdle(
        for duration: Duration
    ) async throws -> UserInputSnapshot {
        guard duration >= .zero else {
            throw UserIdleMonitorError.invalidIdleDuration
        }
        guard isMonitoring else {
            throw UserIdleMonitorError.notMonitoring
        }

        while true {
            try Task.checkCancellation()
            guard isMonitoring else {
                throw UserIdleMonitorError.notMonitoring
            }

            let check = stateStore.idleCheck(
                at: now(),
                duration: duration
            )
            if check.isIdle {
                return check.snapshot
            }

            try await clock.sleep(for: check.remainingDuration)
        }
    }

    deinit {
        eventTap.stop()
    }
}

// The lock is the sole access path to mutable state.
private final class UserInputStateStore: @unchecked Sendable {
    private let lock = NSLock()
    private var state: UserInputState

    init(state: UserInputState) {
        self.state = state
    }

    func snapshot() -> UserInputSnapshot {
        lock.withLock { state.snapshot }
    }

    func recordInput(
        at timestamp: ContinuousClock.Instant,
        sourceIdentifier: Int64?
    ) {
        lock.withLock {
            state.recordInput(
                at: timestamp,
                sourceIdentifier: sourceIdentifier
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

    func idleCheck(
        at timestamp: ContinuousClock.Instant,
        duration: Duration
    ) -> IdleCheck {
        lock.withLock {
            let snapshot = state.snapshot
            guard
                !state.isIdle(at: timestamp, for: duration)
            else {
                return IdleCheck(
                    snapshot: snapshot,
                    isIdle: true,
                    remainingDuration: .zero
                )
            }

            return IdleCheck(
                snapshot: snapshot,
                isIdle: false,
                remainingDuration: state.timeUntilIdle(
                    at: timestamp,
                    for: duration
                ) ?? .zero
            )
        }
    }
}

private struct IdleCheck {
    let snapshot: UserInputSnapshot
    let isIdle: Bool
    let remainingDuration: Duration
}

final class InputEventTapContext: Sendable {
    private let observe: @Sendable (Int64) -> Void
    private let reenable: @Sendable () -> Void

    init(
        observe: @escaping @Sendable (Int64) -> Void,
        reenable: @escaping @Sendable () -> Void
    ) {
        self.observe = observe
        self.reenable = reenable
    }

    func handle(
        type: CGEventType,
        event: CGEvent
    ) -> CGEvent {
        if type == .tapDisabledByTimeout
            || type == .tapDisabledByUserInput
        {
            reenable()
            return event
        }

        guard Self.isObservedInput(type) else {
            return event
        }

        let sourceIdentifier = event.getIntegerValueField(
            .eventSourceUserData
        )
        if sourceIdentifier
            != AutomatorSyntheticEvent.sourceIdentifier
        {
            observe(sourceIdentifier)
        }
        return event
    }

    private static func isObservedInput(
        _ type: CGEventType
    ) -> Bool {
        switch type {
        case
            .keyDown,
            .keyUp,
            .flagsChanged,
            .leftMouseDown,
            .leftMouseUp,
            .rightMouseDown,
            .rightMouseUp,
            .otherMouseDown,
            .otherMouseUp,
            .mouseMoved,
            .leftMouseDragged,
            .rightMouseDragged,
            .otherMouseDragged,
            .scrollWheel:
            true
        default:
            false
        }
    }
}

protocol EventTapLifecycleDriving: Sendable {
    var isValid: Bool { get }
    var isEnabled: Bool { get }

    func start(context: InputEventTapContext) throws
    func reenable() -> Bool
    func stop()
}

// The controller serializes start, stop, and callback recovery so a failed
// re-enable cannot be mistaken for a live monitor.
private final class EventTapLifecycleController:
    @unchecked Sendable
{
    private let lock = NSLock()
    private let driver: any EventTapLifecycleDriving
    private var recoveryFailed = false

    init(driver: any EventTapLifecycleDriving) {
        self.driver = driver
    }

    var isRunning: Bool {
        lock.withLock { isHealthy }
    }

    func start(
        context: InputEventTapContext
    ) throws -> Bool {
        try lock.withLock {
            if isHealthy {
                return false
            }

            driver.stop()
            recoveryFailed = false
            do {
                try driver.start(context: context)
            } catch {
                recoveryFailed = true
                throw error
            }

            guard isHealthy else {
                driver.stop()
                recoveryFailed = true
                throw UserIdleMonitorError.cannotEnableEventTap
            }
            return true
        }
    }

    func reenable() {
        lock.withLock {
            guard driver.isValid else {
                recoveryFailed = true
                return
            }

            let recovered = driver.reenable()
            if !recovered
                || !driver.isValid
                || !driver.isEnabled
            {
                recoveryFailed = true
            }
        }
    }

    func stop() {
        lock.withLock {
            driver.stop()
            recoveryFailed = false
        }
    }

    private var isHealthy: Bool {
        !recoveryFailed
            && driver.isValid
            && driver.isEnabled
    }
}

final class PassiveInputEventTap: InputEventTapping {
    private let lifecycle: EventTapLifecycleController
    let context: InputEventTapContext

    convenience init(
        observe: @escaping @Sendable (Int64) -> Void
    ) {
        self.init(
            observe: observe,
            driver: CoreGraphicsEventTapDriver()
        )
    }

    init(
        observe: @escaping @Sendable (Int64) -> Void,
        driver: any EventTapLifecycleDriving
    ) {
        let lifecycle = EventTapLifecycleController(
            driver: driver
        )
        self.lifecycle = lifecycle
        self.context = InputEventTapContext(
            observe: observe,
            reenable: {
                lifecycle.reenable()
            }
        )
    }

    var isRunning: Bool {
        lifecycle.isRunning
    }

    func start() throws -> Bool {
        try lifecycle.start(context: context)
    }

    func stop() {
        lifecycle.stop()
    }

    deinit {
        lifecycle.stop()
    }
}

// Core Foundation handles are not Sendable. Every handle and its explicit
// callback-context retain are confined behind this driver's lock.
private final class CoreGraphicsEventTapDriver:
    EventTapLifecycleDriving,
    @unchecked Sendable
{
    private struct Resources {
        let port: CFMachPort
        let source: CFRunLoopSource
        let runLoop: CFRunLoop
        let contextPointer: UnsafeMutableRawPointer
    }

    private let lock = NSLock()
    private var resources: Resources?

    var isValid: Bool {
        lock.withLock {
            guard let resources else {
                return false
            }
            return CFMachPortIsValid(resources.port)
        }
    }

    var isEnabled: Bool {
        lock.withLock {
            guard let resources else {
                return false
            }
            return CGEvent.tapIsEnabled(
                tap: resources.port
            )
        }
    }

    func start(context: InputEventTapContext) throws {
        try lock.withLock {
            guard resources == nil else {
                throw UserIdleMonitorError.cannotCreateEventTap
            }

            // Core Graphics does not retain userInfo. Keep one explicit
            // retain until the source is removed and the port invalidated.
            let retainedContext = Unmanaged
                .passRetained(context)
            let contextPointer = retainedContext.toOpaque()
            guard
                let port = CGEvent.tapCreate(
                    tap: .cgSessionEventTap,
                    place: .headInsertEventTap,
                    options: .listenOnly,
                    eventsOfInterest: observedInputEventMask,
                    callback: passiveInputEventTapCallback,
                    userInfo: contextPointer
                )
            else {
                retainedContext.release()
                throw UserIdleMonitorError
                    .cannotCreateEventTap
            }
            guard
                let source = CFMachPortCreateRunLoopSource(
                    kCFAllocatorDefault,
                    port,
                    0
                )
            else {
                CFMachPortInvalidate(port)
                retainedContext.release()
                throw UserIdleMonitorError
                    .cannotCreateRunLoopSource
            }

            guard let runLoop = CFRunLoopGetMain() else {
                CFMachPortInvalidate(port)
                retainedContext.release()
                throw UserIdleMonitorError.cannotAccessRunLoop
            }
            CFRunLoopAddSource(
                runLoop,
                source,
                .commonModes
            )
            CGEvent.tapEnable(tap: port, enable: true)
            guard CGEvent.tapIsEnabled(tap: port) else {
                CFRunLoopRemoveSource(
                    runLoop,
                    source,
                    .commonModes
                )
                CFMachPortInvalidate(port)
                retainedContext.release()
                throw UserIdleMonitorError.cannotEnableEventTap
            }
            resources = Resources(
                port: port,
                source: source,
                runLoop: runLoop,
                contextPointer: contextPointer
            )
        }
    }

    func reenable() -> Bool {
        lock.withLock {
            guard
                let resources,
                CFMachPortIsValid(resources.port)
            else {
                return false
            }
            CGEvent.tapEnable(
                tap: resources.port,
                enable: true
            )
            return CFMachPortIsValid(resources.port)
                && CGEvent.tapIsEnabled(
                    tap: resources.port
                )
        }
    }

    func stop() {
        lock.withLock {
            guard let resources else {
                return
            }
            CFRunLoopRemoveSource(
                resources.runLoop,
                resources.source,
                .commonModes
            )
            CFMachPortInvalidate(resources.port)
            Unmanaged<InputEventTapContext>
                .fromOpaque(resources.contextPointer)
                .release()
            self.resources = nil
        }
    }
}

private let observedInputEventMask = [
    CGEventType.keyDown,
    .keyUp,
    .flagsChanged,
    .leftMouseDown,
    .leftMouseUp,
    .rightMouseDown,
    .rightMouseUp,
    .otherMouseDown,
    .otherMouseUp,
    .mouseMoved,
    .leftMouseDragged,
    .rightMouseDragged,
    .otherMouseDragged,
    .scrollWheel,
].reduce(CGEventMask(0)) { mask, type in
    mask | (CGEventMask(1) << type.rawValue)
}

private let passiveInputEventTapCallback: CGEventTapCallBack = {
    _,
    type,
    event,
    userInfo in
    guard let userInfo else {
        return Unmanaged.passUnretained(event)
    }

    let context = Unmanaged<InputEventTapContext>
        .fromOpaque(userInfo)
        .takeUnretainedValue()
    let returnedEvent = context.handle(
        type: type,
        event: event
    )
    return Unmanaged.passUnretained(returnedEvent)
}
