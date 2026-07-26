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

    /// 아이템 그리드가 놓이는 세로 구간(실측 0.55~0.78). 위로는 던전 이름·
    /// 전투 시간 같은 메타 텍스트를, 아래로는 버튼과 안내문(y≥0.82: 나가기·
    /// 다시 하기·'은동전이 부족해요.')을 잘라낸다. 상한이 없으면 그 UI가
    /// 전리품 이름으로 섞여 드랍률 집계가 오염된다.
    static let itemMinimumY = 0.5
    static let itemMaximumY = 0.80

    /// 결과 화면이 떠 있는 동안 모으는 중간 상태.
    private struct PendingCycle {
        var appearedAt: Date
        var dungeon: String?
        var combatSeconds: Int?
        var items: [String]
        var seenItems: Set<String>
    }

    private var pending: PendingCycle?

    public init() {}

    /// 한 프레임을 관찰한다. 결과 화면이 떠 있는 동안은 아이템을 모으기만
    /// 하고(nil), 화면이 닫히는 순간 한 판을 기록해 돌려준다.
    ///
    /// 처음 뜬 프레임만 보고 기록하면 은동전 쓴 런의 장비 드랍을 놓친다 —
    /// 그 화면은 전리품 한 칸이 '?'로 가려져 있고 '발견한 전리품'을 눌러야
    /// 드러나기 때문이다.
    public mutating func observe(
        texts: [RecognizedTextObservation],
        imageSize: CGSize,
        at now: Date = Date()
    ) -> CycleRecord? {
        let marker = texts.first {
            $0.text.contains(Self.markerText)
        }
        guard let marker else {
            defer { pending = nil }
            return pending.map {
                CycleRecord(
                    at: $0.appearedAt,
                    dungeon: $0.dungeon,
                    combatSeconds: $0.combatSeconds,
                    items: $0.items
                )
            }
        }

        var cycle = pending ?? PendingCycle(
            appearedAt: now,
            dungeon: nil,
            combatSeconds: nil,
            items: [],
            seenItems: []
        )
        // 던전 이름·전투 시간은 연출 때문에 프레임마다 흔들린다.
        // 한 번 제대로 읽은 값을 유지한다.
        cycle.dungeon = cycle.dungeon ?? DungeonNameExtractor.extract(
            from: texts,
            imageSize: imageSize
        )
        cycle.combatSeconds = cycle.combatSeconds
            ?? Self.combatSeconds(in: marker.text)
        for name in Self.itemNames(in: texts, imageSize: imageSize)
            where cycle.seenItems.insert(name).inserted
        {
            cycle.items.append(name)
        }
        pending = cycle
        return nil
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

    /// 수량 뱃지인지. 아이콘 위에 얹힌 '255.3만'·'1,382' 같은 숫자다.
    ///
    /// 한글 필터만으로는 못 거른다 — 단위 '만'·'천'·'억'이 한글이라
    /// '255.3만'이 그대로 전리품 이름으로 쌓였다(실측 로그). 숫자와 단위
    /// 말고 다른 글자가 하나라도 있으면 진짜 이름으로 본다('만병통치약').
    static func isQuantityBadge(_ text: String) -> Bool {
        let stripped = text.filter { !$0.isWhitespace }
        guard !stripped.isEmpty, stripped.contains(where: \.isNumber) else {
            return false
        }
        let units: Set<Character> = ["만", "천", "억", ",", ".", "+", "%"]
        return stripped.allSatisfy { $0.isNumber || units.contains($0) }
    }

    static func itemNames(
        in texts: [RecognizedTextObservation],
        imageSize: CGSize
    ) -> [String] {
        guard imageSize.height > 0 else {
            return []
        }
        let labels = texts.filter { observation in
            let name = observation.text.trimmingCharacters(in: .whitespaces)
            let y = observation.boundingBox.midY / imageSize.height
            return (itemMinimumY ... itemMaximumY).contains(y)
                && !name.isEmpty
                // 전리품 이름은 한글이다. 'BO'·'BP' 같은 아이콘 오독을 건다.
                && name.contains(where: { $0.isHangul })
                && !isQuantityBadge(name)
        }
        return joinStackedLabels(labels)
    }

    /// 아이콘 하나 밑에 이름이 두 줄로 쌓이면 OCR이 따로 준다
    /// ('세공된 블루' / '스피넬Z'). 같은 칸(가로로 겹침)에서 바로 아래
    /// 줄이면 한 이름으로 잇는다. 좌표를 상수로 박지 않고 글자 높이로
    /// 재므로 창 크기가 달라도 같은 기준이 선다.
    static func joinStackedLabels(
        _ labels: [RecognizedTextObservation]
    ) -> [String] {
        let sorted = labels.sorted {
            $0.boundingBox.midY < $1.boundingBox.midY
        }
        var used = Set<Int>()
        var names: [String] = []
        for (index, top) in sorted.enumerated() where !used.contains(index) {
            var name = top.text.trimmingCharacters(in: .whitespaces)
            for (other, below) in sorted.enumerated()
                where other > index && !used.contains(other)
            {
                let gap = below.boundingBox.midY - top.boundingBox.midY
                // 다음 줄은 글자 높이의 두 배 안쪽이다. 다음 아이템 행은
                // 그보다 훨씬 멀다(실측 8배).
                guard gap <= top.boundingBox.height * 2 else {
                    break
                }
                guard horizontallyOverlap(top, below) else {
                    continue
                }
                name += " " + below.text.trimmingCharacters(in: .whitespaces)
                used.insert(other)
                break
            }
            used.insert(index)
            names.append(name)
        }
        return names
    }

    private static func horizontallyOverlap(
        _ lhs: RecognizedTextObservation,
        _ rhs: RecognizedTextObservation
    ) -> Bool {
        let a = lhs.boundingBox
        let b = rhs.boundingBox
        let overlap = min(a.maxX, b.maxX) - max(a.minX, b.minX)
        let narrower = min(a.width, b.width)
        guard narrower > 0 else {
            return false
        }
        return overlap / narrower >= 0.5
    }
}

