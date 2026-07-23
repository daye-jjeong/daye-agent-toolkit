# Background Automator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a native macOS menu bar app that recognizes an extensible sequence of states in a background Mabinogi Mobile window and safely clicks only validated actions without moving the user's pointer or stealing focus.

**Architecture:** A Swift Package separates pure rule/state-machine logic from macOS runtime adapters for ScreenCaptureKit, Vision, CoreGraphics, permissions, and the menu bar UI. A JSON-driven engine captures only the target window, evaluates OCR/image/color detectors, revalidates immediately before each click, and pauses on any unexpected state. Implementation is gated by a small probe that must prove background capture and `CGEvent.postToPid` behavior against the live game before full app work proceeds.

**Tech Stack:** Swift 6, SwiftUI `MenuBarExtra`, ScreenCaptureKit, Vision, CoreGraphics, ApplicationServices, XCTest, Swift Package Manager, ad-hoc app bundle signing

---

## Before implementation

- Read the approved design: `docs/plans/2026-07-23-background-automator-design.md`.
- Create a dedicated worktree and branch from the commit containing this plan.
- Use TDD for every new core function.
- Do not continue past Task 3 unless the live game probe preserves the physical pointer and foreground app.
- Do not automate `장면 넘기기`.
- Do not add process-memory access, packet inspection, or anti-cheat bypasses.

Suggested worktree setup:

```bash
git worktree add ../daye-agent-toolkit-background-automator -b feat/background-automator
cd ../daye-agent-toolkit-background-automator
```

Expected: a clean worktree on `feat/background-automator`.

### Task 1: Scaffold the Swift package

**Files:**
- Create: `apps/background-automator/Package.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/BackgroundAutomatorCore.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/BackgroundAutomatorRuntime.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/Resources/default-rules.json`
- Create: `apps/background-automator/Sources/BackgroundAutomatorProbe/main.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorApp/BackgroundAutomatorApp.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorCoreTests/SmokeTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/SmokeTests.swift`

**Step 1: Write the package manifest**

Create `apps/background-automator/Package.swift`:

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "BackgroundAutomator",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "BackgroundAutomatorCore", targets: ["BackgroundAutomatorCore"]),
        .library(name: "BackgroundAutomatorRuntime", targets: ["BackgroundAutomatorRuntime"]),
        .executable(name: "BackgroundAutomatorProbe", targets: ["BackgroundAutomatorProbe"]),
        .executable(name: "BackgroundAutomatorApp", targets: ["BackgroundAutomatorApp"]),
    ],
    targets: [
        .target(name: "BackgroundAutomatorCore"),
        .target(
            name: "BackgroundAutomatorRuntime",
            dependencies: ["BackgroundAutomatorCore"],
            resources: [.process("Resources")]
        ),
        .executableTarget(
            name: "BackgroundAutomatorProbe",
            dependencies: ["BackgroundAutomatorRuntime"]
        ),
        .executableTarget(
            name: "BackgroundAutomatorApp",
            dependencies: ["BackgroundAutomatorRuntime"]
        ),
        .testTarget(
            name: "BackgroundAutomatorCoreTests",
            dependencies: ["BackgroundAutomatorCore"]
        ),
        .testTarget(
            name: "BackgroundAutomatorRuntimeTests",
            dependencies: ["BackgroundAutomatorRuntime"]
        ),
    ]
)
```

**Step 2: Add the smallest compilable targets**

Use public marker values for the two libraries, an argument-printing probe, and a minimal `MenuBarExtra` app:

Create the initial runtime resource as `{"version":1,"rules":[]}` so the package resource path exists from the first build.

```swift
// BackgroundAutomatorCore.swift
public enum BackgroundAutomatorCore {
    public static let version = "0.1.0"
}
```

```swift
// BackgroundAutomatorRuntime.swift
import BackgroundAutomatorCore

public enum BackgroundAutomatorRuntime {
    public static let version = BackgroundAutomatorCore.version
}
```

```swift
// BackgroundAutomatorProbe/main.swift
import BackgroundAutomatorRuntime

