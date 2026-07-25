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
    // 임무 선택 상태(은동전 부족): 안내문이 떠 있어 '선택됨'을 눌러 해제한다.
    ("landscape-selected-nocoin", "deselect_challenge"),
    // 해제 상태(은동전 부족): 버튼이 '입장하기'로 바뀌어 입장한다.
    ("landscape-deselected-nocoin", "enter_ready"),
    // 임무 선택 상태(은동전 충분): 안내문 대신 두 배 보상 안내가 뜬다.
    // 은동전을 쓰지 않는 것이 기본이므로 '선택됨'을 눌러 해제한다.
    ("landscape-mission-select-10coin", "deselect_double_loot"),
    // 해제 상태(은동전 충분): '입장하기'가 깨끗하게 떠 입장한다.
    ("landscape-deselected-10coin", "enter_ready"),
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
func sufficientCoinsDoNotStallTheMissionSelectScreen() async throws {
    // 회귀(2026-07-25): 은동전이 10개를 넘긴 순간 임무 선택 화면이 바뀐다.
    // '선택을 해제하면 임무 없이 입장할 수 있습니다.' 안내문이 사라지고
    // 두 배 보상 미리보기가 대신 뜨는데, 그러면
    //   deselect_challenge → 시그니처(안내문)가 없어 안 걸림
    //   enter_ready       → 버튼이 '10 입장하기'라 완전 일치 실패
    //   mission_selection → '도전'이 신뢰도 0.50이라 기준 미달
    // 셋 다 빗나가 후보가 0개가 되고 자동화가 통째로 멈췄다.
    // 은동전을 쓰지 않는 기본 동작으로 '선택됨'을 눌러 해제해야 한다.
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-mission-select-10coin"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(!result.actionCandidates.isEmpty)
    #expect(result.actionCandidates.first?.targetText == "선택됨")
}

@Test
func retryMenuFiresAloneWhenCoinsAreSufficient() async throws {
    // 실측(은동전 10개 = 충분한 상태의 결과 화면): 코인이 모자랄 때 뜨던
    // '다음 임무에 사용할 은동전이 부족해요.'가 사라지고 '다음 구역에
    // 도전해 봐요.'로 바뀐다. 버튼 구성(나가기/다시 하기/다음 구역으로)은
    // 같으므로, 코인 잔량과 무관하게 '다시 하기'만 눌러야 한다.
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-retry-menu-10coin"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    #expect(result.actionCandidates.first?.ruleID == "reward_retry")
    #expect(result.actionCandidates.first?.targetText == "다시 하기")
}

@Test
func autoStartGaugeIsSkippedByPressingTheStartButton() async throws {
    // 실측(던전 입장 직후, 약 5초): 우하단에 나침반 버튼과 초록 링 게이지가
    // 뜨고 '잠시 후 자동으로 진행됩니다.'가 표시된다. 링이 다 차야 자동
    // 전투가 시작되므로 매 판 5초를 버린다. 버튼을 눌러 즉시 시작한다.
    //
    // 말풍선 자체는 '중단하려면 말풍선을 누르세요'라 눌러선 안 된다 —
    // 누르면 자동 진행이 취소된다. 눌러야 하는 건 그 아래 'Space' 라벨이
    // 붙은 원형 버튼이다.
    let observer = SceneObserver()

    let result = try await observer.observe(
        image: try liveFixtureImage(named: "landscape-autostart-gauge"),
        layout: .landscape,
        rules: RuleLoader().loadDefaultRules()
    )

    #expect(result.actionCandidates.count == 1)
    let candidate = try #require(result.actionCandidates.first)
    #expect(candidate.ruleID == "auto_start")
    #expect(candidate.targetText == "Space")
    // 취소용 말풍선(y 0.75~0.79)이 아니라 그 아래 버튼을 눌러야 한다.
    #expect(candidate.boundingBox.midY / 949 > 0.90)
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
func revealedEquipmentDropIsRecordedInTheSameCycle() async throws {
    // 실측(은동전 쓴 런): 결과 화면이 처음 뜰 때 전리품 한 칸이 '?'로
    // 가려져 있고, '발견한 전리품'을 눌러야 장비 드랍이 드러난다. 두 프레임을
    // 순서대로 흘려 넣어 한 판으로 합쳐지는지 본다 — 처음 프레임만 봤다면
    // 장비를 통째로 놓친다.
    let recognizer = VisionTextRecognizer()
    let hidden = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-loot-coin-used")
    )
    let revealed = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-loot-coin-used-revealed")
    )
    var tracker = CycleTracker()
    let size = CGSize(width: 1_512, height: 949)

    _ = tracker.observe(texts: hidden, imageSize: size)
    _ = tracker.observe(texts: revealed, imageSize: size)
    let closed = tracker.observe(texts: [], imageSize: size)
    let record = try #require(closed)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds == 16)
    // 가려져 있던 장비(OCR이 두 줄로 끊어 읽는다)가 들어와야 한다.
    #expect(record.items.contains { $0.contains("방패의 판금") })
    // 처음부터 보이던 것도 그대로 남는다.
    #expect(record.items.contains("룬의 파편"))
}

