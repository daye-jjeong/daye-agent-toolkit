import Foundation
import Testing

@Test
func successfulProbeCommandExitsPromptly() throws {
    let process = Process()
    let standardOutput = Pipe()
    process.executableURL = try probeExecutableURL()
    process.arguments = ["version"]
    process.standardOutput = standardOutput
    process.standardError = FileHandle.nullDevice

    try process.run()

    let deadline = Date().addingTimeInterval(2)
    while process.isRunning, Date() < deadline {
        Thread.sleep(forTimeInterval: 0.01)
    }

    if process.isRunning {
        process.terminate()
        process.waitUntilExit()
        Issue.record("Successful probe command did not exit within 2 seconds.")
        return
    }

    #expect(process.terminationReason == .exit)
    #expect(process.terminationStatus == 0)
    let output = standardOutput.fileHandleForReading.readDataToEndOfFile()
    #expect(
        String(decoding: output, as: UTF8.self)
            == "MAgentProbe 0.1.0\n"
    )
}

private func probeExecutableURL() throws -> URL {
    let packageDirectory = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let candidate = packageDirectory
        .appendingPathComponent(".build")
        .appendingPathComponent("debug")
        .appendingPathComponent("MAgentProbe")

    if FileManager.default.isExecutableFile(atPath: candidate.path) {
        return candidate
    }

    throw ProbeLifecycleTestError.executableNotFound
}

private enum ProbeLifecycleTestError: Error {
    case executableNotFound
}