extension Character {
    /// 한글 음절·자모인지. 전리품 이름을 아이콘 오독과 구분하는 데 쓴다.
    var isHangul: Bool {
        unicodeScalars.contains {
            (0xAC00 ... 0xD7A3).contains($0.value) // 가–힣
                || (0x1100 ... 0x11FF).contains($0.value) // 자모
                || (0x3130 ... 0x318F).contains($0.value) // 호환 자모
        }
    }
}

public struct CycleSummary: Codable, Equatable, Sendable {
    public let totalCycles: Int
    /// 오늘(로컬 달력 기준) 돈 판. 누적만 보면 오늘 얼마나 돌았는지
    /// 알 수 없고, 파밍은 자정을 넘겨 이어지므로 날짜로 끊는다.
    public let todayCycles: Int
    public let byDungeon: [String: Int]

    public init(
        totalCycles: Int,
        todayCycles: Int = 0,
        byDungeon: [String: Int]
    ) {
        self.totalCycles = totalCycles
        self.todayCycles = todayCycles
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

    public func summary(
        now: Date = Date(),
        calendar: Calendar = .current
    ) throws -> CycleSummary {
        guard
            let data = try? Data(contentsOf: fileURL),
            !data.isEmpty
        else {
            return CycleSummary(totalCycles: 0, byDungeon: [:])
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let startOfToday = calendar.startOfDay(for: now)
        var totalCycles = 0
        var todayCycles = 0
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
            if record.at >= startOfToday {
                todayCycles += 1
            }
            if let dungeon = record.dungeon {
                byDungeon[dungeon, default: 0] += 1
            }
        }

        return CycleSummary(
            totalCycles: totalCycles,
            todayCycles: todayCycles,
            byDungeon: byDungeon
        )
    }
}
