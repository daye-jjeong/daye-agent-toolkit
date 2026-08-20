import ApplicationServices
import CoreGraphics
import Foundation

public struct AccessibilityWindowState: Equatable, Sendable {
    public let title: String
    public let frame: CGRect
    public let isMinimized: Bool

    public init(title: String, frame: CGRect, isMinimized: Bool) {
        self.title = title
        self.frame = frame
        self.isMinimized = isMinimized
    }
}

public enum WindowVisibilityError: Error, Equatable, Sendable {
    case accessibilityNotTrusted(processID: Int32)
    case accessibilityQueryFailed(
        processID: Int32,
        attribute: String,
        code: Int32
    )
    case accessibilityWindowNotFound(windowID: UInt32)
    case accessibilityWindowAmbiguous(windowID: UInt32)
    case accessibilityInvalidValue(
        processID: Int32,
        attribute: String
    )
}

extension WindowVisibilityError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case let .accessibilityNotTrusted(processID):
            "Accessibility access is not trusted for process \(processID)."
        case let .accessibilityQueryFailed(processID, attribute, code):
            "Accessibility query \(attribute) failed for process \(processID) with code \(code)."
        case let .accessibilityWindowNotFound(windowID):
            "No Accessibility window exactly matched window \(windowID)."
        case let .accessibilityWindowAmbiguous(windowID):
            "More than one Accessibility window matched window \(windowID)."
        case let .accessibilityInvalidValue(processID, attribute):
            "Accessibility query \(attribute) returned an invalid value for process \(processID)."
        }
    }
}

protocol AccessibilityWindowProviding: Sendable {
    func windows(processID: Int32) throws -> [AccessibilityWindowState]
}

struct AXAccessibilityWindowProvider: AccessibilityWindowProviding {
    func windows(processID: Int32) throws -> [AccessibilityWindowState] {
        guard AXIsProcessTrusted() else {
            throw WindowVisibilityError.accessibilityNotTrusted(
                processID: processID
            )
        }

        let application = AXUIElementCreateApplication(processID)
        let windowsValue = try attributeValue(
            element: application,
            attribute: kAXWindowsAttribute,
            processID: processID
        )
        guard let windows = windowsValue as? [AXUIElement] else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: kAXWindowsAttribute
            )
        }

        return try windows.map {
            try windowState(element: $0, processID: processID)
        }
    }

    private func windowState(
        element: AXUIElement,
        processID: Int32
    ) throws -> AccessibilityWindowState {
        let titleValue = try attributeValue(
            element: element,
            attribute: kAXTitleAttribute,
            processID: processID
        )
        guard let title = titleValue as? String else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: kAXTitleAttribute
            )
        }

        let position = try pointValue(
            element: element,
            attribute: kAXPositionAttribute,
            processID: processID
        )
        let size = try sizeValue(
            element: element,
            attribute: kAXSizeAttribute,
            processID: processID
        )
        let minimizedValue = try attributeValue(
            element: element,
            attribute: kAXMinimizedAttribute,
            processID: processID
        )
        guard let minimized = minimizedValue as? NSNumber else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: kAXMinimizedAttribute
            )
        }

        return AccessibilityWindowState(
            title: title,
            frame: CGRect(origin: position, size: size),
            isMinimized: minimized.boolValue
        )
    }

    private func pointValue(
        element: AXUIElement,
        attribute: String,
        processID: Int32
    ) throws -> CGPoint {
        let value = try axValue(
            element: element,
            attribute: attribute,
            processID: processID,
            expectedType: .cgPoint
        )
        var point = CGPoint.zero
        guard AXValueGetValue(value, .cgPoint, &point) else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: attribute
            )
        }
        return point
    }

    private func sizeValue(
        element: AXUIElement,
        attribute: String,
        processID: Int32
    ) throws -> CGSize {
        let value = try axValue(
            element: element,
            attribute: attribute,
            processID: processID,
            expectedType: .cgSize
        )
        var size = CGSize.zero
        guard AXValueGetValue(value, .cgSize, &size) else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: attribute
            )
        }
        return size
    }

    private func axValue(
        element: AXUIElement,
        attribute: String,
        processID: Int32,
        expectedType: AXValueType
    ) throws -> AXValue {
        let rawValue = try attributeValue(
            element: element,
            attribute: attribute,
            processID: processID
        )
        guard CFGetTypeID(rawValue) == AXValueGetTypeID() else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: attribute
            )
        }
        let value = unsafeDowncast(rawValue, to: AXValue.self)
        guard AXValueGetType(value) == expectedType else {
            throw WindowVisibilityError.accessibilityInvalidValue(
                processID: processID,
                attribute: attribute
            )
        }
        return value
    }

    private func attributeValue(
        element: AXUIElement,
        attribute: String,
        processID: Int32
    ) throws -> CFTypeRef {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(
            element,
            attribute as CFString,
            &value
        )
        guard error == .success, let value else {
            throw WindowVisibilityError.accessibilityQueryFailed(
                processID: processID,
                attribute: attribute,
                code: Int32(error.rawValue)
            )
        }
        return value
    }
}

struct CoreGraphicsWindowState: Equatable, Sendable {
    let processID: Int32
    let isOnScreen: Bool
}

enum WindowVisibilityValidator {
    static func isVisible(
        screenCaptureKitIsOnScreen: Bool,
        processID: Int32,
        coreGraphicsWindow: CoreGraphicsWindowState?
    ) -> Bool {
        screenCaptureKitIsOnScreen
            && coreGraphicsWindow?.processID == processID
            && coreGraphicsWindow?.isOnScreen == true
    }

    static func accessibilityWindow(
        matching candidate: WindowCandidate,
        from windows: [AccessibilityWindowState]
    ) throws -> AccessibilityWindowState {
        let matches = windows.filter {
            $0.title == candidate.title && $0.frame == candidate.frame
        }

        switch matches.count {
        case 1:
            return matches[0]
        case 0:
            throw WindowVisibilityError.accessibilityWindowNotFound(
                windowID: candidate.windowID
            )
        default:
            throw WindowVisibilityError.accessibilityWindowAmbiguous(
                windowID: candidate.windowID
            )
        }
    }

    static func isVisible(
        accessibilityWindow: AccessibilityWindowState
    ) -> Bool {
        !accessibilityWindow.isMinimized
    }
}

protocol WindowVisibilityProviding: Sendable {
    func snapshot() -> [UInt32: CoreGraphicsWindowState]
}

struct CoreGraphicsWindowVisibilityProvider: WindowVisibilityProviding {
    func snapshot() -> [UInt32: CoreGraphicsWindowState] {
        guard
            let windows = CGWindowListCopyWindowInfo(
                .optionAll,
                kCGNullWindowID
            ) as? [[CFString: Any]]
        else {
            return [:]
        }

        var states: [UInt32: CoreGraphicsWindowState] = [:]
        for window in windows {
            guard
                let windowID = window[kCGWindowNumber] as? NSNumber,
                let processID = window[kCGWindowOwnerPID] as? NSNumber,
                let isOnScreen = window[kCGWindowIsOnscreen] as? NSNumber
            else {
                continue
            }

            states[windowID.uint32Value] = CoreGraphicsWindowState(
                processID: processID.int32Value,
                isOnScreen: isOnScreen.boolValue
            )
        }
        return states
    }
}