print("BackgroundAutomatorProbe \(BackgroundAutomatorRuntime.version)")
```

```swift
// BackgroundAutomatorApp/BackgroundAutomatorApp.swift
import AppKit
import SwiftUI

@main
struct BackgroundAutomatorApp: App {
    var body: some Scene {
        MenuBarExtra("Background Automator", systemImage: "cursorarrow.click.2") {
            Text("준비 중")
            Divider()
            Button("종료") { NSApplication.shared.terminate(nil) }
        }
    }
}
```

**Step 3: Write smoke tests**

```swift
import XCTest
@testable import BackgroundAutomatorCore

final class SmokeTests: XCTestCase {
    func testVersionIsStable() {
        XCTAssertEqual(BackgroundAutomatorCore.version, "0.1.0")
    }
}
```

Write the equivalent runtime test for `BackgroundAutomatorRuntime.version`.

**Step 4: Build and test**

Run:

```bash
cd apps/background-automator
swift test
swift build --product BackgroundAutomatorProbe
swift run BackgroundAutomatorProbe
```

Expected:

- `swift test` passes two smoke tests.
- Probe prints `BackgroundAutomatorProbe 0.1.0`.

**Step 5: Commit**

```bash
git add apps/background-automator
git commit -m "chore: scaffold background automator"
```

### Task 2: Implement target-window discovery and background capture probe

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/WindowTarget.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/WindowCaptureService.swift`
- Modify: `apps/background-automator/Sources/BackgroundAutomatorProbe/main.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/WindowTargetTests.swift`

**Step 1: Write failing target-selection tests**

Define a platform-independent candidate:

```swift
struct WindowCandidate: Equatable, Sendable {
    let windowID: UInt32
    let processID: Int32
    let bundleIdentifier: String
    let title: String
    let frame: CGRect
    let isOnScreen: Bool
}
```

Test that selection:

- requires exact bundle ID;
- requires `titleContains`;
- rejects `isOnScreen == false`;
- chooses the largest matching window when wrappers expose duplicates.

Example:

```swift
func testSelectsLargestVisibleMatchingWindow() throws {
    let candidates = [
        WindowCandidate(
            windowID: 1,
            processID: 10,
            bundleIdentifier: "com.nexon.devcat.mm",
            title: "마비노기 모바일",
            frame: CGRect(x: 0, y: 0, width: 300, height: 200),
            isOnScreen: true
        ),
        WindowCandidate(
            windowID: 2,
            processID: 10,
            bundleIdentifier: "com.nexon.devcat.mm",
            title: "마비노기 모바일",
            frame: CGRect(x: 0, y: 0, width: 1224, height: 768),
            isOnScreen: true
        ),
    ]

    let selected = try WindowTarget.select(
        from: candidates,
        bundleIdentifier: "com.nexon.devcat.mm",
        titleContains: "마비노기"
    )

    XCTAssertEqual(selected.windowID, 2)
}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
swift test --filter WindowTargetTests
```

Expected: FAIL because `WindowTarget` does not exist.

**Step 3: Implement target selection**

Create `WindowTarget.select` as a pure function:

```swift
public enum WindowTargetError: Error, Equatable {
    case notFound
}

public enum WindowTarget {
    public static func select(
        from candidates: [WindowCandidate],
        bundleIdentifier: String,
        titleContains: String
    ) throws -> WindowCandidate {
        let matches = candidates.filter {
            $0.bundleIdentifier == bundleIdentifier
                && $0.title.localizedCaseInsensitiveContains(titleContains)
                && $0.isOnScreen
                && $0.frame.width > 0
                && $0.frame.height > 0
        }
        guard let result = matches.max(by: {
            $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height
        }) else {
            throw WindowTargetError.notFound
        }
        return result
    }
}
```

**Step 4: Add the ScreenCaptureKit adapter**

Implement:

```swift
public protocol WindowCapturing: Sendable {
    func findWindow(
        bundleIdentifier: String,
        titleContains: String
    ) async throws -> WindowCandidate

    func capture(windowID: UInt32) async throws -> CGImage
}
```

Production behavior:

