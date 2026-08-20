import Foundation
import MAgentRuntime

/// 메뉴 "플랫폼 상태" 한 줄. 심볼(🟢/🔴/❔) + 라벨 + 세부.
struct PlatformStatusRow: Equatable {
    let label: String
    let symbol: String
    let detail: String
}

/// 시세 수집기(launchd)가 매 사이클 남기는 heartbeat 파일을 읽는다.
/// 수집기는 눈에 안 보이는 백그라운드 프로세스라, 데이터 신선도로 살아있는지
/// 판단한다 — 프로세스가 살아도 403이면 as_of가 안 올라가므로.
///
/// 계약: apps/mabinogi/README.md. heartbeat 경로는
/// ~/.mabi/equipment-cost/collector-status.json (collect.py loop가 씀).
enum PlatformStatus {
    /// 10분 간격의 2.5배. 이보다 오래 안 갱신되면 멈춘 것으로 본다.
    private static let staleSeconds: TimeInterval = 25 * 60

    private struct Heartbeat: Decodable {
        let lastRun: String
        let ok: Bool
        let count: Int
        let error: String?

        enum CodingKeys: String, CodingKey {
            case lastRun = "last_run"
            case ok, count, error
        }
    }

    static func collectorRow(now: Date = Date()) -> PlatformStatusRow {
        let label = "시세 수집기"
        guard let home = MAgentPaths.supportDirectory()?.deletingLastPathComponent()
        else {
            return PlatformStatusRow(label: label, symbol: "❔", detail: "경로 없음")
        }
        let path = home
            .appendingPathComponent("equipment-cost", isDirectory: true)
            .appendingPathComponent("collector-status.json")

        guard
            let data = try? Data(contentsOf: path),
            let beat = try? JSONDecoder().decode(Heartbeat.self, from: data),
            let lastRun = ISO8601DateFormatter().date(from: beat.lastRun)
        else {
            return PlatformStatusRow(label: label, symbol: "❔", detail: "미확인")
        }

        let ago = relative(now.timeIntervalSince(lastRun))
        if !beat.ok {
            let why = beat.error.map { String($0.prefix(40)) } ?? "실패"
            return PlatformStatusRow(label: label, symbol: "🔴", detail: "\(ago) · \(why)")
        }
        if now.timeIntervalSince(lastRun) > staleSeconds {
            return PlatformStatusRow(label: label, symbol: "🔴", detail: "\(ago) · 멈춤?")
        }
        return PlatformStatusRow(label: label, symbol: "🟢", detail: "\(ago) · \(beat.count)건")
    }

    private static func relative(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds / 60)
        if minutes < 1 { return "방금" }
        if minutes < 60 { return "\(minutes)분 전" }
        return "\(minutes / 60)시간 전"
    }
}
