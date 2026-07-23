import Testing
import CoreGraphics

@testable import BackgroundAutomatorRuntime

@Test
func visibilityAcceptsMatchingOnscreenSignals() {
    let coreGraphicsWindow = CoreGraphicsWindowState(
        processID: 42,
        isOnScreen: true
    )

    #expect(
        WindowVisibilityValidator.isVisible(
            screenCaptureKitIsOnScreen: true,
            processID: 42,
            coreGraphicsWindow: coreGraphicsWindow
        )
    )
}

@Test
func visibilityRejectsScreenCaptureKitOffscreenWindow() {
    let coreGraphicsWindow = CoreGraphicsWindowState(
        processID: 42,
        isOnScreen: true
    )

    #expect(
        !WindowVisibilityValidator.isVisible(
            screenCaptureKitIsOnScreen: false,
            processID: 42,
            coreGraphicsWindow: coreGraphicsWindow
        )
    )
}

@Test
func visibilityRejectsCoreGraphicsOffscreenWindow() {
    let coreGraphicsWindow = CoreGraphicsWindowState(
        processID: 42,
        isOnScreen: false
    )

    #expect(
        !WindowVisibilityValidator.isVisible(
            screenCaptureKitIsOnScreen: true,
            processID: 42,
            coreGraphicsWindow: coreGraphicsWindow
        )
    )
}

@Test
func visibilityRejectsMissingCoreGraphicsWindow() {
    #expect(
        !WindowVisibilityValidator.isVisible(
            screenCaptureKitIsOnScreen: true,
            processID: 42,
            coreGraphicsWindow: nil
        )
    )
}

@Test
func visibilityRejectsReusedWindowIDFromDifferentProcess() {
    let replacement = CoreGraphicsWindowState(
        processID: 99,
        isOnScreen: true
    )

    #expect(
        !WindowVisibilityValidator.isVisible(
            screenCaptureKitIsOnScreen: true,
            processID: 42,
            coreGraphicsWindow: replacement
        )
    )
}

@Test
func accessibilityMatcherSelectsExactTitleAndFrame() throws {
    let candidate = windowCandidate(
        windowID: 7,
        title: "Game",
        frame: CGRect(x: 10, y: 20, width: 800, height: 600)
    )
    let expected = AccessibilityWindowState(
        title: "Game",
        frame: candidate.frame,
        isMinimized: false
    )
    let other = AccessibilityWindowState(
        title: "Game",
        frame: CGRect(x: 20, y: 30, width: 800, height: 600),
        isMinimized: true
    )

    let matched = try WindowVisibilityValidator.accessibilityWindow(
        matching: candidate,
        from: [other, expected]
    )

    #expect(matched == expected)
}

@Test
func accessibilityMatcherRejectsMissingExactFrame() {
    let candidate = windowCandidate(
        windowID: 7,
        title: "Game",
        frame: CGRect(x: 10, y: 20, width: 800, height: 600)
    )
    let differentFrame = AccessibilityWindowState(
        title: "Game",
        frame: CGRect(x: 20, y: 30, width: 800, height: 600),
        isMinimized: false
    )

    #expect(
        throws: WindowVisibilityError.accessibilityWindowNotFound(windowID: 7)
    ) {
        try WindowVisibilityValidator.accessibilityWindow(
            matching: candidate,
            from: [differentFrame]
        )
    }
}

@Test
func accessibilityMatcherRejectsAmbiguousExactMatches() {
    let candidate = windowCandidate(
        windowID: 7,
        title: "Game",
        frame: CGRect(x: 10, y: 20, width: 800, height: 600)
    )
    let duplicate = AccessibilityWindowState(
        title: "Game",
        frame: candidate.frame,
        isMinimized: false
    )

    #expect(
        throws: WindowVisibilityError.accessibilityWindowAmbiguous(windowID: 7)
    ) {
        try WindowVisibilityValidator.accessibilityWindow(
            matching: candidate,
            from: [duplicate, duplicate]
        )
    }
}

@Test
func accessibilityVisibilityRejectsMinimizedWindow() {
    let minimized = AccessibilityWindowState(
        title: "Game",
        frame: CGRect(x: 10, y: 20, width: 800, height: 600),
        isMinimized: true
    )

    #expect(!WindowVisibilityValidator.isVisible(accessibilityWindow: minimized))
}

private func windowCandidate(
    windowID: UInt32,
    processID: Int32 = 42,
    title: String,
    frame: CGRect
) -> WindowCandidate {
    WindowCandidate(
        windowID: windowID,
        processID: processID,
        bundleIdentifier: "com.example.target",
        title: title,
        frame: frame,
        isOnScreen: true
    )
}