- call `SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)`;
- map `SCWindow` values into `WindowCandidate`;
- filter by the owning application's bundle ID and title;
- create `SCContentFilter(desktopIndependentWindow:)`;
- configure `showsCursor = false`;
- use the window frame dimensions for output;
- call `SCScreenshotManager.captureImage`.

**Step 5: Add probe commands**

Support:

```text
BackgroundAutomatorProbe list
BackgroundAutomatorProbe capture --bundle-id <id> --title <text> --output <path>
```

The probe must print the selected window ID, PID, frame, and output path without printing unrelated window titles.

**Step 6: Test and perform the live capture check**

Run:

```bash
swift test --filter WindowTargetTests
swift run BackgroundAutomatorProbe list
swift run BackgroundAutomatorProbe capture \
  --bundle-id com.nexon.devcat.mm \
  --title "마비노기" \
  --output /tmp/background-automator-game.png
```

Expected:

- unit tests pass;
- `/tmp/background-automator-game.png` contains the game window;
- move another app in front and repeat;
- the second capture still contains the unobscured game window;
- minimize the game and verify the probe reports `notFound` or `notOnScreen`.

If background capture fails, stop and revise the design before Task 3.

**Step 7: Commit**

```bash
git add apps/background-automator
git commit -m "feat: capture target window in background"
```

### Task 3: Prove process-targeted clicks preserve pointer and focus

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ClickService.swift`
- Modify: `apps/background-automator/Sources/BackgroundAutomatorProbe/main.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/CoordinateConverterTests.swift`

**Step 1: Write failing coordinate-conversion tests**

Use normalized window coordinates with origin at the captured image's top-left:

```swift
func testConvertsNormalizedWindowPointToScreenPoint() throws {
    let frame = CGRect(x: 100, y: 200, width: 1200, height: 800)
    let point = try CoordinateConverter.screenPoint(
        normalizedX: 0.5,
        normalizedY: 0.75,
        windowFrame: frame
    )

    XCTAssertEqual(point.x, 700, accuracy: 0.001)
    XCTAssertEqual(point.y, 800, accuracy: 0.001)
}
```

Add rejection tests for values outside `0...1`.

**Step 2: Run the tests to verify they fail**

Run:

```bash
swift test --filter CoordinateConverterTests
```

Expected: FAIL because `CoordinateConverter` is missing.

**Step 3: Implement coordinate conversion**

```swift
public enum CoordinateError: Error, Equatable {
    case outOfRange
}

public enum CoordinateConverter {
    public static func screenPoint(
        normalizedX: Double,
        normalizedY: Double,
        windowFrame: CGRect
    ) throws -> CGPoint {
        guard (0...1).contains(normalizedX), (0...1).contains(normalizedY) else {
            throw CoordinateError.outOfRange
        }
        return CGPoint(
            x: windowFrame.minX + normalizedX * windowFrame.width,
            y: windowFrame.minY + normalizedY * windowFrame.height
        )
    }
}
```

**Step 4: Implement the click adapter**

```swift
public protocol Clicking: Sendable {
    func click(processID: pid_t, screenPoint: CGPoint) throws
}

public struct ProcessClickService: Clicking {
    public init() {}

    public func click(processID: pid_t, screenPoint: CGPoint) throws {
        guard let source = CGEventSource(stateID: .hidSystemState),
              let down = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseDown,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
              ),
              let up = CGEvent(
                mouseEventSource: source,
                mouseType: .leftMouseUp,
                mouseCursorPosition: screenPoint,
                mouseButton: .left
              ) else {
            throw ClickError.cannotCreateEvent
        }
        down.postToPid(processID)
        up.postToPid(processID)
    }
}
```

Do not call `NSRunningApplication.activate`, `CGEvent.post(tap:)`, or APIs that globally move the pointer.

**Step 5: Add a guarded probe command**

Support:

```text
BackgroundAutomatorProbe click \
  --bundle-id <id> \
  --title <text> \
  --x <0...1> \
  --y <0...1>
