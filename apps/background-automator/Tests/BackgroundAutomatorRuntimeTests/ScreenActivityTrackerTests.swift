import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func theFirstObservationCountsAsMovement() {
    // 비교 대상이 없다. 시작하자마자 멈춤으로 몰면 안 된다.
    var tracker = ScreenActivityTracker()
    let moved = tracker.noteTexts(["체력 100"])
    #expect(moved)
}

@Test
func anIdenticalScreenIsNotMovement() {
    // 굳은 화면은 글자가 그대로다(실측: 멈춘 세 화면 모두 인식 결과가
    // 프레임마다 똑같았다).
    var tracker = ScreenActivityTracker()
    let frame = ["발견한 전리품", "마물 퇴치 증표"]

    _ = tracker.noteTexts(frame)

    let second = tracker.noteTexts(frame)
    let third = tracker.noteTexts(frame)
    #expect(!second)
    #expect(!third)
}

@Test
func changedTextIsMovement() {
    // 전투 중에는 알림·채팅·체력이 계속 바뀐다.
    var tracker = ScreenActivityTracker()
    _ = tracker.noteTexts(["체력 100"])

    let moved = tracker.noteTexts(["체력 82"])
    #expect(moved)
}

@Test
func aDisappearingTextIsMovement() {
    var tracker = ScreenActivityTracker()
    _ = tracker.noteTexts([
        "발견한 전리품",
        "다시 하기",
    ])

    let moved = tracker.noteTexts(["발견한 전리품"])
    #expect(moved)
}

@Test
func orderFromTheRecognizerDoesNotMatter() {
    // OCR이 같은 화면을 다른 순서로 돌려주기도 한다. 그걸 변화로 세면
    // 굳은 화면이 계속 움직이는 것처럼 보인다.
    var tracker = ScreenActivityTracker()
    let first = "발견한 전리품"
    let second = "마물 퇴치 증표"

    _ = tracker.noteTexts([first, second])

    let moved = tracker.noteTexts([second, first])
    #expect(!moved)
}
