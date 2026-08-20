import CoreGraphics
import Foundation

@testable import MAgentRuntime

/// 전리품 수집 구간을 여는 앵커 두 개.
///
/// 수집 구간은 화면 비율이 아니라 `발견한 전리품`과 아래 첫 버튼 사이로
/// 잡는다. 실제 결과 화면엔 늘 이 둘이 있으므로, 전리품을 다루는 테스트도
/// 같은 조건을 갖춰야 한다. 앵커가 없으면 아무것도 모으지 않는 게 맞다 —
/// 어림짐작으로 모으면 버튼과 안내문이 전리품으로 섞인다.
func lootBandAnchors(
    headerY: Double = 400,
    footerY: Double = 800
) -> [RecognizedTextObservation] {
    [
        RecognizedTextObservation(
            text: "발견한 전리품",
            confidence: 1,
            boundingBox: CGRect(x: 700, y: headerY, width: 120, height: 25)
        ),
        RecognizedTextObservation(
            text: "다시 하기",
            confidence: 1,
            boundingBox: CGRect(x: 700, y: footerY, width: 100, height: 29)
        ),
    ]
}
