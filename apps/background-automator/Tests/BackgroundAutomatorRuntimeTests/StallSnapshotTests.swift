import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

private func stallDirectory(_ label: String) -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent("stall-\(label)-\(UUID().uuidString)")
}

private func snapshotContent(
    status: String,
    texts: [String] = ["다시 하기"]
) -> DiagnosticsSnapshot.Content {
    let frame = AutomationScreenFrame(
        observation: SceneObservation(
            imageSize: CGSize(width: 1_512, height: 949),
            recognizedTexts: texts.map {
                RecognizedTextObservation(
                    text: $0,
                    confidence: 1.0,
                    boundingBox: CGRect(
                        x: 700,
                        y: 860,
                        width: 100,
                        height: 28
                    )
                )
            },
            actionCandidates: []
        ),
        window: WindowCandidate(
            windowID: 42_055,
            processID: 27_040,
            bundleIdentifier: "com.nexon.devcat.mm",
            title: "마비노기 모바일",
            frame: CGRect(x: 0, y: 0, width: 1_512, height: 949),
            isOnScreen: true,
            processLifetimeIdentity: try? ProcessLifetimeIdentity(
                launchTimeIntervalSinceReferenceDate: 10
            )
        ),
        layout: .landscape
    )
    return DiagnosticsSnapshot.Content(
        schemaVersion: 1,
        appVersion: "0.1.0",
        processID: 123,
        statusDescription: status,
        preflight: nil,
        lastActionDescription: "버튼 클릭 완료",
        lastActionAt: Date(timeIntervalSince1970: 1_800_000_000),
        observation: ObservationDiagnostics(frame: frame)
    )
}

@Test
func onlyBlockedStatusesCountAsStalled() {
    // 진행이 막힌 상태(사람이 봐야 풀리는 상태)만 정지로 본다.
    // 전투 대기·쿨다운처럼 곧 스스로 풀리는 상태는 정지가 아니다.
    #expect(AutomationMenuStatus.needsAttention("모호").isStalled)
    #expect(AutomationMenuStatus.pausedRestorationFailure.isStalled)

    #expect(!AutomationMenuStatus.observing.isStalled)
    #expect(!AutomationMenuStatus.combatWait.isStalled)
    #expect(!AutomationMenuStatus.cooldown.isStalled)
    #expect(!AutomationMenuStatus.clicking.isStalled)
    #expect(!AutomationMenuStatus.waitingForUserIdle.isStalled)
    #expect(!AutomationMenuStatus.buttonDetected.isStalled)
    #expect(!AutomationMenuStatus.stopped.isStalled)
    #expect(!AutomationMenuStatus.stopping.isStalled)
    #expect(!AutomationMenuStatus.checkingPreflight.isStalled)
}

@Test
func stallSnapshotIsKeptWhenAutomationStopsProgressing() throws {
    // status.json은 매 프레임 덮어써져서, 자동화가 멈춘 순간의 화면이
    // 곧바로 사라진다(2026-07-25 21분 정지의 원인을 사후에 확정하지 못한
    // 이유). 멈춘 시점의 스냅샷은 따로 보존해야 진단할 수 있다.
    let directory = stallDirectory("keep")
    defer { try? FileManager.default.removeItem(at: directory) }
    let recorder = StallSnapshotRecorder(directory: directory)

    recorder.record(
        content: snapshotContent(status: "확인 필요: 화면 후보가 모호합니다"),
        isStalled: true,
        at: Date(timeIntervalSince1970: 1_800_000_000)
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            StallSnapshotRecorder.fileName
        ),
        encoding: .utf8
    )
    #expect(text.contains("화면 후보가 모호합니다"))
    #expect(text.contains("다시 하기"))
    #expect(text.split(separator: "\n").count == 1)
}

@Test
func healthyStatusIsNotRecorded() throws {
    // 정상 동작 중 스냅샷까지 남기면 파일이 금세 커져 정작 필요한 정지
    // 기록을 덮어버린다.
    let directory = stallDirectory("healthy")
    defer { try? FileManager.default.removeItem(at: directory) }
    let recorder = StallSnapshotRecorder(directory: directory)

    recorder.record(
        content: snapshotContent(status: "화면 확인 중"),
        isStalled: false,
        at: Date(timeIntervalSince1970: 1_800_000_000)
    )

    #expect(
        !FileManager.default.fileExists(
            atPath: directory
                .appendingPathComponent(StallSnapshotRecorder.fileName)
                .path
        )
    )
}

@Test
func repeatedStallDoesNotFloodTheFile() throws {
    // 같은 화면에서 멈춰 있으면 폴링마다 같은 스냅샷이 쏟아진다.
    // 상태가 바뀔 때만(정지 진입 시) 한 줄 남긴다.
    let directory = stallDirectory("flood")
    defer { try? FileManager.default.removeItem(at: directory) }
    let recorder = StallSnapshotRecorder(directory: directory)
    let stalled = snapshotContent(status: "확인 필요: 화면 후보가 모호합니다")

    for _ in 0 ..< 5 {
        recorder.record(
            content: stalled,
            isStalled: true,
            at: Date(timeIntervalSince1970: 1_800_000_000)
        )
    }

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            StallSnapshotRecorder.fileName
        ),
        encoding: .utf8
    )
    #expect(text.split(separator: "\n").count == 1)
}

@Test
func recoveryThenNewStallRecordsSecondEntry() throws {
    // 정상으로 돌아왔다가 다시 멈추면 별개의 사건이므로 새로 남긴다.
    let directory = stallDirectory("again")
    defer { try? FileManager.default.removeItem(at: directory) }
    let recorder = StallSnapshotRecorder(directory: directory)
    let at = Date(timeIntervalSince1970: 1_800_000_000)

    recorder.record(
        content: snapshotContent(status: "확인 필요: 화면 후보가 모호합니다"),
        isStalled: true,
        at: at
    )
    recorder.record(
        content: snapshotContent(status: "화면 확인 중"),
        isStalled: false,
        at: at
    )
    recorder.record(
        content: snapshotContent(status: "확인 필요: 지원하지 않는 화면 비율"),
        isStalled: true,
        at: at
    )

    let text = try String(
        contentsOf: directory.appendingPathComponent(
            StallSnapshotRecorder.fileName
        ),
        encoding: .utf8
    )
    #expect(text.split(separator: "\n").count == 2)
    #expect(text.contains("지원하지 않는 화면 비율"))
}