```

The probe must:

1. capture the target window;
2. print the target PID, window frame, and computed point;
3. wait for explicit terminal confirmation `CLICK`;
4. send one click;
5. capture an after image for verification.

**Step 6: Run the live technical gate**

Set up a safe game screen with a known, reversible button. Keep Codex or another text editor in front.

Record:

- physical mouse position before the click;
- frontmost app before the click;
- physical mouse position after the click;
- frontmost app after the click;
- before/after game captures.

Run:

```bash
swift run BackgroundAutomatorProbe click \
  --bundle-id com.nexon.devcat.mm \
  --title "마비노기" \
  --x 0.50 \
  --y 0.92
```

Pass conditions:

- the intended game action occurs;
- the physical pointer does not move;
- the foreground app does not change;
- only one click is delivered.

Fail conditions:

- no game action;
- pointer moves;
- focus changes;
- a different control receives the click.

**HARD GATE:** If any fail condition occurs, stop. Document the exact result in the design, and evaluate a separate VM/session. Do not continue to Task 4.

**Step 7: Commit**

```bash
git add apps/background-automator
git commit -m "feat: prove background process clicks"
```

### Task 4: Define and validate the JSON rule model

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/RuleModels.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/RuleValidator.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/RuleLoader.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorCoreTests/RuleLoaderTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorCoreTests/RuleValidatorTests.swift`

**Step 1: Write failing decode and validation tests**

Cover:

- supported schema version;
- unique state IDs;
- valid initial state;
- every `next` state exists;
- intervals and timeouts are positive;
- detector IDs are unique within a state;
- click actions reference an existing detector or a valid normalized point;
- terminal/error states may omit `next`;
- malformed JSON reports a user-facing error.

Minimal fixture:

```swift
let json = """
{
  "version": 1,
  "rules": [{
    "id": "mabinogi-deep-dungeon-repeat",
    "enabled": true,
    "target": {
      "bundleIdentifier": "com.nexon.devcat.mm",
      "windowTitleContains": "마비노기"
    },
    "initialState": "RUNNING_COOLDOWN",
    "states": [{
      "id": "RUNNING_COOLDOWN",
      "initialDelay": 60,
      "pollInterval": 3,
      "timeout": 300,
      "detectors": [],
      "match": "all",
      "action": {"type": "none"},
      "next": "RUNNING_SCAN",
      "onFailure": "pause"
    }, {
      "id": "RUNNING_SCAN",
      "pollInterval": 3,
      "timeout": 300,
      "detectors": [{
        "id": "touch",
        "type": "text",
        "text": "화면을 터치해 주세요"
      }],
      "match": "all",
      "action": {"type": "clickMatch", "detectorID": "touch"},
      "next": "WAIT_REWARD",
      "afterDelay": 2,
      "verifyBeforeAction": true,
      "onFailure": "pause"
    }]
  }]
}
"""
```

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter RuleLoaderTests
swift test --filter RuleValidatorTests
```

Expected: FAIL because model and validator types are missing.

**Step 3: Implement Codable models**

Use simple discriminators rather than custom enum decoding:

```swift
public struct AutomationConfig: Codable, Sendable {
    public let version: Int
    public let rules: [AutomationRule]
}

public struct AutomationRule: Codable, Sendable {
    public let id: String
    public let enabled: Bool
    public let target: TargetRule
    public let initialState: String
    public let states: [StateRule]
}

public struct TargetRule: Codable, Sendable {
    public let bundleIdentifier: String
    public let windowTitleContains: String
}

public struct StateRule: Codable, Sendable {
    public let id: String
    public let initialDelay: Double?
    public let pollInterval: Double
    public let timeout: Double
    public let detectors: [DetectorRule]
    public let match: MatchMode
    public let action: ActionRule
    public let next: String?
    public let afterDelay: Double?
    public let verifyBeforeAction: Bool?
    public let onFailure: FailurePolicy
}
```

`DetectorRule` contains optional fields selected by `type`: `text`, `template`, `region`, `color`, `threshold`.
`ActionRule` contains `type`, optional `detectorID`, and optional normalized point.

**Step 4: Implement validation and loading**

`RuleLoader.decode(data:)` decodes JSON and calls `RuleValidator.validate`.
Return typed errors with a concise path such as:

```text
rules[0].states[1].action.detectorID references missing detector "foo"
```

**Step 5: Run tests**

Run:

```bash
swift test --filter RuleLoaderTests
swift test --filter RuleValidatorTests
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/background-automator
git commit -m "feat: add validated automation rules"
```

### Task 5: Build the pure state machine

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/StateMachine.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/Observation.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorCoreTests/StateMachineTests.swift`

