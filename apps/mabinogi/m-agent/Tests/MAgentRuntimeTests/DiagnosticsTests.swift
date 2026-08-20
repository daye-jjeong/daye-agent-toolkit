import MAgentCore
import CoreGraphics
import Foundation
import Testing

@testable import MAgentRuntime

// MARK: - PreflightDiagnostics

@Test
func preflightDiagnosticsMapsReadyContextWithLayoutAndRatio() {
    let window = diagnosticsWindow(
        frame: CGRect(x: -1_512, y: 203, width: 1_512, height: 949)
    )
    let diagnostics = PreflightDiagnostics(
        result: .ready(
            PreflightReadyContext(window: window, layout: .landscape)
        )
    )

    #expect(diagnostics.outcome == "ready")
    #expect(diagnostics.guidance == nil)
    #expect(diagnostics.windowWidth == 1_512)
    #expect(diagnostics.windowHeight == 949)
    #expect(diagnostics.aspectRatio == 1.5933)
    #expect(diagnostics.layout == "landscape")
}

@Test
func preflightDiagnosticsMapsUnsupportedLayoutWithMeasuredSize() {
    let diagnostics = PreflightDiagnostics(
        result: .needsAttention(
            .unsupportedLayout(
                measured: CGSize(width: 1_098, height: 949)
            )
        )
    )

    #expect(diagnostics.outcome == "unsupportedLayout")
    #expect(diagnostics.guidance?.contains("1098") == true)
    #expect(diagnostics.windowWidth == 1_098)
    #expect(diagnostics.windowHeight == 949)
    #expect(diagnostics.aspectRatio == 1.157)
    #expect(diagnostics.layout == nil)
}

@Test
func preflightDiagnosticsMapsPermissionIssueWithoutWindowData() {
    let diagnostics = PreflightDiagnostics(
        result: .needsAttention(.screenRecordingDenied)
    )

    #expect(diagnostics.outcome == "screenRecordingDenied")
    #expect(diagnostics.guidance?.contains("화면 기록") == true)
    #expect(diagnostics.windowWidth == nil)
    #expect(diagnostics.windowHeight == nil)
    #expect(diagnostics.aspectRatio == nil)
    #expect(diagnostics.layout == nil)
}

// MARK: - ObservationDiagnostics

@Test
func observationDiagnosticsMapsFrameTextsCandidatesAndAppearance() throws {
    let evidence = RuleAppearanceEvidence(
        contextBoundingBox: CGRect(x: 1, y: 2, width: 3, height: 4),
        targetBoundingBox: CGRect(x: 5, y: 6, width: 7, height: 8),
        contextStatistics: AppearanceStatistics(
            medianSaturation: 0.1234,
            medianLuminance: 0.5678,
            sampleCount: 100
        ),
        targetStatistics: AppearanceStatistics(
            medianSaturation: 0.4321,
            medianLuminance: 0.8765,
            sampleCount: 200
        )
    )
    let frame = AutomationScreenFrame(
        observation: SceneObservation(
            captureIdentity: try CaptureIdentity(
                sessionID: UUID(),
                sequence: 3
            ),
            imageSize: CGSize(width: 1_512, height: 949),
            recognizedTexts: [
                RecognizedTextObservation(
                    text: "입장하기",
                    confidence: 0.987_654,
                    boundingBox: CGRect(
                        x: 10.44,
                        y: 20.55,
                        width: 30.66,
                        height: 40.77
                    )
                ),
            ],
            actionCandidates: [
                SceneActionCandidate(
                    ruleID: "enter_ready",
                    targetText: "입장하기",
                    boundingBox: CGRect(x: 1, y: 2, width: 3, height: 4),
                    confidence: 0.99
                ),
            ],
            appearanceEvidence: ["enter_ready": evidence]
        ),
        window: diagnosticsWindow(
            frame: CGRect(x: 0, y: 0, width: 1_512, height: 949)
        ),
        layout: .landscape
    )

    let diagnostics = ObservationDiagnostics(frame: frame)

    #expect(diagnostics.imageWidth == 1_512)
    #expect(diagnostics.imageHeight == 949)
    #expect(diagnostics.layout == "landscape")
    #expect(diagnostics.recognizedTexts.count == 1)
    #expect(diagnostics.recognizedTexts.first?.text == "입장하기")
    #expect(diagnostics.recognizedTexts.first?.confidence == 0.988)
    #expect(diagnostics.recognizedTexts.first?.box.x == 10.4)
    #expect(
        diagnostics.actionCandidates.map(\.ruleID) == ["enter_ready"]
    )
    #expect(
        diagnostics.actionCandidates.first?.targetText == "입장하기"
    )
    let appearance = try #require(
        diagnostics.appearanceEvidence["enter_ready"]
    )
    #expect(appearance.contextMedianSaturation == 0.123)
    #expect(appearance.contextMedianLuminance == 0.568)
    #expect(appearance.contextSampleCount == 100)
    #expect(appearance.targetMedianSaturation == 0.432)
    #expect(appearance.targetMedianLuminance == 0.877)
    #expect(appearance.targetSampleCount == 200)
}

