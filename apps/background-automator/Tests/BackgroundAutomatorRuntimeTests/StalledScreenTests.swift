import BackgroundAutomatorCore
import CoreGraphics
import Foundation
import ImageIO
import Testing

@testable import BackgroundAutomatorRuntime

/// 실제로 앱이 굳었던 화면을 그대로 통과시켜 본다.
///
/// 2026-07-29 17:08에 은동전이 6개(임무값 10개)로 떨어진 입장 화면에서
/// 150초를 서 있었다. 안내는 '누를 버튼을 찾지 못했습니다'였는데, 이 테스트가
/// 그 화면을 규칙에 태워 보니 후보도 잡히고 검증도 통과한다 — 화면·규칙·OCR
/// 어느 쪽도 문제가 아니었다는 뜻이다. 그 덕에 원인 후보를 캡처·재확인 쪽으로
/// 좁혔다. 이 화면이 다시 막히면 여기서 걸린다.
@Test(arguments: [(false, false), (true, false), (false, true)])
func coinShortEntryScreenIsAlwaysHandledByDeselect(
    usesSilverCoin: Bool,
    usesTribute: Bool
) async throws {
    let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("Fixtures/landscape-coin-entry-nomore.png")
    let source = try #require(CGImageSourceCreateWithURL(url as CFURL, nil))
    let image = try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))

    let rules = try RuleLoader().loadDefaultRules(
        usesSilverCoin: usesSilverCoin,
        usesTribute: usesTribute
    )
    let observation = try await SceneObserver().observe(
        image: image,
        layout: .landscape,
        rules: rules
    )

    // 재화가 모자라면 옵션과 무관하게 임무를 해제하고 들어간다.
    #expect(observation.actionCandidates.map(\.ruleID) == ["deselect_challenge"])

    // 규칙 매칭을 넘어 최종 검증까지 통과하는지 본다. 관찰만 보고 넘어가면
    // '후보는 잡혔는데 클릭이 안 나가는' 구간을 그대로 놓친다.
    let identified = SceneObservation(
        captureIdentity: try CaptureIdentity(
            sessionID: UUID(),
            sequence: 1
        ),
        imageSize: observation.imageSize,
        recognizedTexts: observation.recognizedTexts,
        actionCandidates: observation.actionCandidates
    )
    var evaluator = try RuleEvaluator(rules: rules)
    let validated = evaluator.validatedCandidate(
        observation: identified,
        // 실제 창과 같은 값 — 왼쪽 모니터라 x가 음수다.
        windowIdentity: WindowCandidate(
            windowID: 115_929,
            processID: 46116,
            bundleIdentifier: "com.nexon.devcat.mm",
            title: "마비노기 모바일",
            frame: CGRect(x: -1512, y: 203, width: 1512, height: 877),
            isOnScreen: true,
            processLifetimeIdentity: try ProcessLifetimeIdentity(
                launchTimeIntervalSinceReferenceDate: 123
            )
        ),
        layout: .landscape
    )

    #expect(validated?.ruleID == "deselect_challenge")
}
