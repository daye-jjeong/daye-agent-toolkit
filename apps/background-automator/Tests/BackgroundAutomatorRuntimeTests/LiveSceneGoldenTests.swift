import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

// 실제 게임 캡처를 진짜 Vision OCR 파이프라인에 통과시켜, 각 장면에서
// 의도한 규칙 하나만 발동하는지 확인한다. 손으로 먹인 OCR 값으로는
// 잡히지 않는 실화면 인식 변화(오독·겹침·연출 오버레이)를 여기서 잡는다.
//
// 후보가 2개 이상이면 자동화는 모호성으로 얼어붙어 정지하므로,
// '단독 발동'은 각 장면의 필수 조건이다.

@Test(arguments: [
    // 보스전 돌입 컷신: '장면 넘기기' + 보스 이름이 함께 뜬다.
    ("landscape-scene-skip-boss-intro", "scene_skip"),
    // 클리어 컷신: '장면 넘기기'만 단독으로 뜬다.
    ("landscape-scene-skip-clear", "scene_skip"),
    // 보스 처치 후 등급 화면: 하단 '화면을 터치해 주세요'(cf 1.0).
    ("landscape-clear-touch-live", "clear_touch"),
    // 임무 선택 상태: 안내문이 떠 있어 '선택됨'을 눌러 해제한다.
    ("landscape-selected-nocoin", "deselect_challenge"),
    // 해제 상태: 버튼이 '입장하기'로 바뀌어 입장한다.
    ("landscape-deselected-nocoin", "enter_ready"),
])
func liveSceneFiresExactlyOneExpectedRule(
    fixture: String,
    expectedRuleID: String
) async throws {
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: fixture),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == expectedRuleID)
}

@Test
func earlyResultScreenWaitsInsteadOfClicking() async throws {
    // 실측(landscape-result-early): 클리어 직후 결과 화면에는 던전 이름과
    // 순수 전투 시간만 뜨고 '발견한 전리품'은 아직 없다. 누를 것이 없으니
    // 후보도 없어야 한다 — 여기서 무언가 눌리면 연출 중 오클릭이다.
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-result-early"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.isEmpty)
}

@Test
func loot_recordsItemsWithoutQuantityBadgeSuchAsSoulstone() async throws {
    // 실측(은동전 없이 돈 런, 공명의 영혼석 드랍): 같은 화면에서
    // '마물 퇴치 증표'는 10, '미지의 소울 조각'은 1이 찍히는데 '공명의
    // 영혼석'만 수량 뱃지가 아예 없다. 즉 '뱃지 없음 = 1'로 단정할 수
    // 없다(정확한 개수는 별도 과제). 다만 드랍률 계산에 필요한 '이번
    // 사이클에 나왔나'는 이름만으로 정확히 남아야 한다.
    let recognizer = VisionTextRecognizer()
    let texts = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-loot-soulstone-nocoin")
    )
    var tracker = CycleTracker()

    let recorded = tracker.observe(
        texts: texts,
        imageSize: CGSize(width: 1_512, height: 949)
    )
    let record = try #require(recorded)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds == 14)
    #expect(record.items.contains("공명의 영혼석"))
    #expect(record.items.contains("마물 퇴치 증표"))
}

@Test
func loot_screenWithRetryMenuStillFiresOnlyRetry() async throws {
    // 결과 화면에는 '발견한 전리품'과 '다시 하기'가 함께 뜬다. 둘 다
    // 후보가 되면 모호성으로 정지하므로 재도전만 남아야 한다.
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-loot-soulstone-nocoin"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == "reward_retry")
}

@Test
func continueDialogFiresAloneEvenWithLootHeaderBehind() async throws {
    // 실측(은동전 없이 돈 런): '던전 탐험을 계속하시겠습니까?' 팝업이
    // 결과 화면 위에 뜨면서 '발견한 전리품'(y0.46)이 뒤에 그대로 남는다.
    // 두 규칙이 함께 후보가 되면 모호성으로 정지하므로 계속하기만 남아야
    // 한다('다시 하기'는 이 화면에 없어서 reward_detail의 기존 가드로는
    // 막히지 않는다).
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-continue-dialog-nocoin"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == "continue_dialog")
}

@Test
func sceneSkipNeverClicksTheSkipButtonItself() async throws {
    // 안전 규칙: 장면 넘기기 버튼은 절대 직접 누르지 않는다. 컷신은 빈
    // 공간을 탭해서 넘긴다(targetText 없이 safePoint만 쓴다).
    let observer = SceneObserver()

    for fixture in [
        "landscape-scene-skip-boss-intro",
        "landscape-scene-skip-clear",
    ] {
        let result = try await observer.observe(
            image: try liveFixtureImage(named: fixture),
            layout: .landscape,
            rules: RuleLoader().loadDefaultRules()
        )
        let candidate = try #require(result.actionCandidates.first)
        #expect(candidate.targetText == nil)
    }
}

@Test
func entryButtonTextDependsOnMissionSelectionNotCoinBalance() async throws {
    // 실측(은동전 7개 = 10개 미만인 같은 계정, 같은 화면):
    //   선택됨   → 안내문 있음 + 버튼 '10 입장하기'
    //   해제됨   → 안내문 없음 + 버튼 '입장하기'
    // '10'은 보유량이 아니라 임무 전리품 2배에 드는 은동전 '비용'이다.
    // 임무를 해제하면 비용이 사라져 버튼 글자가 바뀐다. 따라서 enter_ready의
    // '입장하기' 완전 일치는 해제 상태에서 정상 동작하며, 선택 상태에서는
    // 매칭되지 않아 deselect_challenge에 자리를 내준다.
    let recognizer = VisionTextRecognizer()

    let selected = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-selected-nocoin")
    ).map(\.text)
    let deselected = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-deselected-nocoin")
    ).map(\.text)

    #expect(selected.contains("10 입장하기"))
    #expect(selected.contains("선택을 해제하면 임무 없이 입장할 수 있습니다."))
    #expect(deselected.contains("입장하기"))
    #expect(!deselected.contains("10 입장하기"))
    #expect(
        !deselected.contains("선택을 해제하면 임무 없이 입장할 수 있습니다.")
    )
}

private func liveFixtureImage(named name: String) throws -> CGImage {
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
