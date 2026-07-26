import AppKit
@preconcurrency import CoreGraphics
import Darwin
import Foundation

public struct ApplicationIdentity: Equatable, Hashable, Sendable {
    public let processIdentifier: pid_t
    public let bundleIdentifier: String

    public init(
        processIdentifier: pid_t,
        bundleIdentifier: String
    ) {
        self.processIdentifier = processIdentifier
        self.bundleIdentifier = bundleIdentifier
    }
}

public enum ForegroundRestorationResult: Equatable, Sendable {
    case restoredOriginalApplication
    case gameWasAlreadyFrontmost
}

public struct ForegroundActionResult: Equatable, Sendable {
    public let originalApplication: ApplicationIdentity
    public let targetApplication: ApplicationIdentity
    public let pointerBefore: CGPoint
    public let targetPoint: CGPoint
    public let pointerRestored: CGPoint
    public let expectedInputGeneration: UInt64
    public let inputGenerationBeforeClick: UInt64
    public let restoration: ForegroundRestorationResult

    public init(
        originalApplication: ApplicationIdentity,
        targetApplication: ApplicationIdentity,
        pointerBefore: CGPoint,
        targetPoint: CGPoint,
        pointerRestored: CGPoint,
        expectedInputGeneration: UInt64,
        inputGenerationBeforeClick: UInt64,
        restoration: ForegroundRestorationResult
    ) {
        self.originalApplication = originalApplication
        self.targetApplication = targetApplication
        self.pointerBefore = pointerBefore
        self.targetPoint = targetPoint
        self.pointerRestored = pointerRestored
        self.expectedInputGeneration = expectedInputGeneration
        self.inputGenerationBeforeClick = inputGenerationBeforeClick
        self.restoration = restoration
    }
}

public enum ForegroundActionFailure: Equatable, Sendable {
    case noFrontmostApplication
    case pointerLocationFailed(String)
    case invalidTargetBox
    case targetActivationFailed(String)
    case targetNotFrontmost
    case inputGenerationChanged(expected: UInt64, actual: UInt64)
    case pointerMoveFailed(String)
    case clickFailed(String)
    case postActionWaitFailed(String)
    case cancelled
    case cancelledAfterClick
}

public enum ForegroundRestorationFailure: Equatable, Sendable {
    case pointerRestoreFailed(String)
    case originalApplicationUnavailable(ApplicationIdentity)
    case originalApplicationActivationFailed(String)
    case originalApplicationNotFrontmost

    public var koreanDescription: String {
        switch self {
        case let .pointerRestoreFailed(reason):
            "포인터 복원 실패(\(reason))"
        case let .originalApplicationUnavailable(app):
            "원래 앱 종료됨(\(app.bundleIdentifier))"
        case let .originalApplicationActivationFailed(reason):
            "원래 앱 활성화 실패(\(reason))"
        case .originalApplicationNotFrontmost:
            "원래 앱이 최전면으로 복귀 실패"
        }
    }
}

public struct ForegroundActionCoordinatorError:
    Error,
    Equatable,
    Sendable
{
    public let primaryFailure: ForegroundActionFailure?
    public let restorationFailures: [ForegroundRestorationFailure]

    public init(
        primaryFailure: ForegroundActionFailure?,
        restorationFailures: [ForegroundRestorationFailure]
    ) {
        self.primaryFailure = primaryFailure
        self.restorationFailures = restorationFailures
    }
}

extension ForegroundActionCoordinatorError: LocalizedError {
    public var errorDescription: String? {
        let primary = primaryFailure.map { "action=\($0)" }
        let restoration = restorationFailures.isEmpty
            ? nil
            : "restoration=\(restorationFailures)"
        return [primary, restoration]
            .compactMap { $0 }
            .joined(separator: "; ")
    }
}

protocol ApplicationCoordinating: Sendable {
    func frontmostApplication() -> ApplicationIdentity?
    func activate(_ application: ApplicationIdentity) throws -> Bool
    func isFrontmost(_ application: ApplicationIdentity) -> Bool
    func isRunning(_ application: ApplicationIdentity) -> Bool
}

public protocol PointerControlling: Sendable {
    func location() throws -> CGPoint
    func move(
        to point: CGPoint,
        sourceIdentifier: Int64
    ) throws
}

protocol ActionSleeping: Sendable {
    func sleep(for duration: Duration) async throws
}

protocol PointerMoveEventCreating: Sendable {
    func makeMoveEvent(at screenPoint: CGPoint) -> CGEvent?
}

private enum ForegroundActionAbort: Error {
    case failure(ForegroundActionFailure)
}

