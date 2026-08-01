import BackgroundAutomatorCore
@preconcurrency import CoreGraphics
import Foundation

/// 결과 화면 상단 중앙에서 던전 이름을 뽑아낸다.
///
/// 실측(마비노기 모바일 결과 화면): 던전 이름은 신뢰도 1.0으로 상단
/// 중앙 밴드에 찍히고, 난이도(신뢰도 낮음)·전투 시간·상태이상 설명과
/// 위치·신뢰도·키워드로 구분된다. 완벽한 파싱이 아니라 최선 추정이다.
public enum DungeonNameExtractor {
    /// 실측(2026-07-25): 같은 던전 이름이 은동전 쓴 런에서는 연출 오버레이
    /// 탓에 conf 0.50까지 떨어진다(안 쓴 런은 1.0). 0.9로 거르면 코인런의
    /// 이름을 통째로 잃어 던전별 집계가 빈다. 장식 폰트 수준까지 낮추고,
    /// 완화로 밴드에 들어오는 난이도 라벨은 difficultyLabels로 막는다.
    static let minimumConfidence = 0.45
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

    /// 난이도 라벨은 던전 이름 바로 위(더 작은 y)에 뜨므로 '가장 위' 규칙
    /// 아래서 이름을 밀어낸다. 유한 집합이라 정확히 일치할 때만 배제한다
    /// (부분 일치로 막으면 이름에 같은 글자가 든 던전까지 걸린다).
    static let difficultyLabels: Set<String> = [
        "쉬움", "보통", "어려움", "매우어려움", "노말", "하드",
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
            guard !difficultyLabels.contains(
                normalizedLabel(observation.text)
            ) else {
                return false
            }
            return !excludedKeywords.contains { keyword in
                observation.text.contains(keyword)
            }
        }

        // 밴드 안에서 가장 위(작은 y)에 있는 텍스트를 던전 이름으로.
        return candidates
            .min { $0.boundingBox.midY < $1.boundingBox.midY }
            .map { normalizedName($0.text) }
    }

    /// OCR은 같은 던전을 매번 조금씩 다르게 읽는다 — 실측 로그에
    /// '룬다 1층 2구역'·'룬다. 1층 2구역'·"룬다 '1층 2구역*"이 따로
    /// 쌓여 같은 던전 통계가 셋으로 쪼개졌다. 글자·숫자만 남겨 모은다.
    static func normalizedName(_ text: String) -> String {
        String(text.map { $0.isLetter || $0.isNumber ? $0 : " " })
            .split(separator: " ")
            .joined(separator: " ")
    }

    /// OCR이 라벨에 붙이는 공백·괄호 같은 잡음을 떼고 글자만 남긴다
    /// ('어려움]' → '어려움', '매우 어려움' → '매우어려움').
    private static func normalizedLabel(_ text: String) -> String {
        String(text.filter { $0.isLetter })
    }
}

/// 클릭 한 번에 든 시간을 구간별로 쪼갠 값.
///
/// 실측(2026-07-25, 137판): 한 판 104초 중 89초는 게임이 쓰는 시간이고
/// 앱이 쓰는 시간은 16초다. 그 16초가 어느 구간에 몰려 있는지 알아야
/// 무엇을 줄일지 정할 수 있다.
public struct ClickPhaseTimings: Codable, Equatable, Sendable {
    /// 화면을 잡아 글자를 읽기까지.
    public let observeMilliseconds: Int
    /// 그중 창을 잡는 데만 든 시간. 나머지가 글자 인식이다.
    ///
    /// 옵셔널인 이유는 이 값이 없는 과거 기록이 남아 있어서다.
    public let captureMilliseconds: Int?
    /// 사용자가 손을 뗄 때까지 기다린 시간.
    public let idleWaitMilliseconds: Int
    /// 누르기 직전 화면을 다시 확인하는 데 든 시간.
    public let reobserveMilliseconds: Int
    /// 그중 창을 잡는 데만 든 시간.
    public let reobserveCaptureMilliseconds: Int?
    /// 게임을 앞으로 올리고 눌렀다가 원래 앱으로 돌아오기까지.
    public let clickMilliseconds: Int

    public var totalMilliseconds: Int {
        observeMilliseconds
            + idleWaitMilliseconds
            + reobserveMilliseconds
            + clickMilliseconds
    }

    public init(
        observe: Duration,
        capture: Duration? = nil,
        idleWait: Duration,
        reobserve: Duration,
        reobserveCapture: Duration? = nil,
        click: Duration
    ) {
        observeMilliseconds = Self.milliseconds(observe)
        captureMilliseconds = capture.map(Self.milliseconds)
        idleWaitMilliseconds = Self.milliseconds(idleWait)
        reobserveMilliseconds = Self.milliseconds(reobserve)
        reobserveCaptureMilliseconds =
            reobserveCapture.map(Self.milliseconds)
        clickMilliseconds = Self.milliseconds(click)
    }

    /// 클럭이 뒤로 가거나 측정이 어긋나도 음수가 남지 않게 자른다.
    private static func milliseconds(_ duration: Duration) -> Int {
        let components = duration.components
        let value = components.seconds * 1_000
            + components.attoseconds / 1_000_000_000_000_000
        return value > 0 ? Int(value) : 0
    }
}

public struct ActivityEvent: Codable, Equatable, Sendable {
    public let at: Date
    public let outcome: String
    public let scene: String?
    public let dungeonName: String?
    public let phases: ClickPhaseTimings?
    /// 이 기록을 남긴 빌드. 채우는 쪽은 writer라 호출부는 건드리지 않는다.
    /// 스탬프를 찍기 전에 쌓인 기록에는 없으므로 옵셔널이다.
    public let build: String?

    public init(
        at: Date,
        outcome: String,
        scene: String?,
        dungeonName: String?,
        phases: ClickPhaseTimings? = nil,
        build: String? = nil
    ) {
        self.at = at
        self.outcome = outcome
        self.scene = scene
        self.dungeonName = dungeonName
        self.phases = phases
        self.build = build
    }

    func stamped(_ build: String?) -> ActivityEvent {
        guard let build else {
            return self
        }
        return ActivityEvent(
            at: at,
            outcome: outcome,
            scene: scene,
            dungeonName: dungeonName,
            phases: phases,
            build: build
        )
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
    private let build: String?

    public init(directory: URL, build: String? = nil) {
        self.directory = directory
        self.build = build
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    public func append(_ event: ActivityEvent) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.withoutEscapingSlashes]
        try JSONLinesFile.append(
            encoder.encode(event.stamped(build)),
            to: fileURL,
            in: directory
        )
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
