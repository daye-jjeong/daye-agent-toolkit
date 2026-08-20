import Foundation

/// 지금 돌고 있는 빌드의 신원.
///
/// 배포 전후로 빨라졌는지 판단하려면 기록마다 '어느 빌드가 남겼나'가 있어야
/// 한다. 시각으로 자르면 두 군데서 어긋난다(2026-07-26 실측) — 빌드해도 앱을
/// 다시 켜지 않으면 옛 바이너리가 계속 돌고, 배포 시각 자체가 로그에 없어
/// 기억이나 프로세스 가동 시간으로 역산해야 한다.
public struct BuildIdentity: Equatable, Sendable {
    /// 스탬프가 없을 때. `swift run`이나 build-app.sh를 거치지 않은 번들이다.
    public static let developmentIdentifier = "dev"
    public static let identifierKey = "BABuildIdentifier"
    public static let summaryKey = "BABuildSummary"

    /// `a81ec70-0726T1558` — 커밋 해시와 빌드 시각. 커밋하지 않고 빌드하는
    /// 일이 잦아 해시만으로는 빌드끼리 구분되지 않는다.
    public let id: String
    /// 이 빌드에 새로 들어간 변경. 직전 빌드 이후의 커밋 제목이다.
    public let summary: String?

    public init(id: String, summary: String? = nil) {
        self.id = id
        self.summary = Self.cleaned(summary)
    }

    public init(infoDictionary: [String: Any]?) {
        id = Self.cleaned(infoDictionary?[Self.identifierKey] as? String)
            ?? Self.developmentIdentifier
        summary = Self.cleaned(infoDictionary?[Self.summaryKey] as? String)
    }

    public static func current(bundle: Bundle = .main) -> BuildIdentity {
        BuildIdentity(infoDictionary: bundle.infoDictionary)
    }

    /// 빈 문자열·공백만 남은 값은 없는 것으로 본다. 스탬프를 못 찍었을 때
    /// 비교표에 빈칸이 남는 대신 '없음'으로 떨어진다.
    private static func cleaned(_ text: String?) -> String? {
        let trimmed = text?.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let trimmed, !trimmed.isEmpty else {
            return nil
        }
        return trimmed
    }
}

/// 빌드가 처음 돈 시각과 그 빌드에 들어간 변경.
///
/// 사이클·클릭 기록은 빌드 아이디만 달고, 설명은 여기 한 줄로 둔다. 줄마다
/// 설명을 반복하면 로그만 커지고 값은 같다.
public struct BuildRecord: Codable, Equatable, Sendable {
    public let build: String
    public let firstSeenAt: Date
    public let summary: String?

    public init(build: String, firstSeenAt: Date, summary: String?) {
        self.build = build
        self.firstSeenAt = firstSeenAt
        self.summary = summary
    }
}

public final class BuildLogWriter {
    public static let fileName = "builds.jsonl"

    private let directory: URL
    private let fileURL: URL

    public init(directory: URL) {
        self.directory = directory
        fileURL = directory.appendingPathComponent(Self.fileName)
    }

    /// 아직 없는 빌드면 한 줄 남기고 true. 앱은 켤 때마다 부르므로, 같은
    /// 빌드를 몇 번 켜도 줄이 하나여야 아이디로 조인한 결과가 흔들리지 않는다.
    @discardableResult
    public func recordIfNeeded(
        _ identity: BuildIdentity,
        at now: Date = Date()
    ) throws -> Bool {
        guard !recordedBuilds().contains(identity.id) else {
            return false
        }
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.withoutEscapingSlashes]
        try JSONLinesFile.append(
            encoder.encode(
                BuildRecord(
                    build: identity.id,
                    firstSeenAt: now,
                    summary: identity.summary
                )
            ),
            to: fileURL,
            in: directory
        )
        return true
    }

    public func records() -> [BuildRecord] {
        guard
            let data = try? Data(contentsOf: fileURL),
            !data.isEmpty
        else {
            return []
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return data.split(separator: 0x0A).compactMap {
            try? decoder.decode(BuildRecord.self, from: Data($0))
        }
    }

    private func recordedBuilds() -> Set<String> {
        Set(records().map(\.build))
    }
}

/// JSONL 한 줄 덧붙이기. 사이클·클릭·빌드 세 로그가 같은 방식을 쓴다.
enum JSONLinesFile {
    static func append(_ line: Data, to fileURL: URL, in directory: URL) throws {
        var line = line
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
}