/// 클릭 목표 박스 안에서 실제 클릭 좌표를 고른다.
protocol TargetPointSelecting: Sendable {
    func point(in box: CGRect) -> CGPoint?
}

/// 항상 박스 정중앙. 테스트 결정성용 기본값.
struct CenterTargetPointSelector: TargetPointSelecting {
    func point(in box: CGRect) -> CGPoint? {
        guard isUsableTargetBox(box) else { return nil }
        return CGPoint(x: box.midX, y: box.midY)
    }
}

/// 박스 가장자리에 insetFraction 여백을 두고 남은 중앙 영역에서 균일 임의
/// 지점을 고른다. 매번 정중앙을 찍지 않고 흩뿌려 '동일 위치 반복'을 없앤다.
/// 여백을 빼 범위가 사라지는 작은 박스는 중앙으로 폴백한다.
struct RandomTargetPointSelector: TargetPointSelecting {
    let insetFraction: Double

    func point(in box: CGRect) -> CGPoint? {
        guard isUsableTargetBox(box) else { return nil }
        let insetX = box.width * insetFraction
        let insetY = box.height * insetFraction
        let lowX = box.minX + insetX
        let highX = box.maxX - insetX
        let lowY = box.minY + insetY
        let highY = box.maxY - insetY
        let x = highX > lowX ? Double.random(in: lowX ... highX) : box.midX
        let y = highY > lowY ? Double.random(in: lowY ... highY) : box.midY
        return CGPoint(x: x, y: y)
    }
}

private func isUsableTargetBox(_ box: CGRect) -> Bool {
    !box.isNull
        && !box.isInfinite
        && box.origin.x.isFinite
        && box.origin.y.isFinite
        && box.size.width.isFinite
        && box.size.height.isFinite
        && box.size.width >= 0
        && box.size.height >= 0
}

public struct ForegroundActionCoordinator: Sendable {
    private let applications: any ApplicationCoordinating
    private let pointer: any PointerControlling
    private let clicker: any GlobalClicking
    private let sleeper: any ActionSleeping
    private let inputMonitor: any UserIdleMonitoring
    private let postActionDelay: Duration
    private let pointSelector: any TargetPointSelecting
    private let delayJitter: TimingJitter

    /// 사람이 마우스를 누르고 있는 시간은 대체로 50~120ms다. 지터를 얹어
    /// 60~100ms로 흩어진다. 지금까지는 0ms — 누름과 뗌이 같은 순간이었다.
    static let clickHold = Duration.milliseconds(80)

    public init(
        inputMonitor: any UserIdleMonitoring,
        postActionDelay: Duration = .milliseconds(500)
    ) {
        applications = WorkspaceApplicationCoordinator()
        pointer = CoreGraphicsPointerController()
        clicker = GlobalClickService()
        sleeper = ContinuousActionSleeper()
        self.inputMonitor = inputMonitor
        self.postActionDelay = postActionDelay
        pointSelector = RandomTargetPointSelector(insetFraction: 0.2)
        delayJitter = TimingJitter()
    }

    /// 테스트는 결정적이어야 하므로 기본 선택기·지터를 고정값으로 둔다.
    init(
        applications: any ApplicationCoordinating,
        pointer: any PointerControlling,
        clicker: any GlobalClicking,
        sleeper: any ActionSleeping,
        inputMonitor: any UserIdleMonitoring,
        postActionDelay: Duration = .milliseconds(500),
        pointSelector: any TargetPointSelecting = CenterTargetPointSelector(),
        delayJitter: TimingJitter = TimingJitter(spread: 0)
    ) {
        self.applications = applications
        self.pointer = pointer
        self.clicker = clicker
        self.sleeper = sleeper
        self.inputMonitor = inputMonitor
        self.postActionDelay = postActionDelay
        self.pointSelector = pointSelector
        self.delayJitter = delayJitter
    }

