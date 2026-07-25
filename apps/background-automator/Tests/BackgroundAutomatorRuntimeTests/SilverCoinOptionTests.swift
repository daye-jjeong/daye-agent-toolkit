import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

// 은동전을 쓸지 말지는 사용자가 고른다.
//
//   끔(기본) 임무를 해제하고 들어가 은동전을 아낀다.
//   켬       임무를 그대로 두고 들어가 전리품을 두 배로 받는다(10개 소모).
//
// 켠 상태의 입장 버튼은 '10 입장하기'인데 OCR이 ') 입장하기'로 흘려 읽기도
// 해서 완전 일치로는 잡히지 않는다. 그래서 이 규칙만 끝말 일치를 쓴다.
// 반대로 끈 상태의 enter_ready는 완전 일치를 유지해야 한다 — 그 완전 일치가
// 실수로 은동전을 쓰지 않게 막는 안전장치다.

private func coinFixture(named name: String) throws -> CGImage {
    let url = try #require(
        Bundle.module.url(
            forResource: name,
            withExtension: "png",
            subdirectory: "Fixtures"
        )
    )
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    return try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
}

@Test
func coinOffDeselectsTheMissionBeforeEntering() async throws {
    let rules = try RuleLoader().loadDefaultRules(usesSilverCoin: false)
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try coinFixture(named: "landscape-mission-select-10coin"),
        layout: .landscape,
        rules: rules
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.targetText == "선택됨")
}

@Test
func coinOnEntersWithTheMissionKept() async throws {
    let rules = try RuleLoader().loadDefaultRules(usesSilverCoin: true)
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try coinFixture(named: "landscape-mission-select-10coin"),
        layout: .landscape,
        rules: rules
    )

    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "enter_with_coin")
    // 버튼 글자가 흔들려도(') 입장하기') 끝말로 잡는다.
    #expect(candidate.targetText?.hasSuffix("입장하기") == true)
    // 해제 규칙은 빠져 있어야 한다 — 함께 뜨면 모호성으로 멈춘다.
    #expect(!rules.contains { $0.id == "deselect_double_loot" })
}

@Test
func coinOnStillNeedsTheDoubleLootScreenSignature() async throws {
    // 켠 상태여도 은동전이 모자라면(안내문이 뜨는 화면) 두 배 보상 문구가
    // 없어 이 규칙이 발동하지 않는다. 기존 해제 흐름이 그대로 처리한다.
    let rules = try RuleLoader().loadDefaultRules(usesSilverCoin: true)
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try coinFixture(named: "landscape-selected-nocoin"),
        layout: .landscape,
        rules: rules
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == "deselect_challenge")
}

@Test
func suffixMatchingIsScopedToTheOptInRuleOnly() throws {
    // 끝말 일치는 은동전 규칙에만 쓴다. enter_ready가 끝말로 바뀌면
    // '10 입장하기'까지 눌러 은동전을 몰래 쓰게 된다.
    let rules = try RuleLoader().loadDefaultRules(usesSilverCoin: true)
    for rule in rules where rule.id != "enter_with_coin" {
        #expect(rule.action.targetTextSuffix == nil, "규칙 \(rule.id)")
    }
}
