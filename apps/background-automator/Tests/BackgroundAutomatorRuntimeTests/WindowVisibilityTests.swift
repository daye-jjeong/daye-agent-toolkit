import Testing

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