    public func perform(
        targetApplication: ApplicationIdentity,
        targetBox: CGRect,
        expectedInputGeneration: UInt64
    ) async throws -> ForegroundActionResult {
        guard let originalApplication = applications.frontmostApplication()
        else {
            throw ForegroundActionCoordinatorError(
                primaryFailure: .noFrontmostApplication,
                restorationFailures: []
            )
        }

        let pointerBefore: CGPoint
        do {
            pointerBefore = try pointer.location()
        } catch {
            throw ForegroundActionCoordinatorError(
                primaryFailure: .pointerLocationFailed(
                    String(describing: error)
                ),
                restorationFailures: []
            )
        }

        guard let targetPoint = pointSelector.point(in: targetBox) else {
            throw ForegroundActionCoordinatorError(
                primaryFailure: .invalidTargetBox,
                restorationFailures: []
            )
        }

        let gameWasAlreadyFrontmost =
            originalApplication == targetApplication
        var activationMayHaveChangedFocus = false
        var pointerMayHaveChanged = false
        var inputGenerationBeforeClick = expectedInputGeneration
        var primaryFailure: ForegroundActionFailure?
        var clickCompleted = false

        do {
            try Self.checkCancellation()

            if !gameWasAlreadyFrontmost {
                activationMayHaveChangedFocus = true
                let activated: Bool
                do {
                    activated = try applications.activate(
                        targetApplication
                    )
                } catch is CancellationError {
                    throw ForegroundActionAbort.failure(.cancelled)
                } catch {
                    try Self.checkCancellation()
                    throw ForegroundActionAbort.failure(
                        .targetActivationFailed(
                            String(describing: error)
                        )
                    )
                }
                try Self.checkCancellation()
                guard activated else {
                    throw ForegroundActionAbort.failure(
                        .targetActivationFailed("returned false")
                    )
                }
            }

            guard applications.isFrontmost(targetApplication) else {
                throw ForegroundActionAbort.failure(.targetNotFrontmost)
            }

            let inputBeforeClick = await inputMonitor.snapshot()
            try Self.checkCancellation()
            inputGenerationBeforeClick = inputBeforeClick.generation
            guard
                inputBeforeClick.generation == expectedInputGeneration
            else {
                throw ForegroundActionAbort.failure(
                    .inputGenerationChanged(
                        expected: expectedInputGeneration,
                        actual: inputBeforeClick.generation
                    )
                )
            }

            try Self.checkCancellation()
            pointerMayHaveChanged = true
            do {
                try pointer.move(
                    to: targetPoint,
                    sourceIdentifier:
                        AutomatorSyntheticEvent.sourceIdentifier
                )
            } catch is CancellationError {
                throw ForegroundActionAbort.failure(.cancelled)
            } catch {
                throw ForegroundActionAbort.failure(
                    .pointerMoveFailed(String(describing: error))
                )
            }

            let inputImmediatelyBeforeClick =
                await inputMonitor.snapshot()
            try Self.checkCancellation()
            inputGenerationBeforeClick =
                inputImmediatelyBeforeClick.generation
            guard
                inputImmediatelyBeforeClick.generation
                    == expectedInputGeneration
            else {
                throw ForegroundActionAbort.failure(
                    .inputGenerationChanged(
                        expected: expectedInputGeneration,
                        actual: inputImmediatelyBeforeClick.generation
                    )
                )
            }

            try Self.checkCancellation()
            guard applications.isFrontmost(targetApplication) else {
                throw ForegroundActionAbort.failure(.targetNotFrontmost)
            }

            do {
                try clicker.click(
                    screenPoint: targetPoint,
                    sourceIdentifier:
                        AutomatorSyntheticEvent.sourceIdentifier,
                    hold: delayJitter.applied(to: Self.clickHold)
                )
                clickCompleted = true
            } catch is CancellationError {
                throw ForegroundActionAbort.failure(.cancelled)
            } catch {
                throw ForegroundActionAbort.failure(
                    .clickFailed(String(describing: error))
                )
            }

            do {
                try await sleeper.sleep(
                    for: delayJitter.applied(to: postActionDelay)
                )
            } catch is CancellationError {
                throw ForegroundActionAbort.failure(
                    .cancelledAfterClick
                )
            } catch {
                throw ForegroundActionAbort.failure(
                    .postActionWaitFailed(String(describing: error))
                )
            }
            if Task.isCancelled {
                throw ForegroundActionAbort.failure(
                    .cancelledAfterClick
                )
            }
        } catch let ForegroundActionAbort.failure(failure) {
            primaryFailure = failure
        } catch is CancellationError {
            primaryFailure = clickCompleted
                ? .cancelledAfterClick
                : .cancelled
        } catch {
            primaryFailure = .postActionWaitFailed(
                String(describing: error)
            )
        }

        var restorationFailures: [ForegroundRestorationFailure] = []

        if pointerMayHaveChanged {
            do {
                try pointer.move(
                    to: pointerBefore,
                    sourceIdentifier:
                        AutomatorSyntheticEvent.sourceIdentifier
                )
            } catch {
                restorationFailures.append(
                    .pointerRestoreFailed(String(describing: error))
                )
            }
        }

        if activationMayHaveChangedFocus {
            if !applications.isRunning(originalApplication) {
                restorationFailures.append(
                    .originalApplicationUnavailable(originalApplication)
                )
            } else {
                var activationSucceeded = false
                do {
                    if try applications.activate(originalApplication) {
                        activationSucceeded = true
                    } else {
                        restorationFailures.append(
                            .originalApplicationActivationFailed(
                                "returned false"
                            )
                        )
                    }
                } catch {
                    restorationFailures.append(
                        .originalApplicationActivationFailed(
                            String(describing: error)
                        )
                    )
                }

                if activationSucceeded,
                    !applications.isFrontmost(originalApplication)
                {
                    restorationFailures.append(
                        .originalApplicationNotFrontmost
                    )
                }
            }
        }

        if primaryFailure != nil || !restorationFailures.isEmpty {
            throw ForegroundActionCoordinatorError(
                primaryFailure: primaryFailure,
                restorationFailures: restorationFailures
            )
        }

        return ForegroundActionResult(
            originalApplication: originalApplication,
            targetApplication: targetApplication,
            pointerBefore: pointerBefore,
            targetPoint: targetPoint,
            pointerRestored: pointerBefore,
            expectedInputGeneration: expectedInputGeneration,
            inputGenerationBeforeClick: inputGenerationBeforeClick,
            restoration: gameWasAlreadyFrontmost
                ? .gameWasAlreadyFrontmost
                : .restoredOriginalApplication
        )
    }

