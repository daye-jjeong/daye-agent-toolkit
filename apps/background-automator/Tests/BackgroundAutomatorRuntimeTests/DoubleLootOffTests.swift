import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

/// 더블 루팅은 아직 지원하지 않는다(전리품 절반이 스크롤 아래에 있어
/// 기록이 안 된다). 켜져 있으면 은동전이 판당 20개 나가므로 무조건 끈다.
@Test(arguments: [false, true])
func doubleLootIsAlwaysTurnedOffRegardlessOfCoinOption(
    usesSilverCoin: Bool
) async throws {
    let image = try doubleLootFixture("landscape-double-loot-selected")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesSilverCoin: usesSilverCoin)
    )

    // 둘 다 선택된 화면엔 '선택됨'이 두 개다. 지금까지는 '정확히 하나'
    // 조건이 깨져 아무 후보도 없이 멈췄다.
    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "turn_off_double_loot")
    #expect(candidate.targetText == "선택됨")

    // 임무가 아니라 더블 루팅 쪽을 눌러야 한다 — 안내문보다 아래다.
    let texts = try await VisionTextRecognizer().recognizeText(in: image)
    let anchor = try #require(
        texts.first {
            $0.text.contains("두 배가 됩니다")
        }
    )
    #expect(candidate.boundingBox.midY > anchor.boundingBox.midY)
}

@Test(arguments: [
    "landscape-double-loot-available-off",
    "landscape-double-loot-nomission",
    "landscape-mission-select-10coin",
])
func doubleLootOffRuleStaysQuietWhenItIsAlreadyOff(
    fixture: String
) async throws {
    // 더블 루팅이 꺼져 있으면 이 규칙은 뜨면 안 된다. 뜨면 임무 쪽
    // '선택됨'을 눌러 엉뚱한 걸 해제하거나 후보가 겹쳐 멈춘다.
    for usesSilverCoin in [false, true] {
        let result = try await SceneObserver().observe(
            image: try doubleLootFixture(fixture),
            layout: .landscape,
            rules: RuleLoader().loadDefaultRules(
                usesSilverCoin: usesSilverCoin
            )
        )
        #expect(
            !result.actionCandidates.contains {
                $0.ruleID == "turn_off_double_loot"
            }
        )
        // 화면마다 후보는 늘 하나여야 한다(모호하면 자동화가 얼어붙는다).
        #expect(result.actionCandidates.count <= 1)
    }
}

@Test
func doubleLootOffRuleIsPresentInBothCoinModes() throws {
    // 은동전을 쓰든 말든 더블 루팅은 끈다.
    for usesSilverCoin in [false, true] {
        let rules = try RuleLoader().loadDefaultRules(
            usesSilverCoin: usesSilverCoin
        )
        #expect(rules.contains { $0.id == "turn_off_double_loot" })
    }
    #expect(
        AutomationCoordinator.scene(forRuleID: "turn_off_double_loot")
            == .turnOffDoubleLoot
    )
}

private func doubleLootFixture(_ name: String) throws -> CGImage {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Fixtures/\(name).png")
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    return try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
}
