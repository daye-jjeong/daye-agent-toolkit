@preconcurrency import CoreGraphics
import Foundation

/// 이 판에 던전을 어떻게 들어갔나.
///
/// 재화를 쓰고 들어간 판인지가 기록에 없어, 드랍률을 비교하려면 전리품 칸
/// 수로 짐작해야 했다(실측: 재화를 쓰면 3칸 → 24칸). 짐작은 기록이 아니다.
public enum DungeonEntry: String, Codable, Equatable, Sendable {
    /// 은동전을 쓰고 임무를 받았다.
    case coin
    /// 공물을 쓰고 임무를 받았다.
    case tribute
    /// 임무를 해제하고 들어갔다 — 재화를 쓰지 않는다.
    case free

    /// 입장 버튼을 누른 규칙에서 유도한다. 입장 규칙이 아니면 nil이라,
    /// 컷신 넘기기 같은 다른 클릭이 기록을 덮어쓰지 않는다.
    public init?(ruleID: String) {
        switch ruleID {
        case "enter_with_coin":
            self = .coin
        case "enter_with_tribute":
            self = .tribute
        case "enter_ready":
            self = .free
        default:
            return nil
        }
    }
}

/// 던전 1판(사이클)의 결과 기록.
public struct CycleRecord: Codable, Equatable, Sendable {
    public let at: Date
    public let dungeon: String?
    public let combatSeconds: Int?
    /// 이번 사이클에 등장한 아이템 이름. 지금은 '나왔나'(등장 여부)만
    /// 담는다 — 정확한 개수는 이름↔수량 페어링과 수량 생략 규칙이
    /// 확정돼야 해서 별도 과제다.
    public let items: [String]
    /// 이 판을 남긴 빌드. 채우는 쪽은 writer라 호출부는 건드리지 않는다.
    /// 스탬프를 찍기 전에 쌓인 기록에는 없으므로 옵셔널이다.
    public let build: String?
    /// 어떻게 들어갔나. 앱이 입장 버튼을 누르지 않은 판(사용자가 직접 들어간
    /// 경우)은 알 수 없으므로 옵셔널이다 — 모르는 것을 free로 적지 않는다.
    public let entry: DungeonEntry?

    public init(
        at: Date,
        dungeon: String?,
        combatSeconds: Int?,
        items: [String],
        build: String? = nil,
        entry: DungeonEntry? = nil
    ) {
        self.at = at
        self.dungeon = dungeon
        self.combatSeconds = combatSeconds
        self.items = items
        self.build = build
        self.entry = entry
    }

    public func entered(_ entry: DungeonEntry?) -> CycleRecord {
        CycleRecord(
            at: at,
            dungeon: dungeon,
            combatSeconds: combatSeconds,
            items: items,
            build: build,
            entry: entry
        )
    }

