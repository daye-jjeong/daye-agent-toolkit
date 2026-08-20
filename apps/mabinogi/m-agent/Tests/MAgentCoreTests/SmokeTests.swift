import Testing

@testable import MAgentCore

@Test
func exposesCurrentVersion() {
    #expect(MAgentCore.version == "0.1.0")
}