**Step 1: Write failing state-machine tests**

Model detector results separately from screen processing:

```swift
public struct DetectionResult: Equatable, Sendable {
    public let detectorID: String
    public let matched: Bool
    public let confidence: Double
    public let normalizedBounds: CGRect?
}

public enum StateDecision: Equatable, Sendable {
    case wait
    case perform(ActionRequest)
    case transition(String)
    case pause(String)
}
```

Test:

- `all` requires every detector;
- `any` requires at least one detector;
- a no-action cooldown transitions only after its delay;
- a matched action returns exactly one action request;
- the same state action cannot fire twice in one cycle;
- timeout returns `.pause`;
- successful entry resets the cycle action set.

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter StateMachineTests
```

Expected: FAIL because `StateMachine` is missing.

**Step 3: Implement the minimal pure state machine**

The state machine owns:

- current state ID;
- state entry time;
- action IDs executed in the current cycle;
- last decision;
- transition history.

It does not capture screens, sleep, or click.

**Step 4: Run tests**

Run:

```bash
swift test --filter StateMachineTests
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/background-automator
git commit -m "feat: add automation state machine"
```

### Task 6: Implement OCR, image, and color detectors

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ScreenDetector.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/VisionTextDetector.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/TemplateImageDetector.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ColorRegionDetector.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/NormalizedGeometry.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/NormalizedGeometryTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/ColorRegionDetectorTests.swift`

**Step 1: Write failing geometry and color tests**

Test Vision's bottom-left normalized coordinates to top-left window coordinates:

```swift
func testConvertsVisionBoundsToTopLeftCoordinates() {
    let vision = CGRect(x: 0.2, y: 0.1, width: 0.4, height: 0.2)
    let converted = NormalizedGeometry.topLeftRect(fromVisionRect: vision)
    XCTAssertEqual(converted, CGRect(x: 0.2, y: 0.7, width: 0.4, height: 0.2))
}
```

For the color detector, create an in-memory 10×10 image and verify mean-color tolerance inside a normalized region.

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter NormalizedGeometryTests
swift test --filter ColorRegionDetectorTests
```

Expected: FAIL.

**Step 3: Implement `VisionTextDetector`**

Use:

```swift
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = false
request.customWords = configuredTexts
```

Return the best candidate, confidence, and normalized bounds. Normalize whitespace so `다시 하기` and accidental repeated spaces compare consistently, but do not remove meaningful characters.

**Step 4: Implement image and color detection**

- Template detector: crop the configured region and use `VNGenerateImageFeaturePrintRequest`; match when feature-print distance is below the configured threshold.
- Color detector: compute mean RGB in the configured region and compare with per-channel tolerance.
- Keep both behind `ScreenDetector`.

**Step 5: Run tests**

Run:

```bash
swift test --filter NormalizedGeometryTests
swift test --filter ColorRegionDetectorTests
swift test
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/background-automator
git commit -m "feat: detect text images and colors"
```

### Task 7: Add click revalidation and runtime orchestration

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/AutomationEngine.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ActionExecutor.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/Sleeper.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/AutomationEngineTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/ActionExecutorTests.swift`

**Step 1: Write failing tests with mocks**

Create mocks for capture, detection, click, and sleep.

Required tests:

- dry run records an intended action but never calls click;
- stale revalidation cancels the action;
- successful revalidation clicks once;
- after-delay is honored before the next capture;
- unknown screen produces no click;
- target window missing moves to waiting;
- target window minimized produces no click;
- expected next state missing by timeout pauses the engine;
- stop cancels outstanding sleep and prevents later click.

Key stale-state test:

```swift
func testDoesNotClickWhenStateDisappearsDuringRevalidation() async throws {
    let detector = MockDetector(results: [
        [.matched(id: "retry")],
        [.notMatched(id: "retry")],
    ])
    let clicker = MockClicker()
    let engine = makeEngine(detector: detector, clicker: clicker)

    await engine.tick()

    XCTAssertEqual(clicker.clicks.count, 0)
    XCTAssertEqual(await engine.status, .waiting)
}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter AutomationEngineTests
swift test --filter ActionExecutorTests
```