@Test
func observationDiagnosticsKeepsEveryRecognizedText() throws {
    // 예전엔 24개에서 잘랐다. 남길 24개를 OCR이 돌려준 순서로 골라서,
    // 화면 아래쪽 버튼이 통째로 빠지는 일이 생겼다(2026-07-29 실측:
    // '다시 하기'가 후보로는 잡혔는데 진단 파일엔 없어서, 버튼을 못 읽은
    // 것으로 오진했다). 항목 하나가 107바이트라 40개여도 4.2KB고,
    // 이 파일은 매 관찰마다 덮어쓰므로 쌓이지도 않는다.
    let texts = (0 ..< 40).map { index in
        RecognizedTextObservation(
            text: String(repeating: "가", count: 100),
            confidence: 0.9,
            boundingBox: CGRect(
                x: 0,
                y: Double(index),
                width: 10,
                height: 5
            )
        )
    }
    let frame = AutomationScreenFrame(
        observation: SceneObservation(
            captureIdentity: try CaptureIdentity(
                sessionID: UUID(),
                sequence: 1
            ),
            imageSize: CGSize(width: 600, height: 900),
            recognizedTexts: texts,
            actionCandidates: []
        ),
        window: diagnosticsWindow(
            frame: CGRect(x: 0, y: 0, width: 600, height: 900)
        ),
        layout: .portraitMobile
    )

    let diagnostics = ObservationDiagnostics(frame: frame)

    #expect(diagnostics.recognizedTexts.count == texts.count)
    // 개당 길이는 계속 자른다. 이건 항목을 지우는 게 아니라 한 항목을
    // 짧게 만드는 것뿐이라, 무엇이 보였는지는 그대로 남는다.
    #expect(
        diagnostics.recognizedTexts.allSatisfy {
            $0.text.count <= ObservationDiagnostics.maximumTextLength
        }
    )
}

// MARK: - DiagnosticsFileWriter

@Test
func diagnosticsWriterCreatesDirectoryAndWritesDecodableSnapshot() throws {
    let directory = uniqueDiagnosticsDirectory()
    defer {
        removeDiagnosticsDirectory(directory)
    }
    let writer = DiagnosticsFileWriter(directory: directory)
    let content = sampleDiagnosticsContent(statusDescription: "화면 확인 중")
    let timestamp = Date(timeIntervalSince1970: 1_753_000_000)

    let result = writer.write(content: content, at: timestamp)

    #expect(result == .written)
    let snapshot = try decodeDiagnosticsSnapshot(in: directory)
    #expect(snapshot.content == content)
    #expect(snapshot.updatedAt == timestamp)
}

@Test
func diagnosticsWriterSkipsRewritingUnchangedContent() throws {
    let directory = uniqueDiagnosticsDirectory()
    defer {
        removeDiagnosticsDirectory(directory)
    }
    let writer = DiagnosticsFileWriter(directory: directory)
    let content = sampleDiagnosticsContent(statusDescription: "화면 확인 중")
    let firstTimestamp = Date(timeIntervalSince1970: 1_753_000_000)
    let secondTimestamp = Date(timeIntervalSince1970: 1_753_000_060)

    #expect(writer.write(content: content, at: firstTimestamp) == .written)
    #expect(
        writer.write(content: content, at: secondTimestamp)
            == .skippedUnchanged
    )

    let snapshot = try decodeDiagnosticsSnapshot(in: directory)
    #expect(snapshot.updatedAt == firstTimestamp)
}

