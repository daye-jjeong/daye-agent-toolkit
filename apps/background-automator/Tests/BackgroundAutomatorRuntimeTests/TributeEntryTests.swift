import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

/// 공물 던전(페카 고분)은 임무를 1개 소모한다. 은동전 던전과 화면 골격은
/// 같지만 더블 루팅 카드가 없어 `도전에 성공하면 임무 전리품이 두 배가
/// 됩니다.`가 뜨지 않는다. 그 문구를 필수로 삼은 기존 규칙이 전부 어긋나
/// 공물이 남아 있는 동안에는 입장 화면에서 멈췄다.

@Test
func tributeIsSkippedByDeselectingTheMissionWhenTheOptionIsOff() async throws {
    let image = try tributeFixture("landscape-tribute-selected")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesTribute: false)
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.ruleID == "deselect_tribute")
    #expect(candidate.targetText == "선택됨")
}

@Test
func tributeIsSpentByPressingEnterWhenTheOptionIsOn() async throws {
    let image = try tributeFixture("landscape-tribute-selected")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesTribute: true)
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(result.actionCandidates.count == 1)
    #expect(candidate.ruleID == "enter_with_tribute")
    // OCR은 버튼을 '공물1 입장하기'처럼 읽는다.
    #expect(candidate.targetText?.hasSuffix("입장하기") == true)
}

@Test(arguments: [false, true])
func deselectedTributeScreenEntersRegardlessOfTheOption(
    usesTribute: Bool
) async throws {
    // 임무가 이미 해제됐으면 옵션과 무관하게 그냥 들어간다.
    let image = try tributeFixture("landscape-tribute-deselected")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesTribute: usesTribute)
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "enter_ready")
}

@Test(arguments: [false, true])
func exhaustedTributeIsResolvedByDeselecting(
    usesTribute: Bool
) async throws {
    // 공물이 0이면 입장 버튼이 비활성이고 '선택을 해제하면 임무 없이 입장할
    // 수 있습니다.' 안내문이 뜬다. 공물 쓰기를 켜 뒀어도 해제해야 빠져나온다
    // — 안 그러면 죽은 버튼을 계속 누른다.
    let image = try tributeFixture("landscape-tribute-entry-nomore")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesTribute: usesTribute)
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "deselect_challenge")
    #expect(candidate.targetText == "선택됨")
}

@Test(arguments: [false, true])
func exhaustedAndDeselectedTributeScreenEnters(
    usesTribute: Bool
) async throws {
    let image = try tributeFixture("landscape-tribute-nomore-deselected")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesTribute: usesTribute)
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "enter_ready")
}

@Test(arguments: [false, true])
func exhaustedSilverCoinIsResolvedByDeselecting(
    usesSilverCoin: Bool
) async throws {
    // 재화가 바닥나면 '쓰기'를 켜 뒀어도 해제해야 빠져나온다. 은동전이
    // 임무값에도 모자라면 더블 루팅 카드가 통째로 사라져 '도전에 성공하면
    // 임무 전리품이 두 배가 됩니다.'가 없고, 대신 해제 안내문이 뜬다.
    // 그래서 enter_with_coin이 죽은 버튼을 누르는 일이 없다.
    let image = try tributeFixture("landscape-selected-nocoin")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules(usesSilverCoin: usesSilverCoin)
    )

    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "deselect_challenge")
    #expect(candidate.targetText == "선택됨")
}

@Test(arguments: [
    "landscape-double-loot-selected",
    "landscape-mission-select-10coin",
    "landscape-double-loot-available-off",
    "landscape-selected-nocoin",
])
func tributeRulesStayQuietOnSilverCoinScreens(
    fixture: String
) async throws {
    // 은동전 화면에도 '선택됨'과 '입장하기'가 있다. 공물 규칙이 여기서
    // 발동하면 후보가 겹쳐 자동화가 모호성으로 멈춘다.
    let image = try tributeFixture(fixture)
    for usesTribute in [false, true] {
        let result = try await SceneObserver().observe(
            image: image,
            layout: .landscape,
            rules: RuleLoader().loadDefaultRules(usesTribute: usesTribute)
        )
        let ids = Set(result.actionCandidates.map(\.ruleID))
        #expect(!ids.contains("deselect_tribute"))
        #expect(!ids.contains("enter_with_tribute"))
    }
}

@Test
func continueDialogIsAnsweredOnTheTributeRoute() async throws {
    // '다시 하기' 뒤에 가끔 끼어드는 확인창. 페카에서도 같은 규칙이 받는다.
    let image = try tributeFixture("landscape-continue-dialog-quest")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "continue_dialog")
    #expect(candidate.targetText == "계속하기")
}

@Test
func tributeResultScreenRetriesRatherThanLeaving() async throws {
    // 공물이 떨어지면 게임이 '나가기'를 강조하지만, 파밍은 계속해야 한다.
    let image = try tributeFixture("landscape-tribute-result-nomore")
    let result = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "reward_retry")
    #expect(candidate.targetText == "다시 하기")
}

private func tributeFixture(_ name: String) throws -> CGImage {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Fixtures/\(name).png")
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    return try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
}
