import CoreGraphics
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func selectsExactBundleIdentifier() throws {
    let expected = candidate(windowID: 1, bundleIdentifier: "com.example.target")
    let other = candidate(windowID: 2, bundleIdentifier: "com.example.target.beta")

    let selected = try WindowTarget.select(
        from: [other, expected],
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )

    #expect(selected == expected)
}

@Test
func matchesTitleCaseInsensitively() throws {
    let expected = candidate(windowID: 1, title: "My Great GAME Window")

    let selected = try WindowTarget.select(
        from: [expected],
        bundleIdentifier: "com.example.target",
        titleContains: "great game"
    )

    #expect(selected == expected)
}

@Test
func rejectsOffscreenWindows() {
    let offscreen = candidate(windowID: 1, isOnScreen: false)

    #expect(throws: WindowTargetError.notFound) {
        try WindowTarget.select(
            from: [offscreen],
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
}

@Test(arguments: [
    CGRect(x: 0, y: 0, width: 0, height: 100),
    CGRect(x: 0, y: 0, width: 100, height: 0),
    CGRect(x: 0, y: 0, width: -1, height: 100),
    CGRect(x: 0, y: 0, width: 100, height: -1),
])
func rejectsNonPositiveDimensions(frame: CGRect) {
    let invalid = candidate(windowID: 1, frame: frame)

    #expect(throws: WindowTargetError.notFound) {
        try WindowTarget.select(
            from: [invalid],
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
}

@Test
func throwsNotFoundWhenNoCandidateMatches() {
    #expect(throws: WindowTargetError.notFound) {
        try WindowTarget.select(
            from: [],
            bundleIdentifier: "com.example.target",
            titleContains: "Game"
        )
    }
}

@Test
func selectsLargestVisibleDuplicate() throws {
    let small = candidate(
        windowID: 1,
        frame: CGRect(x: 0, y: 0, width: 640, height: 480)
    )
    let large = candidate(
        windowID: 2,
        frame: CGRect(x: 0, y: 0, width: 1920, height: 1080)
    )
    let largerButOffscreen = candidate(
        windowID: 3,
        frame: CGRect(x: 0, y: 0, width: 2560, height: 1440),
        isOnScreen: false
    )

    let selected = try WindowTarget.select(
        from: [small, largerButOffscreen, large],
        bundleIdentifier: "com.example.target",
        titleContains: "Game"
    )

    #expect(selected == large)
}

private func candidate(
    windowID: UInt32,
    processID: Int32 = 42,
    bundleIdentifier: String = "com.example.target",
    title: String = "Game",
    frame: CGRect = CGRect(x: 0, y: 0, width: 800, height: 600),
    isOnScreen: Bool = true
) -> WindowCandidate {
    WindowCandidate(
        windowID: windowID,
        processID: processID,
        bundleIdentifier: bundleIdentifier,
        title: title,
        frame: frame,
        isOnScreen: isOnScreen
    )
}
