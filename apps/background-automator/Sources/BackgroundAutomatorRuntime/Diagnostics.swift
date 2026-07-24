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
    public static let maximumTextCount = 24
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
            .prefix(Self.maximumTextCount)
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

        public init(
            schemaVersion: Int,
            appVersion: String,
            processID: Int32,
            statusDescription: String,
            preflight: PreflightDiagnostics?,
            lastActionDescription: String?,
            lastActionAt: Date?,
            observation: ObservationDiagnostics?
        ) {
            self.schemaVersion = schemaVersion
            self.appVersion = appVersion
            self.processID = processID
            self.statusDescription = statusDescription
            self.preflight = preflight
            self.lastActionDescription = lastActionDescription
            self.lastActionAt = lastActionAt
            self.observation = observation
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