Expected: FAIL.

**Step 3: Implement the actor-based engine**

`AutomationEngine` is an actor and owns exactly one loop task.

Execution order:

1. honor initial delay;
2. find and capture target window;
3. detect current-state conditions;
4. ask pure state machine for a decision;
5. for an action, capture and detect again;
6. cancel if the second observation differs;
7. in dry run, log only;
8. otherwise send one click;
9. honor after-delay;
10. transition and continue.

Use a `Sleeper` protocol so tests never wait in real time.

**Step 4: Run tests**

Run:

```bash
swift test --filter AutomationEngineTests
swift test --filter ActionExecutorTests
swift test
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/background-automator
git commit -m "feat: orchestrate safe automation actions"
```

### Task 8: Add the first Mabinogi rule

**Files:**
- Modify: `apps/background-automator/Sources/BackgroundAutomatorRuntime/Resources/default-rules.json`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/DefaultRules.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/DefaultRuleTests.swift`

**Step 1: Write a failing default-rule test**

The test loads the bundled fixture and asserts the exact state sequence:

```text
RUNNING_COOLDOWN
RUNNING_SCAN
CLEAR_RESULT
WAIT_REWARD
REWARD
CONTINUE_CONFIRM
DUNGEON_SELECT
ENTER_READY
RUNNING_COOLDOWN
```

Also assert:

- no detector or action contains `장면 넘기기`;
- `CLEAR_RESULT.afterDelay == 2`;
- `RUNNING_COOLDOWN.initialDelay == 60`;
- `RUNNING_SCAN.pollInterval == 3`;
- every clickable state uses `verifyBeforeAction == true`.

**Step 2: Run the test to verify it fails**

Run:

```bash
swift test --filter DefaultRuleTests
```

Expected: FAIL because the default rule is absent.

**Step 3: Create the rule**

Use the approved screen combinations:

- `CLEAR_RESULT`: `던전 클리어!` + `화면을 터치해 주세요`;
- `REWARD`: `나가기` + `다시 하기` + `다음 구역으로`;
- `CONTINUE_CONFIRM`: dialog title + `계속하기` + `나가기`;
- `DUNGEON_SELECT`: dungeon title + `선택됨`;
- `ENTER_READY`: gray-selection template/color + active `입장하기`.

Use OCR match-bound clicks where text exists. Use a normalized safe point only for the initial touch and only while both clear-result texts are present.

Expose `DefaultRules.load()` from the runtime library. It reads `default-rules.json` through `Bundle.module`, decodes it with `RuleLoader`, and is the only production entry point for the bundled default.

**Step 4: Run tests**

Run:

```bash
swift test --filter DefaultRuleTests
swift test
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/background-automator
git commit -m "feat: add Mabinogi dungeon repeat rule"
```

### Task 9: Add permissions, app support files, and logs

**Files:**
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/PermissionService.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/AppSupport.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/EventLog.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/AppSupportTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/EventLogTests.swift`

**Step 1: Write failing path and logging tests**

Test:

