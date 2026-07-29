import BackgroundAutomatorCore
@preconcurrency import CoreGraphics
import Foundation

enum DiagnosticsRounding {
    static func round(_ value: Double, places: Int) -> Double {
        guard value.isFinite else {
            return -1
        }
        let factor = pow(10, Double(places))
        return (value * factor).rounded() / factor
    }
}

public struct DiagnosticsRect: Codable, Equatable, Sendable {
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double

    public init(_ rect: CGRect) {
        x = DiagnosticsRounding.round(rect.origin.x, places: 1)
        y = DiagnosticsRounding.round(rect.origin.y, places: 1)
        width = DiagnosticsRounding.round(rect.size.width, places: 1)
        height = DiagnosticsRounding.round(rect.size.height, places: 1)
    }
}

public struct DiagnosticsTextObservation: Codable, Equatable, Sendable {
    public let text: String
    public let confidence: Double
    public let box: DiagnosticsRect
}

public struct DiagnosticsActionCandidate: Codable, Equatable, Sendable {
    public let ruleID: String
    public let targetText: String?
    public let confidence: Double
    public let box: DiagnosticsRect
}

public struct DiagnosticsAppearance: Codable, Equatable, Sendable {
    public let contextMedianSaturation: Double
    public let contextMedianLuminance: Double
    public let contextSampleCount: Int
    public let targetMedianSaturation: Double
    public let targetMedianLuminance: Double
    public let targetSampleCount: Int
}

public struct ObservationDiagnostics: Codable, Equatable, Sendable {
    /// 한 항목의 글자 수 상한. 항목을 통째로 버리지 않고 길이만 줄이므로,
    /// 무엇이 화면에 있었는지는 그대로 남는다. 개수는 자르지 않는다 —
    /// 예전엔 24개에서 끊었는데, 남길 24개를 OCR이 돌려준 순서로 골라
    /// 화면 아래쪽 버튼이 통째로 빠졌다(2026-07-29: '다시 하기'가 후보로는
    /// 잡혔는데 진단 파일엔 없어 버튼을 못 읽은 것으로 오진했다).
    /// 항목 하나가 107바이트고 이 파일은 매 관찰마다 덮어써서, 아껴봐야
    /// 1.7KB다. 진단이 틀리는 값이 그보다 훨씬 비싸다.
    public static let maximumTextLength = 60

    public let imageWidth: Double?
    public let imageHeight: Double?
    public let layout: String
    public let recognizedTexts: [DiagnosticsTextObservation]
    public let actionCandidates: [DiagnosticsActionCandidate]
    public let appearanceEvidence: [String: DiagnosticsAppearance]

    public init(frame: AutomationScreenFrame) {
        imageWidth = frame.observation.imageSize.map {
            Double($0.width)
        }
        imageHeight = frame.observation.imageSize.map {
            Double($0.height)
        }
        layout = frame.layout.rawValue
        recognizedTexts = frame.observation.recognizedTexts
            .map { observed in
                DiagnosticsTextObservation(
                    text: String(
                        observed.text.prefix(Self.maximumTextLength)
                    ),
                    confidence: DiagnosticsRounding.round(
                        observed.confidence,
                        places: 3
                    ),
                    box: DiagnosticsRect(observed.boundingBox)
                )
            }
        actionCandidates = frame.observation.actionCandidates.map {
            DiagnosticsActionCandidate(
                ruleID: $0.ruleID,
                targetText: $0.targetText,
                confidence: DiagnosticsRounding.round(
                    $0.confidence,
                    places: 3
                ),
                box: DiagnosticsRect($0.boundingBox)
            )
        }
        appearanceEvidence = frame.observation.appearanceEvidence
            .mapValues { evidence in
                DiagnosticsAppearance(
                    contextMedianSaturation: DiagnosticsRounding.round(
                        evidence.contextStatistics.medianSaturation,
                        places: 3
                    ),
                    contextMedianLuminance: DiagnosticsRounding.round(
                        evidence.contextStatistics.medianLuminance,
                        places: 3
                    ),
                    contextSampleCount:
                        evidence.contextStatistics.sampleCount,
                    targetMedianSaturation: DiagnosticsRounding.round(
                        evidence.targetStatistics.medianSaturation,
                        places: 3
                    ),
                    targetMedianLuminance: DiagnosticsRounding.round(
                        evidence.targetStatistics.medianLuminance,
                        places: 3
                    ),
                    targetSampleCount:
                        evidence.targetStatistics.sampleCount
                )
            }
    }
}

public struct PreflightDiagnostics: Codable, Equatable, Sendable {
    public let outcome: String
    public let guidance: String?
    public let windowWidth: Double?
    public let windowHeight: Double?
    public let aspectRatio: Double?
    public let layout: String?

    public init(result: PreflightResult) {
        switch result {
        case let .ready(context):
            outcome = "ready"
            guidance = nil
            let size = context.window.frame.size
            windowWidth = DiagnosticsRounding.round(
                size.width,
                places: 1
            )
            windowHeight = DiagnosticsRounding.round(
                size.height,
                places: 1
            )
            aspectRatio = Self.aspectRatio(of: size)
            layout = context.layout.rawValue

        case let .needsAttention(issue):
            outcome = Self.outcomeName(for: issue)
            guidance = issue.koreanGuidance
            if case let .unsupportedLayout(measured) = issue {
                windowWidth = DiagnosticsRounding.round(
                    measured.width,
                    places: 1
                )
                windowHeight = DiagnosticsRounding.round(
                    measured.height,
                    places: 1
                )
                aspectRatio = Self.aspectRatio(of: measured)
            } else {
                windowWidth = nil
                windowHeight = nil
                aspectRatio = nil
            }
            layout = nil
        }
    }

