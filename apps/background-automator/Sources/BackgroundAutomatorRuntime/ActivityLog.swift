import BackgroundAutomatorCore
@preconcurrency import CoreGraphics
import Foundation

/// 결과 화면 상단 중앙에서 던전 이름을 뽑아낸다.
///
/// 실측(마비노기 모바일 결과 화면): 던전 이름은 신뢰도 1.0으로 상단
/// 중앙 밴드에 찍히고, 난이도(신뢰도 낮음)·전투 시간·상태이상 설명과
/// 위치·신뢰도·키워드로 구분된다. 완벽한 파싱이 아니라 최선 추정이다.
public enum DungeonNameExtractor {
    static let minimumConfidence = 0.9
    static let bandMinY = 0.20
    static let bandMaxY = 0.33
    static let bandMinX = 0.30
    static let bandMaxX = 0.70

    /// 던전 이름이 아닌 설명/수치 텍스트를 거르는 키워드.
    static let excludedKeywords = [
        "시간", "오염", "침식", "효과", "보상", "감소", "내구도",
        "은동전", "떨어졌", "싸우", "쉬워", "얻습니다", "점",
        "등급", "전리품", "포인트", "증표", "경험치", "아이템",
        "상세", "클리어", "터치",
    ]

    public static func extract(
        from texts: [RecognizedTextObservation],
        imageSize: CGSize
    ) -> String? {
        guard
            imageSize.width.isFinite,
            imageSize.height.isFinite,
            imageSize.width > 0,
            imageSize.height > 0
        else {
            return nil
        }

        let candidates = texts.filter { observation in
            guard observation.confidence >= minimumConfidence else {
                return false
            }
            let box = observation.boundingBox
            guard box.width > 0, box.height > 0 else {
                return false
            }
            let nx = box.midX / imageSize.width
            let ny = box.midY / imageSize.height
            guard
                (bandMinX ... bandMaxX).contains(nx),
                (bandMinY ... bandMaxY).contains(ny)
            else {
                return false
            }
            return !excludedKeywords.contains { keyword in
                observation.text.contains(keyword)
            }
        }

        // 밴드 안에서 가장 위(작은 y)에 있는 텍스트를 던전 이름으로.
        return candidates
            .min { $0.boundingBox.midY < $1.boundingBox.midY }?
            .text
    }
}

public struct ActivityEvent: Codable, Equatable, Sendable {
    public let at: Date
    public let outcome: String
    public let scene: String?
    public let dungeonName: String?

    public init(
        at: Date,
        outcome: String,
        scene: String?,
        dungeonName: String?
    ) {
        self.at = at
        self.outcome = outcome
        self.scene = scene
        self.dungeonName = dungeonName
    }
}

public struct ActivitySummary: Codable, Equatable, Sendable {
    public let totalClicks: Int
    public let dungeonRuns: Int
    public let byDungeon: [String: Int]

    public init(
        totalClicks: Int,
        dungeonRuns: Int,
        byDungeon: [String: Int]
    ) {
        self.totalClicks = totalClicks
        self.dungeonRuns = dungeonRuns
        self.byDungeon = byDungeon
    }
}

public final class ActivityLogWriter {
    public static let fileName = "activity-log.jsonl"

    /// clear_touch 클릭 = 던전 1판 완료로 집계한다.
    public static let dungeonRunScene = "clear_touch"

    private let directory: URL
    private let fileURL: URL

    public init(directory: URL) {
        self.directory = directory
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    public func append(_ event: ActivityEvent) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.withoutEscapingSlashes]
        var line = try encoder.encode(event)
        line.append(0x0A) // '\n'

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
    }

    public func summary() throws -> ActivitySummary {
        guard
            let data = try? Data(contentsOf: fileURL),
            !data.isEmpty
        else {
            return ActivitySummary(
                totalClicks: 0,
                dungeonRuns: 0,
                byDungeon: [:]
            )
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        var totalClicks = 0
        var dungeonRuns = 0
        var byDungeon: [String: Int] = [:]

        for line in data.split(separator: 0x0A) {
            guard
                let event = try? decoder.decode(
                    ActivityEvent.self,
                    from: Data(line)
                )
            else {
                continue
            }
            totalClicks += 1
            if event.scene == Self.dungeonRunScene {
                dungeonRuns += 1
                if let name = event.dungeonName {
                    byDungeon[name, default: 0] += 1
                }
            }
        }

        return ActivitySummary(
            totalClicks: totalClicks,
            dungeonRuns: dungeonRuns,
            byDungeon: byDungeon
        )
    }
}