    func stamped(_ build: String?) -> CycleRecord {
        guard let build else {
            return self
        }
        return CycleRecord(
            at: at,
            dungeon: dungeon,
            combatSeconds: combatSeconds,
            items: items,
            build: build,
            entry: entry
        )
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

    /// 결과 화면을 덮는 확인 다이얼로그. 이 글자가 보이는 프레임은 전리품을
    /// 모으지 않는다 — 다이얼로그 문구가 수집 구간 한가운데에 떨어져
    /// 전리품으로 쌓였다(실측: 페카 38판 중 33판). 가려진 화면은 믿지 않고,
    /// 전리품은 이미 앞 프레임에서 모였다.
    static let overlayMarkers = ["던전 탐험을 계속하시겠습니까?"]

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
        // 던전 이름·전투 시간은 다이얼로그가 덮지 않는 위쪽에 있어 계속 읽는다.
        if !Self.isCoveredByOverlay(texts) {
            for name in Self.itemNames(in: texts, imageSize: imageSize)
                where cycle.seenItems.insert(name).inserted
            {
                cycle.items.append(name)
            }
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

    /// 수량 뱃지에 숫자와 함께 붙는 단위·구분 기호.
    private static let quantityUnits: Set<Character> = [
        "만", "천", "억", ",", ".", "+", "%",
    ]

    /// 수량 뱃지인지. 아이콘 위에 얹힌 '255.3만'·'1,382' 같은 숫자다.
    ///
    /// 한글 필터만으로는 못 거른다 — 단위 '만'·'천'·'억'이 한글이라
    /// '255.3만'이 그대로 전리품 이름으로 쌓였다(실측 로그). 숫자와 단위
    /// 말고 다른 글자가 하나라도 있으면 진짜 이름으로 본다('만병통치약').
    static func isQuantityBadge(_ text: String) -> Bool {
        let stripped = text.filter { !$0.isWhitespace }
        // 숫자가 없으면 뱃지가 아니다. 빈 문자열도 여기서 함께 걸린다.
        guard stripped.contains(where: \.isNumber) else {
            return false
        }
        return stripped.allSatisfy {
            $0.isNumber || quantityUnits.contains($0)
        }
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
                && name.contains(where: \.isHangul)
                && !isQuantityBadge(name)
        }
        // 이어 붙인 뒤에 거른다. 결과 화면이 떠오르는 동안 헤더가 수집 구간을
        // 지나가면 '페카 고분 심층 1층 2구역' + '• 순수 전투 시간 0:26'이 한
        // 이름으로 붙는데(실측 3판), 던전 이름 쪽만 보면 전리품과 구분이 안 된다.
        return joinStackedLabels(labels).filter {
            !$0.contains(markerText)
        }
    }

    static func isCoveredByOverlay(
        _ texts: [RecognizedTextObservation]
    ) -> Bool {
        texts.contains { observation in
            overlayMarkers.contains { observation.text.contains($0) }
        }
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
        // 윗줄에 붙여 쓴 라벨. 자기 이름으로 다시 나오면 안 된다.
        var joined = Set<Int>()
        var names: [String] = []
        for index in sorted.indices where !joined.contains(index) {
            let top = sorted[index]
            var name = top.text.trimmingCharacters(in: .whitespaces)
            for next in (index + 1) ..< sorted.count
                where !joined.contains(next)
            {
                let below = sorted[next]
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
                joined.insert(next)
                break
            }
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
    /// 오늘 실제로 돌린 시간(초). 판 수만으로는 얼마나 붙잡고 있었는지
    /// 알 수 없고, '가동 시간'은 이번에 시작한 뒤부터라 중간에 멈췄다
    /// 다시 켜면 0으로 돌아간다. 자리를 비운 공백은 빼고 센다.
    public let todayActiveSeconds: Int
    public let byDungeon: [String: Int]

    public init(
        totalCycles: Int,
        todayCycles: Int = 0,
        todayActiveSeconds: Int = 0,
        byDungeon: [String: Int]
    ) {
        self.totalCycles = totalCycles
        self.todayCycles = todayCycles
        self.todayActiveSeconds = todayActiveSeconds
        self.byDungeon = byDungeon
    }

    /// "2시간 15분" 꼴. 오늘 한 판도 안 돌았으면 nil.
    public var todayActiveDescription: String? {
        guard todayActiveSeconds > 0 else {
            return nil
        }
        let minutes = todayActiveSeconds / 60
        guard minutes >= 60 else {
            return "\(minutes)분"
        }
        return "\(minutes / 60)시간 \(minutes % 60)분"
    }
}

/// 사이클 기록을 JSONL로 남긴다. 클릭 단위인 activity-log와 달리 던전
/// 1판당 한 줄이라, 나중에 던전별 소요 시간·드랍 분석에 그대로 쓴다.
public final class CycleLogWriter {
    public static let fileName = "cycle-log.jsonl"

    private let directory: URL
    private let fileURL: URL
    private let build: String?

    public init(directory: URL, build: String? = nil) {
        self.directory = directory
        self.build = build
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    public func append(_ record: CycleRecord) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.withoutEscapingSlashes]
        try JSONLinesFile.append(
            encoder.encode(record.stamped(build)),
            to: fileURL,
            in: directory
        )
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
        var todayActiveSeconds = 0.0
        var previousToday: Date?
        var byDungeon: [String: Int] = [:]
        // 띄어쓰기를 지운 이름 → 처음 읽은 표기. OCR이 같은 던전을 '페카 고분
        // 심층 1층 2구역'과 '페카고분 심층 1층 2구역'으로 갈라 읽어 통계가
        // 쪼개졌다(실측 8판 + 27판). 세는 기준만 띄어쓰기를 무시하고, 보여줄
        // 이름은 처음 읽은 쪽을 쓴다 — 붙여 쓴 표기가 이기면 읽기 나쁘다.
        var displayNames: [String: String] = [:]

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
                if let previous = previousToday,
                   case let gap = record.at.timeIntervalSince(previous),
                   gap > 0,
                   gap <= Self.maximumCycleGapSeconds
                {
                    todayActiveSeconds += gap
                }
                previousToday = record.at
            }
            if let dungeon = record.dungeon {
                let key = dungeon.filter { !$0.isWhitespace }
                let name = displayNames[key] ?? dungeon
                displayNames[key] = name
                byDungeon[name, default: 0] += 1
            }
        }

        return CycleSummary(
            totalCycles: totalCycles,
            todayCycles: todayCycles,
            todayActiveSeconds: Int(todayActiveSeconds),
            byDungeon: byDungeon
        )
    }

    /// 이보다 벌어진 간격은 자리를 비운 것으로 본다. 정상 판당 소요는
    /// 105~130초고 멈춤 감지 기준이 150초라, 5분이면 정상 파밍은 한 번도
    /// 끊기지 않으면서 휴식은 확실히 걸러진다.
    static let maximumCycleGapSeconds: TimeInterval = 300
}