@Test
func diagnosticsWriterRewritesWhenContentChanges() throws {
    let directory = uniqueDiagnosticsDirectory()
    defer {
        removeDiagnosticsDirectory(directory)
    }
    let writer = DiagnosticsFileWriter(directory: directory)
    let first = sampleDiagnosticsContent(statusDescription: "화면 확인 중")
    let second = sampleDiagnosticsContent(statusDescription: "버튼 감지됨")

    #expect(
        writer.write(
            content: first,
            at: Date(timeIntervalSince1970: 1_753_000_000)
        ) == .written
    )
    #expect(
        writer.write(
            content: second,
            at: Date(timeIntervalSince1970: 1_753_000_060)
        ) == .written
    )

    let snapshot = try decodeDiagnosticsSnapshot(in: directory)
    #expect(snapshot.content == second)
}

@Test
func diagnosticsWriterReportsFailureWhenDirectoryPathIsAFile() throws {
    let parent = uniqueDiagnosticsDirectory()
    defer {
        removeDiagnosticsDirectory(parent)
    }
    try FileManager.default.createDirectory(
        at: parent,
        withIntermediateDirectories: true
    )
    let blockedDirectory = parent.appendingPathComponent("blocked")
    try Data("파일".utf8).write(to: blockedDirectory)
    let writer = DiagnosticsFileWriter(directory: blockedDirectory)

    let result = writer.write(
        content: sampleDiagnosticsContent(statusDescription: "화면 확인 중"),
        at: Date(timeIntervalSince1970: 1_753_000_000)
    )

    if case .failed = result {
    } else {
        Issue.record("expected .failed, got \(result)")
    }
}

// MARK: - AutomationLaunchOptions

@Test
func startOnLaunchIsDetectedOnlyInRealArguments() {
    #expect(
        AutomationLaunchOptions.shouldStartOnLaunch(
            arguments: ["/Applications/App", "--start-on-launch"]
        )
    )
    #expect(
        !AutomationLaunchOptions.shouldStartOnLaunch(
            arguments: ["/Applications/App"]
        )
    )
    #expect(
        !AutomationLaunchOptions.shouldStartOnLaunch(
            arguments: ["--start-on-launch"]
        )
    )
    #expect(
        !AutomationLaunchOptions.shouldStartOnLaunch(arguments: [])
    )
}

// MARK: - Helpers

private func diagnosticsWindow(frame: CGRect) -> WindowCandidate {
    WindowCandidate(
        windowID: 42_055,
        processID: 27_040,
        bundleIdentifier: "com.nexon.devcat.mm",
        title: "마비노기 모바일",
        frame: frame,
        isOnScreen: true,
        processLifetimeIdentity: try? ProcessLifetimeIdentity(
            launchTimeIntervalSinceReferenceDate: 10
        )
    )
}

private func sampleDiagnosticsContent(
    statusDescription: String
) -> DiagnosticsSnapshot.Content {
    DiagnosticsSnapshot.Content(
        schemaVersion: 1,
        appVersion: "0.1.0",
        processID: 123,
        statusDescription: statusDescription,
        preflight: PreflightDiagnostics(
            result: .needsAttention(
                .unsupportedLayout(
                    measured: CGSize(width: 1_098, height: 949)
                )
            )
        ),
        lastActionDescription: "없음",
        lastActionAt: nil,
        observation: nil
    )
}

private func uniqueDiagnosticsDirectory() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent(
            "diagnostics-tests-\(UUID().uuidString)",
            isDirectory: true
        )
        .appendingPathComponent("nested", isDirectory: true)
}

private func removeDiagnosticsDirectory(_ directory: URL) {
    try? FileManager.default.removeItem(
        at: directory.deletingLastPathComponent()
    )
}

private func decodeDiagnosticsSnapshot(
    in directory: URL
) throws -> DiagnosticsSnapshot {
    let data = try Data(
        contentsOf: directory.appendingPathComponent(
            DiagnosticsFileWriter.fileName
        )
    )
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .iso8601
    return try decoder.decode(DiagnosticsSnapshot.self, from: data)
}
