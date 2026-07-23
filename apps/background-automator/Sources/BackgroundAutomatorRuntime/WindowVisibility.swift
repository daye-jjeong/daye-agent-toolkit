import CoreGraphics
import Foundation

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
