import Foundation

/// 화면이 실제로 흐르고 있는지 본다.
///
/// 정지 판정을 '클릭이 없었다'로 하면 전투가 긴 던전에서 오탐이 난다.
/// 실측(2026-07-30): 북쪽 폐허 심층 2층은 전투만 평균 118초, 최대 241초라
/// 임계값 150초를 그대로 넘긴다. 앱은 멀쩡히 기다리는 중인데 '확인 필요'가
/// 떴다. 던전마다 임계값을 맞추는 건 끝이 없고, 게임 UI 문구로 '전투 중'을
/// 판별하면 화면 구성이 바뀔 때마다 다시 깨진다.
///
/// 대신 화면이 흐르는지를 본다. 전투 중에는 체력·알림·길드 채팅이 계속
/// 바뀌어 인식 결과가 매 프레임 달라진다. 반대로 진짜로 굳은 화면은
/// 좌표까지 한 자리도 안 움직인다(실측: 멈춘 세 화면 모두 후보 박스가
/// x=694.4 y=370.3으로 소수점까지 동일했다).
public struct ScreenActivityTracker: Sendable {
    private var previous: [String]?

    public init() {}

    /// 이번 관찰이 직전과 다르면 true. 첫 관찰은 비교 대상이 없으므로
    /// 움직인 것으로 친다 — 시작하자마자 멈춤으로 몰지 않는다.
    public mutating func noteTexts(_ texts: [String]) -> Bool {
        // 자리는 보지 않는다. OCR이 소수점 아래를 흔들어 대는데, 그걸
        // 반올림해 걸러도 경계값(793.47 → 793, 793.51 → 794)이 남아서
        // 굳은 화면이 계속 움직이는 것처럼 보인다. 글자만으로 충분하다 —
        // 전투 중에는 알림·길드 채팅·체력이 계속 바뀌고, 굳은 화면은
        // 글자도 그대로다.
        let current = texts.sorted()
        defer { previous = current }
        guard let previous else {
            return true
        }
        return current != previous
    }
}
