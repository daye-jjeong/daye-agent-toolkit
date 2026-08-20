import Testing

@testable import MAgentRuntime

@Test
func reexportsCoreVersion() {
    #expect(MAgentRuntime.version == "0.1.0")
}