@Test
func coinUsedRunRecordsItsDoubledLoot() async throws {
    // 실측(은동전 10개를 쓰고 들어간 런의 전리품 화면, 소모 후 잔량 0):
    // 두 배 보상이라 아이템이 훨씬 많다(안 쓴 런 5종 → 17종). 화면 구조는
    // 같으므로 같은 마커로 한 사이클이 기록돼야 한다.
    let recognizer = VisionTextRecognizer()
    let texts = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-loot-coin-used")
    )
    var tracker = CycleTracker()

    let size = CGSize(width: 1_512, height: 949)
    _ = tracker.observe(texts: texts, imageSize: size)
    let closed = tracker.observe(texts: [], imageSize: size)
    let record = try #require(closed)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds == 16)
    #expect(record.items.contains("룬의 파편"))
    #expect(record.items.contains("조각난 흑요석"))
    // 두 배 보상 런은 안 쓴 런보다 확실히 많은 종류가 잡힌다.
    #expect(record.items.count > 10)
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

    let size = CGSize(width: 1_512, height: 949)
    _ = tracker.observe(texts: texts, imageSize: size)
    let closed = tracker.observe(texts: [], imageSize: size)
    let record = try #require(closed)

    #expect(record.dungeon == "룬다 1층 2구역")
    #expect(record.combatSeconds == 14)
    #expect(record.items.contains("공명의 영혼석"))
    #expect(record.items.contains("마물 퇴치 증표"))
}

@Test
func recordedItemsExcludeButtonsAndNotices() async throws {
    // 실측 회귀(첫 실사용 기록): 아이템 그리드 아래의 버튼·안내문이 전리품
    // 이름으로 섞여 들어갔다('나가기', '다시 하기', '던전 탐험을
    // 계속하시겠습니까?', '은동전이 부족해요.'). 드랍률 집계가 오염된다.
    let recognizer = VisionTextRecognizer()
    let texts = try await recognizer.recognizeText(
        in: try liveFixtureImage(named: "landscape-loot-soulstone-nocoin")
    )
    var tracker = CycleTracker()
    let size = CGSize(width: 1_512, height: 949)

    _ = tracker.observe(texts: texts, imageSize: size)
    let closed = tracker.observe(texts: [], imageSize: size)
    let record = try #require(closed)

    // 진짜 전리품은 남는다.
    #expect(record.items.contains("공명의 영혼석"))
    // 버튼·안내문·OCR 잡음은 빠진다.
    for noise in [
        "나가기", "다시 하기", "다음 구역으로", "은동전이 부족해요.", "BO", "BP",
    ] {
        #expect(!record.items.contains(noise), "전리품에 '\(noise)'가 섞였다")
    }
    #expect(!record.items.contains { $0.contains("상세 정보") })
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