- app support root ends with `BackgroundAutomator`;
- default rule is copied only when no user rule exists;
- rule reload does not overwrite user changes;
- log records timestamp, rule, state, event, and message;
- screenshots are not written unless error capture is enabled.

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter AppSupportTests
swift test --filter EventLogTests
```

Expected: FAIL.

**Step 3: Implement permissions**

Screen capture:

```swift
CGPreflightScreenCaptureAccess()
CGRequestScreenCaptureAccess()
```

Accessibility:

```swift
AXIsProcessTrustedWithOptions([
    kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true
] as CFDictionary)
```

Do not start the engine unless both permissions are available.

**Step 4: Implement app support and logging**

Use:

```text
~/Library/Application Support/BackgroundAutomator/rules.json
~/Library/Application Support/BackgroundAutomator/templates/
~/Library/Logs/BackgroundAutomator/events.jsonl
```

Write logs atomically and redact unrelated OCR text. Store only detector IDs and configured matched strings.

**Step 5: Run tests**

Run:

```bash
swift test --filter AppSupportTests
swift test --filter EventLogTests
swift test
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/background-automator
git commit -m "feat: add permissions settings and logs"
```

### Task 10: Build the menu bar UI

**Files:**
- Modify: `apps/background-automator/Sources/BackgroundAutomatorApp/BackgroundAutomatorApp.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/AppModel.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorApp/MenuBarContent.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/AppModelTests.swift`

**Step 1: Write failing model tests**

Test:

- start is disabled without permissions;
- start changes status to scanning;
- stop cancels the engine;
- dry run never enables real clicks;
- reload reports validation errors without replacing the active valid config;
- paused error state exposes a resume action only after the error is cleared.

**Step 2: Run tests to verify they fail**

Run:

```bash
swift test --filter AppModelTests
```

Expected: FAIL.

**Step 3: Implement `AppModel`**

Implement `AppModel` in the runtime library so the test target can exercise it without importing the executable target. Expose:

```swift
@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var status: AutomationStatus = .stopped
    @Published private(set) var lastEvent: String = "실행되지 않음"
    @Published var dryRun = true

    func start()
    func stop()
    func reloadRules()
    func openRules()
    func openLogs()
    func requestPermissions()
}
```

**Step 4: Implement the menu**

Show:

- status icon and Korean status text;
- `드라이런` toggle;
- `자동화 시작`;
- `즉시 중지`;
- current rule and state;
- recent event;
- `설정 다시 불러오기`;
- `설정 파일 열기`;
- `로그 열기`;
- permission status and request action;
- `종료`.

Automation must start stopped on every app launch.

**Step 5: Run tests and launch**

Run:

```bash
swift test --filter AppModelTests
swift run BackgroundAutomatorApp
```

Expected: menu bar item appears and starts in stopped, dry-run mode.

**Step 6: Commit**

```bash
git add apps/background-automator
git commit -m "feat: add automation menu bar controls"
```

### Task 11: Package a stable `.app` bundle

**Files:**
- Create: `apps/background-automator/Resources/Info.plist`
- Create: `apps/background-automator/scripts/build-app.sh`
- Create: `apps/background-automator/scripts/install-app.sh`
- Create: `apps/background-automator/Tests/Packaging/test_app_bundle.sh`

**Step 1: Write the failing packaging test**

Verify:

- executable exists;
- `CFBundleIdentifier` is stable;
- `LSUIElement` is true;
- screen capture usage description exists;
- app is ad-hoc signed;
- resources include `default-rules.json`.

**Step 2: Run the test to verify it fails**

Run:

```bash
bash Tests/Packaging/test_app_bundle.sh
```

Expected: FAIL because the bundle does not exist.

**Step 3: Add `Info.plist`**

Use stable values:

```xml
<key>CFBundleIdentifier</key>
<string>com.daye.background-automator</string>
<key>CFBundleName</key>
<string>Background Automator</string>
<key>CFBundleExecutable</key>
<string>BackgroundAutomatorApp</string>
<key>LSUIElement</key>
<true/>
<key>NSScreenCaptureUsageDescription</key>
<string>선택한 앱 창의 상태를 인식해 사용자가 설정한 자동화를 실행합니다.</string>
```

**Step 4: Build and sign**

`build-app.sh` must:

1. run `swift build -c release --product BackgroundAutomatorApp`;
2. create `build/Background Automator.app/Contents/MacOS`;
3. copy the release executable;
4. copy `Info.plist` and the SwiftPM runtime resource bundle;
5. run `codesign --force --deep --sign -`;
6. print the final absolute path.

`install-app.sh` copies only this exact bundle to `/Applications/Background Automator.app` after confirming the source exists.

**Step 5: Run packaging tests**

Run:

```bash
bash scripts/build-app.sh
bash Tests/Packaging/test_app_bundle.sh
codesign --verify --deep --strict "build/Background Automator.app"
```

Expected: all commands succeed.

**Step 6: Commit**

```bash
git add apps/background-automator
git commit -m "build: package background automator app"
```

### Task 12: Capture fixtures and verify dry run

**Files:**
- Create: `apps/background-automator/Tests/Fixtures/README.md`
- Create: `apps/background-automator/Tests/Fixtures/clear-result.png`
- Create: `apps/background-automator/Tests/Fixtures/reward.png`
- Create: `apps/background-automator/Tests/Fixtures/continue-confirm.png`
- Create: `apps/background-automator/Tests/Fixtures/dungeon-selected.png`
- Create: `apps/background-automator/Tests/Fixtures/enter-ready.png`
- Create: `apps/background-automator/Tests/Fixtures/unknown-currency.png`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/MabinogiFixtureTests.swift`

