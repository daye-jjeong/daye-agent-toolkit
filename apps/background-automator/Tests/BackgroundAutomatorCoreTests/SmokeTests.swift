import Testing

@testable import BackgroundAutomatorCore

@Test
func exposesCurrentVersion() {
    #expect(BackgroundAutomatorCore.version == "0.1.0")
}
