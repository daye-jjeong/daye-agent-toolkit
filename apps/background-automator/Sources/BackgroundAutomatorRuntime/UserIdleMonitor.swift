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

        generation = generation == .max
            ? .max
            : generation + 1
        if timestamp > lastInputAt {
            lastInputAt = timestamp
        }
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

    func start() throws
    func stop()
}

public final class UserIdleMonitor: UserIdleMonitoring {
    private let clock: ContinuousClock
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
            stateStore: stateStore,
            eventTap: eventTap
        )
    }

    init(
        initialGeneration: UInt64,
        lastInputAt: ContinuousClock.Instant,
        eventTap: any InputEventTapping
    ) {
        self.clock = ContinuousClock()
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
        stateStore: UserInputStateStore,
        eventTap: any InputEventTapping
    ) {
        self.clock = clock
        self.stateStore = stateStore
        self.eventTap = eventTap
    }

    public var isMonitoring: Bool {
        eventTap.isRunning
    }

    public func start() throws {
        try eventTap.start()
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
                at: clock.now,
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

// Core Graphics delivers callbacks across threads; the lock confines the
// framework handle shared by lifecycle and callback paths.
private final class EventTapPortBox: @unchecked Sendable {
    private let lock = NSLock()
    private var port: CFMachPort?

    func set(_ port: CFMachPort?) {
        lock.withLock {
            self.port = port
        }
    }

    func reenable() {
        let currentPort = lock.withLock { port }
        if let currentPort {
            CGEvent.tapEnable(
                tap: currentPort,
                enable: true
            )
        }
    }
}

// Core Foundation handles are not Sendable, so lifecycle access is confined
// behind `lock`; callback state is separately synchronized by `portBox`.
private final class PassiveInputEventTap:
    InputEventTapping,
    @unchecked Sendable
{
    private struct Resources {
        let port: CFMachPort
        let source: CFRunLoopSource
        let runLoop: CFRunLoop
        let contextPointer: UnsafeMutableRawPointer
    }

    private let lock = NSLock()
    private let portBox: EventTapPortBox
    private let context: InputEventTapContext
    private var resources: Resources?

    init(
        observe: @escaping @Sendable (Int64) -> Void
    ) {
        let portBox = EventTapPortBox()
        self.portBox = portBox
        self.context = InputEventTapContext(
            observe: observe,
            reenable: {
                portBox.reenable()
            }
        )
    }

    var isRunning: Bool {
        lock.withLock {
            guard let resources else {
                return false
            }
            return CFMachPortIsValid(resources.port)
                && CGEvent.tapIsEnabled(
                    tap: resources.port
                )
        }
    }

    func start() throws {
        try lock.withLock {
            guard resources == nil else {
                return
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
            portBox.set(port)
            CGEvent.tapEnable(tap: port, enable: true)
            guard CGEvent.tapIsEnabled(tap: port) else {
                portBox.set(nil)
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

    func stop() {
        lock.withLock {
            guard let resources else {
                return
            }
            portBox.set(nil)
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
