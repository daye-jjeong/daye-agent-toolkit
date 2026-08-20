@preconcurrency import CoreGraphics
import Darwin
import Foundation

public enum CoordinateError: Error, Equatable, Sendable {
    case outOfRange
}

public enum CoordinateConverter {
    public static func screenPoint(
        normalizedX: Double,
        normalizedY: Double,
        windowFrame: CGRect
    ) throws -> CGPoint {
        guard
            (0...1).contains(normalizedX),
            (0...1).contains(normalizedY)
        else {
            throw CoordinateError.outOfRange
        }

        let x = normalizedX == 1
            ? windowFrame.maxX.nextDown
            : windowFrame.minX + normalizedX * windowFrame.width
        let y = normalizedY == 1
            ? windowFrame.maxY.nextDown
            : windowFrame.minY + normalizedY * windowFrame.height
        return CGPoint(x: x, y: y)
    }
}

public enum ClickError: Error, Equatable, Sendable {
    case cannotCreateEvent
}

extension ClickError: LocalizedError {
    public var errorDescription: String? {
        "Could not create the mouse events."
    }
}

public protocol Clicking: Sendable {
    func click(processID: pid_t, screenPoint: CGPoint) throws
}

public protocol GlobalClicking: Sendable {
    /// `hold`는 버튼을 누르고 있는 시간이다. 0이면 누름과 뗌이 같은
    /// 순간에 나가는데, 사람 손으로는 낼 수 없는 값이다.
    func click(
        screenPoint: CGPoint,
        sourceIdentifier: Int64,
        hold: Duration
    ) throws
}

struct ClickEvents {
    let down: CGEvent
    let up: CGEvent
}

protocol ClickEventCreating: Sendable {
    func makeEvents(at screenPoint: CGPoint) -> ClickEvents?
}

protocol ProcessEventPosting: Sendable {
    func post(_ event: CGEvent, to processID: pid_t)
}

protocol GlobalClickEventCreating: Sendable {
    func makeEvents(at screenPoint: CGPoint) -> ClickEvents?
}

protocol GlobalEventPosting: Sendable {
    func post(_ event: CGEvent)
}

private struct CoreGraphicsClickEventFactory: ClickEventCreating {
    func makeEvents(at screenPoint: CGPoint) -> ClickEvents? {
        guard
            let source = CGEventSource(stateID: .hidSystemState),
            let down = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseDown,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
            ),
            let up = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseUp,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
            )
        else {
            return nil
        }

        return ClickEvents(down: down, up: up)
    }
}

private struct CoreGraphicsGlobalClickEventFactory:
    GlobalClickEventCreating
{
    func makeEvents(at screenPoint: CGPoint) -> ClickEvents? {
        guard
            let source = CGEventSource(stateID: .hidSystemState),
            let down = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseDown,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
            ),
            let up = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseUp,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
            )
        else {
            return nil
        }

        return ClickEvents(down: down, up: up)
    }
}

private struct CoreGraphicsProcessEventPoster: ProcessEventPosting {
    func post(_ event: CGEvent, to processID: pid_t) {
        event.postToPid(processID)
    }
}

private struct CoreGraphicsGlobalEventPoster: GlobalEventPosting {
    func post(_ event: CGEvent) {
        event.post(tap: .cghidEventTap)
    }
}

public struct ProcessClickService: Clicking {
    private let eventFactory: any ClickEventCreating
    private let eventPoster: any ProcessEventPosting

    public init() {
        eventFactory = CoreGraphicsClickEventFactory()
        eventPoster = CoreGraphicsProcessEventPoster()
    }

    init(
        eventFactory: any ClickEventCreating,
        eventPoster: any ProcessEventPosting
    ) {
        self.eventFactory = eventFactory
        self.eventPoster = eventPoster
    }

    public func click(processID: pid_t, screenPoint: CGPoint) throws {
        guard let events = eventFactory.makeEvents(at: screenPoint) else {
            throw ClickError.cannotCreateEvent
        }

        eventPoster.post(events.down, to: processID)
        eventPoster.post(events.up, to: processID)
    }
}

public struct GlobalClickService: GlobalClicking {
    private let eventFactory: any GlobalClickEventCreating
    private let eventPoster: any GlobalEventPosting

    public init() {
        eventFactory = CoreGraphicsGlobalClickEventFactory()
        eventPoster = CoreGraphicsGlobalEventPoster()
    }

    init(
        eventFactory: any GlobalClickEventCreating,
        eventPoster: any GlobalEventPosting
    ) {
        self.eventFactory = eventFactory
        self.eventPoster = eventPoster
    }

    public func click(
        screenPoint: CGPoint,
        sourceIdentifier: Int64,
        hold: Duration
    ) throws {
        guard let events = eventFactory.makeEvents(at: screenPoint) else {
            throw ClickError.cannotCreateEvent
        }

        events.down.setIntegerValueField(
            .eventSourceUserData,
            value: sourceIdentifier
        )
        events.up.setIntegerValueField(
            .eventSourceUserData,
            value: sourceIdentifier
        )
        eventPoster.post(events.down)
        // 누른 채 기다리는 구간은 await로 끊지 않는다. 그 사이에 태스크가
        // 취소되면 버튼이 눌린 채로 남아 사용자 조작을 통째로 망가뜨린다.
        // 협동 스레드를 잠깐 막지만 클릭은 판당 6회뿐이라 무시할 수준이다.
        if hold > .zero {
            Thread.sleep(
                forTimeInterval: Double(hold.microseconds) / 1_000_000
            )
        }
        eventPoster.post(events.up)
    }
}