    private static func checkCancellation() throws {
        do {
            try Task.checkCancellation()
        } catch is CancellationError {
            throw ForegroundActionAbort.failure(.cancelled)
        }
    }
}

private final class WorkspaceApplicationCoordinator:
    ApplicationCoordinating,
    @unchecked Sendable
{
    func frontmostApplication() -> ApplicationIdentity? {
        guard
            let application = NSWorkspace.shared.frontmostApplication,
            let bundleIdentifier = application.bundleIdentifier
        else {
            return nil
        }
        return ApplicationIdentity(
            processIdentifier: application.processIdentifier,
            bundleIdentifier: bundleIdentifier
        )
    }

    func activate(_ application: ApplicationIdentity) throws -> Bool {
        guard let runningApplication = exactApplication(application) else {
            return false
        }
        return runningApplication.activate(options: [])
    }

    func isFrontmost(_ application: ApplicationIdentity) -> Bool {
        frontmostApplication() == application
    }

    func isRunning(_ application: ApplicationIdentity) -> Bool {
        exactApplication(application) != nil
    }

    private func exactApplication(
        _ identity: ApplicationIdentity
    ) -> NSRunningApplication? {
        guard
            let application = NSRunningApplication(
                processIdentifier: identity.processIdentifier
            ),
            application.bundleIdentifier == identity.bundleIdentifier,
            !application.isTerminated
        else {
            return nil
        }
        return application
    }
}

private enum PointerControllerError: Error {
    case cannotReadPointer
    case cannotCreateMoveEvent
}

private struct CoreGraphicsPointerMoveEventFactory:
    PointerMoveEventCreating
{
    func makeMoveEvent(at screenPoint: CGPoint) -> CGEvent? {
        guard let source = CGEventSource(stateID: .hidSystemState) else {
            return nil
        }
        return CGEvent(
            mouseEventSource: source,
            mouseType: .mouseMoved,
            mouseCursorPosition: screenPoint,
            mouseButton: .left
        )
    }
}

struct CoreGraphicsPointerController: PointerControlling {
    private let eventFactory: any PointerMoveEventCreating
    private let eventPoster: any GlobalEventPosting
    private let locationReader: @Sendable () throws -> CGPoint

    init() {
        eventFactory = CoreGraphicsPointerMoveEventFactory()
        eventPoster = CoreGraphicsGlobalPointerEventPoster()
        locationReader = {
            guard let event = CGEvent(source: nil) else {
                throw PointerControllerError.cannotReadPointer
            }
            return event.location
        }
    }

    init(
        eventFactory: any PointerMoveEventCreating,
        eventPoster: any GlobalEventPosting,
        locationReader: @escaping @Sendable () throws -> CGPoint
    ) {
        self.eventFactory = eventFactory
        self.eventPoster = eventPoster
        self.locationReader = locationReader
    }

    func location() throws -> CGPoint {
        try locationReader()
    }

    func move(
        to point: CGPoint,
        sourceIdentifier: Int64
    ) throws {
        guard let event = eventFactory.makeMoveEvent(at: point) else {
            throw PointerControllerError.cannotCreateMoveEvent
        }
        event.setIntegerValueField(
            .eventSourceUserData,
            value: sourceIdentifier
        )
        eventPoster.post(event)
    }
}

private struct CoreGraphicsGlobalPointerEventPoster:
    GlobalEventPosting
{
    func post(_ event: CGEvent) {
        event.post(tap: .cghidEventTap)
    }
}

private struct ContinuousActionSleeper: ActionSleeping {
    func sleep(for duration: Duration) async throws {
        try await ContinuousClock().sleep(for: duration)
    }
}
