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

        return CGPoint(
            x: windowFrame.minX + normalizedX * windowFrame.width,
            y: windowFrame.minY + normalizedY * windowFrame.height
        )
    }
}

public enum ClickError: Error, Equatable, Sendable {
    case cannotCreateEvent
}

extension ClickError: LocalizedError {
    public var errorDescription: String? {
        "Could not create the process-targeted mouse events."
    }
}

public protocol Clicking: Sendable {
    func click(processID: pid_t, screenPoint: CGPoint) throws
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

private struct CoreGraphicsProcessEventPoster: ProcessEventPosting {
    func post(_ event: CGEvent, to processID: pid_t) {
        event.postToPid(processID)
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
