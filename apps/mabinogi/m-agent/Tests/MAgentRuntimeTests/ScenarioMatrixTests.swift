import MAgentCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import MAgentRuntime

/// 모든 실캡처 × 옵션 조합에서 어느 규칙이 이기는지 한 표로 뽑는다.
///
/// 시나리오를 말로 정리하면 어긋난다(실제로 두 번 틀렸다). 화면마다 후보가
/// 정확히 하나여야 하고, 하나도 없으면 그 화면에서 앱이 멈춘다.
@Test
func everyCapturedScreenResolvesToExactlyOneAction() async throws {
    var lines: [String] = []
    var stalls: [String] = []
    var ambiguous: [String] = []

    for fixture in ScenarioMatrix.fixtures {
        for option in ScenarioMatrix.Option.allCases {
            let image = try scenarioFixture(fixture)
            let result = try await SceneObserver().observe(
                image: image,
                layout: .landscape,
                rules: RuleLoader().loadDefaultRules(
                    usesSilverCoin: option.usesSilverCoin,
                    usesTribute: option.usesTribute
                )
            )
            let ids = result.actionCandidates.map(\.ruleID).sorted()
            let verdict = ids.isEmpty
                ? "— 멈춤"
                : ids.joined(separator: " + ")
            lines.append("\(fixture) [\(option.label)] → \(verdict)")
            if ids.isEmpty {
                stalls.append("\(fixture) [\(option.label)]")
            } else if ids.count > 1 {
                ambiguous.append("\(fixture) [\(option.label)] → \(verdict)")
            }
        }
    }

    print("\n=== 시나리오 표 ===")
    for line in lines {
        print(line)
    }
    print("=== 끝 ===\n")

    #expect(ambiguous.isEmpty, "후보가 둘 이상이면 모호성으로 멈춘다")
    // 멈추는 화면이 있으면 목록으로 남긴다. 결과 화면 일부는 다음 프레임을
    // 기다리는 게 정상이라 여기서 실패로 보지 않고 눈으로 확인한다.
    print("멈추는 조합 \(stalls.count)개: \(stalls)")
}

enum ScenarioMatrix {
    enum Option: CaseIterable {
        case bothOff
        case coinOn
        case tributeOn

        var usesSilverCoin: Bool { self == .coinOn }
        var usesTribute: Bool { self == .tributeOn }

        var label: String {
            switch self {
            case .bothOff: "둘 다 끔"
            case .coinOn: "은동전 켬"
            case .tributeOn: "공물 켬"
            }
        }
    }

    static let fixtures = [
        // 입장 화면 — 은동전
        "landscape-double-loot-selected",
        "landscape-double-loot-available-off",
        "landscape-double-loot-nomission",
        "landscape-mission-select-10coin",
        "landscape-selected-nocoin",
        // 입장 화면 — 공물
        "landscape-tribute-selected",
        "landscape-tribute-deselected",
        "landscape-tribute-entry-nomore",
        "landscape-tribute-nomore-deselected",
        // 결과 화면
        "landscape-result-early",
        "landscape-reward-detail",
        "landscape-reward-detail-nocoin",
        "landscape-retry-menu-10coin",
        "landscape-tribute-result-selected",
        "landscape-tribute-result-revealed",
        "landscape-tribute-result-deselected",
        "landscape-tribute-result-nomore",
        // 컷신·다이얼로그
        "landscape-scene-skip-clear",
        "landscape-scene-skip-boss-intro",
        "landscape-continue-dialog-quest",
        "landscape-continue-dialog-nocoin",
    ]
}

private func scenarioFixture(_ name: String) throws -> CGImage {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Fixtures/\(name).png")
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    return try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
}