    private static func aspectRatio(of size: CGSize) -> Double? {
        guard
            size.width.isFinite,
            size.height.isFinite,
            size.height > 0
        else {
            return nil
        }
        return DiagnosticsRounding.round(
            size.width / size.height,
            places: 4
        )
    }

    private static func outcomeName(
        for issue: PreflightIssue
    ) -> String {
        switch issue {
        case .targetNotConfigured:
            "targetNotConfigured"
        case .screenRecordingDenied:
            "screenRecordingDenied"
        case .accessibilityDenied:
            "accessibilityDenied"
        case .inputMonitoringUnavailable:
            "inputMonitoringUnavailable"
        case .targetNotRunning:
            "targetNotRunning"
        case .targetWindowUnavailable:
            "targetWindowUnavailable"
        case .ambiguousTargetWindows:
            "ambiguousTargetWindows"
        case .unsupportedLayout:
            "unsupportedLayout"
        }
    }
}

public struct DiagnosticsSnapshot: Codable, Equatable, Sendable {
    public struct Content: Codable, Equatable, Sendable {
        public let schemaVersion: Int
        public let appVersion: String
        public let processID: Int32
        public let statusDescription: String
        public let preflight: PreflightDiagnostics?
        public let lastActionDescription: String?
        public let lastActionAt: Date?
        public let observation: ObservationDiagnostics?
        /// 직전 바퀴가 클릭 없이 끝난 이유. 멈춘 앱을 밖에서 들여다볼 때
        /// '누를 게 없었다'와 '찾고도 못 눌렀다'를 가르는 유일한 단서다.
        public let noActionReason: NoActionReason?

        public init(
            schemaVersion: Int,
            appVersion: String,
            processID: Int32,
            statusDescription: String,
            preflight: PreflightDiagnostics?,
            lastActionDescription: String?,
            lastActionAt: Date?,
            observation: ObservationDiagnostics?,
            noActionReason: NoActionReason? = nil
        ) {
            self.schemaVersion = schemaVersion
            self.appVersion = appVersion
            self.processID = processID
            self.statusDescription = statusDescription
            self.preflight = preflight
            self.lastActionDescription = lastActionDescription
            self.lastActionAt = lastActionAt
            self.observation = observation
            self.noActionReason = noActionReason
        }
    }

    public let content: Content
    public let updatedAt: Date

    public init(content: Content, updatedAt: Date) {
        self.content = content
        self.updatedAt = updatedAt
    }
}

public enum DiagnosticsWriteResult: Equatable, Sendable {
    case written
    case skippedUnchanged
    case failed(String)
}

/// 자동화가 멈춘 순간의 화면을 따로 보존한다.
///
/// status.json은 매 프레임 덮어써지므로, 멈춘 화면이 곧바로 사라져 사후에
/// 원인을 확정할 수 없다(2026-07-25 21분 정지가 그랬다). 정지에 '진입할 때'
/// 한 줄씩 남겨, 나중에 어떤 화면에서 무슨 텍스트가 보였는지 되짚는다.
public final class StallSnapshotRecorder {
    public static let fileName = "stall-log.jsonl"

    private let directory: URL
    private let fileURL: URL
    private var wasStalled = false

    public init(directory: URL) {
        self.directory = directory
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    /// 멈춘 상태로 '바뀐' 순간에만 기록한다. 같은 화면에서 계속 멈춰 있으면
    /// 폴링마다 같은 내용이 쌓여 정작 필요한 기록을 덮으므로 건너뛴다.
    public func record(
        content: DiagnosticsSnapshot.Content,
        isStalled: Bool,
        at timestamp: Date = Date()
    ) {
        defer { wasStalled = isStalled }
        guard isStalled, !wasStalled else {
            return
        }

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        guard
            var line = try? encoder.encode(
                DiagnosticsSnapshot(
                    content: content,
                    updatedAt: timestamp
                )
            )
        else {
            return
        }
        line.append(0x0A) // '\n'

        // 진단 기록 실패가 자동화를 막아서는 안 되므로 조용히 넘어간다.
        do {
            try FileManager.default.createDirectory(
                at: directory,
                withIntermediateDirectories: true
            )
            if let handle = try? FileHandle(forWritingTo: fileURL) {
                defer { try? handle.close() }
                try handle.seekToEnd()
                try handle.write(contentsOf: line)
            } else {
                try line.write(to: fileURL, options: .atomic)
            }
        } catch {
            return
        }
    }
}

public final class DiagnosticsFileWriter {
    public static let fileName = "status.json"

    private let directory: URL
    private let fileURL: URL
    private var lastWrittenContent: DiagnosticsSnapshot.Content?

    public init(directory: URL) {
        self.directory = directory
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    @discardableResult
    public func write(
        content: DiagnosticsSnapshot.Content,
        at timestamp: Date = Date()
    ) -> DiagnosticsWriteResult {
        guard content != lastWrittenContent else {
            return .skippedUnchanged
        }

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [
            .prettyPrinted,
            .sortedKeys,
            .withoutEscapingSlashes,
        ]
        do {
            let data = try encoder.encode(
                DiagnosticsSnapshot(
                    content: content,
                    updatedAt: timestamp
                )
            )
            try FileManager.default.createDirectory(
                at: directory,
                withIntermediateDirectories: true
            )
            try data.write(to: fileURL, options: .atomic)
            lastWrittenContent = content
            return .written
        } catch {
            return .failed(String(describing: error))
        }
    }
}

public enum AutomationLaunchOptions {
    public static let startOnLaunchArgument = "--start-on-launch"

    public static func shouldStartOnLaunch(
        arguments: [String]
    ) -> Bool {
        arguments.dropFirst().contains(Self.startOnLaunchArgument)
    }
}
