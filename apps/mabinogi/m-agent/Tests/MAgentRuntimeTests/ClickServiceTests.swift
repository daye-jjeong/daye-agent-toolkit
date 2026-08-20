import CoreGraphics
import Darwin
import Foundation
import Testing

@testable import MAgentRuntime

@Test
func processClickPostsExactlyOneDownAndUpPairToTargetProcess() throws {
    let point = CGPoint(x: 700, y: 800)
    let factory = RecordingClickEventFactory(
        events: try #require(makeTestClickEvents(at: point))
    )
    let poster = RecordingProcessEventPoster()
    let service = ProcessClickService(
        eventFactory: factory,
        eventPoster: poster
    )

    try service.click(processID: 123, screenPoint: point)

    #expect(factory.requestedPoints == [point])
    #expect(poster.records.count == 2)
    #expect(poster.records.map(\.processID) == [123, 123])
    #expect(
        poster.records.map(\.eventType)
            == [.leftMouseDown, .leftMouseUp]
    )
}

@Test
func processClickThrowsWithoutPostingWhenEventsCannotBeCreated() {
    let factory = RecordingClickEventFactory(events: nil)
    let poster = RecordingProcessEventPoster()
    let service = ProcessClickService(
        eventFactory: factory,
        eventPoster: poster
    )

    #expect(throws: ClickError.cannotCreateEvent) {
        try service.click(
            processID: 123,
            screenPoint: CGPoint(x: 700, y: 800)
        )
    }
    #expect(poster.records.isEmpty)
}

private func makeTestClickEvents(at point: CGPoint) -> ClickEvents? {
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

private final class RecordingClickEventFactory:
    ClickEventCreating,
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

private final class RecordingProcessEventPoster:
    ProcessEventPosting,
    @unchecked Sendable
{
    struct Record: Equatable {
        let processID: pid_t
        let eventType: CGEventType
    }

    private let lock = NSLock()
    private var storedRecords: [Record] = []

    var records: [Record] {
        lock.withLock { storedRecords }
    }

    func post(_ event: CGEvent, to processID: pid_t) {
        lock.withLock {
            storedRecords.append(
                Record(processID: processID, eventType: event.type)
            )
        }
    }
}