**Step 1: Capture only the target window**

Use the probe capture command for each approved state. Do not capture the full desktop.
Review every image before committing to ensure it contains no private chat or unrelated personal information.

**Step 2: Write failing fixture classification tests**

Assert:

- combat is not actionable;
- clear result matches only `CLEAR_RESULT`;
- cutscene is not actionable;
- reward matches `REWARD`;
- confirmation matches `CONTINUE_CONFIRM`;
- selected and gray states are distinct;
- the accidental currency screen is unknown and produces no action.

**Step 3: Run tests to verify any missing detector fails**

Run:

```bash
swift test --filter MabinogiFixtureTests
```

Expected: FAIL until thresholds and regions are calibrated.

**Step 4: Adjust configuration, not detector code**

Calibrate:

- OCR custom words;
- normalized regions;
- image thresholds;
- color thresholds.

Do not add screen-specific conditionals to Swift source.

**Step 5: Run the full suite**

Run:

```bash
swift test
```

Expected: PASS.

**Step 6: Run a two-cycle dry run**

Start the packaged app in dry-run mode. Confirm logs show:

```text
RUNNING_COOLDOWN
RUNNING_SCAN
CLEAR_RESULT
WAIT_REWARD
REWARD
CONTINUE_CONFIRM
DUNGEON_SELECT
ENTER_READY
RUNNING_COOLDOWN
```

No click events may be sent in dry run.

**Step 7: Commit**

```bash
git add apps/background-automator
git commit -m "test: verify Mabinogi screen states"
```

### Task 13: Perform live end-to-end verification and document usage

**Files:**
- Create: `apps/background-automator/README.md`
- Modify: `README.md`
- Modify: `docs/plans/2026-07-23-background-automator-design.md`

**Step 1: Write usage documentation**

Document:

- build and install;
- required permissions;
- start, stop, and dry-run;
- target window must remain non-minimized;
- rule and template paths;
- logs;
- recovery from paused state;
- how to add a new rule;
- explicit exclusion of `장면 넘기기`;
- game policy caveat and no anti-cheat bypass.

**Step 2: Run the live test with the user working in another app**

Checklist:

- app starts stopped;
- permissions are granted;
- dry run sees the expected sequence;
- real mode performs one full cycle;
- pointer does not move;
- foreground app does not change;
- `장면 넘기기` is ignored;
- reward screen is reached passively;
- retry, continue, deselect, and enter occur in order;
- unexpected screen pauses the engine;
- menu `즉시 중지` prevents all later clicks.

**Step 3: Run a second cycle**

Verify state and duplicate-action tracking reset after re-entry.

**Step 4: Run final automated checks**

Run:

```bash
cd apps/background-automator
swift test
bash scripts/build-app.sh
bash Tests/Packaging/test_app_bundle.sh
codesign --verify --deep --strict "build/Background Automator.app"
git diff --check
git status --short
```

Expected:

- all tests pass;
- app bundle verification succeeds;
- `git diff --check` is empty;
- only intentional documentation changes remain before commit.

**Step 5: Commit**

```bash
git add README.md apps/background-automator docs/plans/2026-07-23-background-automator-design.md
git commit -m "docs: add background automator usage"
```

## Final handoff

Do not claim completion from unit tests alone. The proving surface is:

1. live target-window capture while obscured;
2. live game click delivered with pointer and foreground app preserved;
3. two-cycle dry run;
4. two-cycle live run;
5. packaged `.app` launched from `/Applications`.

If the live click technical gate fails, report the exact failing condition and stop before building the menu app.
