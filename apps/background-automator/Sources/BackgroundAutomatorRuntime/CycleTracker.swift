@preconcurrency import CoreGraphics
import Foundation

/// 던전 1판(사이클)의 결과 기록.
public struct CycleRecord: Codable, Equatable, Sendable {
    public let at: Date
    public let dungeon: String?
    public let combatSeconds: Int?
    /// 이번 사이클에 등장한 아이템 이름. 지금은 '나왔나'(등장 여부)만
    /// 담는다 — 정확한 개수는 이름↔수량 페어링과 수량 생략 규칙이
    /// 확정돼야 해서 별도 과제다.
    public let items: [String]

    public init(
        at: Date,
        dungeon: String?,
        combatSeconds: Int?,
        items: [String]
    ) {
        self.at = at
        self.dungeon = dungeon
        self.combatSeconds = combatSeconds
        self.items = items
    }
}

/// 결과 화면의 등장(엣지)으로 사이클을 센다.
///
/// 클릭이 아니라 화면을 기준으로 세기 때문에, 사용자가 중간에 직접 버튼을
/// 눌러 넘긴 사이클도 빠지지 않는다. 마커는 '순수 전투 시간'(실측 cf 1.0)
/// 으로, 은동전 사용 여부와 무관하게 모든 클리어 결과 화면에 뜬다.
public struct CycleTracker: Sendable {
    /// 결과 화면 시그니처. OCR이 앞에 글머리표를 '•'·'C' 등으로 흘려
    /// 읽으므로 포함 검사로 매칭한다.
    static let markerText = "순수 전투 시간"

    /// 아이템 그리드는 결과 화면 아래쪽에 있다(실측 y≥0.5). 던전 이름·
    /// 전투 시간·난이도 같은 상단 메타 텍스트를 아이템으로 오인하지 않는다.
    static let itemMinimumY = 0.5

    private var markerVisible = false

    public init() {}

    /// 한 프레임을 관찰한다. 마커가 '안 보임 → 보임'으로 바뀐 순간에만
    /// 사이클 기록을 돌려준다(같은 화면이 이어지는 동안은 nil).
    public mutating func observe(
        texts: [RecognizedTextObservation],
        imageSize: CGSize,
        at now: Date = Date()
    ) -> CycleRecord? {
        let marker = texts.first {
            $0.text.contains(Self.markerText)
        }
        guard let marker else {
            markerVisible = false
            return nil
        }
        guard !markerVisible else {
            return nil
        }
        markerVisible = true

        return CycleRecord(
            at: now,
            dungeon: DungeonNameExtractor.extract(
                from: texts,
                imageSize: imageSize
            ),
            combatSeconds: Self.combatSeconds(in: marker.text),
            items: Self.itemNames(in: texts, imageSize: imageSize)
        )
    }

    /// '순수 전투 시간 M:SS' → 초. 앞의 글머리표는 무시한다.
    static func combatSeconds(in text: String) -> Int? {
        guard let range = text.range(of: markerText) else {
            return nil
        }
        let tail = text[range.upperBound...]
        let parts = tail
            .split(separator: ":")
            .map { $0.trimmingCharacters(in: .whitespaces) }
        guard
            parts.count == 2,
            let minutes = Int(parts[0]),
            let seconds = Int(parts[1]),
            minutes >= 0,
            (0 ..< 60).contains(seconds)
        else {
            return nil
        }
        return minutes * 60 + seconds
    }

    static func itemNames(
        in texts: [RecognizedTextObservation],
        imageSize: CGSize
    ) -> [String] {
        guard imageSize.height > 0 else {
            return []
        }
        return texts.compactMap { observation in
            let name = observation.text.trimmingCharacters(in: .whitespaces)
            guard
                observation.boundingBox.midY / imageSize.height
                    >= itemMinimumY,
                !name.isEmpty,
                // 수량 뱃지(숫자만)는 이름이 아니다.
                name.contains(where: { $0.isLetter })
            else {
                return nil
            }
            return name
        }
    }
}

public struct CycleSummary: Codable, Equatable, Sendable {
    public let totalCycles: Int
    public let byDungeon: [String: Int]

    public init(totalCycles: Int, byDungeon: [String: Int]) {
        self.totalCycles = totalCycles
        self.byDungeon = byDungeon
    }
}

/// 사이클 기록을 JSONL로 남긴다. 클릭 단위인 activity-log와 달리 던전
/// 1판당 한 줄이라, 나중에 던전별 소요 시간·드랍 분석에 그대로 쓴다.
public final class CycleLogWriter {
    public static let fileName = "cycle-log.jsonl"

    private let directory: URL
    private let fileURL: URL

    public init(directory: URL) {
        self.directory = directory
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    public func append(_ record: CycleRecord) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.withoutEscapingSlashes]
        var line = try encoder.encode(record)
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

    public func summary() throws -> CycleSummary {
        guard
            let data = try? Data(contentsOf: fileURL),
            !data.isEmpty
        else {
            return CycleSummary(totalCycles: 0, byDungeon: [:])
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        var totalCycles = 0
        var byDungeon: [String: Int] = [:]

        for line in data.split(separator: 0x0A) {
            guard
                let record = try? decoder.decode(
                    CycleRecord.self,
                    from: Data(line)
                )
            else {
                continue
            }
            totalCycles += 1
            if let dungeon = record.dungeon {
                byDungeon[dungeon, default: 0] += 1
            }
        }

        return CycleSummary(
            totalCycles: totalCycles,
            byDungeon: byDungeon
        )
    }
}
