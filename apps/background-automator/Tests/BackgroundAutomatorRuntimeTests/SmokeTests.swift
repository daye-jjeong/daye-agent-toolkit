import Testing

@testable import BackgroundAutomatorRuntime

@Test
func reexportsCoreVersion() {
    #expect(BackgroundAutomatorRuntime.version == "0.1.0")
}
