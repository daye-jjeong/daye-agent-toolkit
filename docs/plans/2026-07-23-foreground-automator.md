# Foreground Game Automator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a macOS menu-bar automator that observes Mabinogi Mobile in the background, waits for three seconds of user inactivity, temporarily foregrounds the game to click a freshly detected UI element, and restores the original app and pointer.

**Architecture:** Keep ScreenCaptureKit window capture and identity validation as the observation boundary. Add Vision-based semantic UI detection, a screen-derived state machine, a passive user-input monitor, and a serialized foreground action coordinator that activates, clicks, and restores. Every action is fail-safe: two stable observations, an idle gate, a final capture, and exact window/button revalidation are required.

**Tech Stack:** Swift 6, SwiftUI `MenuBarExtra`, AppKit, ScreenCaptureKit, Vision, CoreGraphics, ApplicationServices Accessibility, XCTest, JSON resources.

---

## Existing foundation

The worktree already contains:

- a Swift package and menu-bar executable;
- ScreenCaptureKit capture for covered windows;
- public CoreGraphics and Accessibility minimized-window validation;
- identity-bound capture that rejects PID/window reuse;
- normalized coordinate conversion and process-click probes;
- 41 passing tests at baseline.

Do not remove the documented failed background-click probe. Production automation must use the explicit foreground action path added by this plan.

### Baseline command

```bash
cd apps/background-automator
swift test
```

Expected: `41 tests` pass before new work.

## Task 1: Define semantic rules and layout profiles

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/AutomationRule.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/LayoutProfile.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/RuleLoader.swift`
- Modify: `apps/background-automator/Sources/BackgroundAutomatorRuntime/Resources/default-rules.json`
- Create: `apps/background-automator/Tests/BackgroundAutomatorCoreTests/AutomationRuleTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/RuleLoaderTests.swift`

### Step 1: Write failing model and decoding tests

Cover:

- `landscape`, `portraitMobile`, and `unsupported` layouts;
- required and forbidden OCR texts;
- a semantic action target;
- search-region variants per layout;
- minimum OCR confidence;
- stable observation count;
- post-action delay and cooldown;
- unknown fields rejected by schema version.

Example:

```swift
func testDecodesPortraitRetryRule() throws {
    let rules = try RuleLoader().loadDefaultRules()
    let retry = try XCTUnwrap(rules.first { $0.id == "reward_retry" })

    XCTAssertEqual(retry.action.targetText, "다시 하기")
    XCTAssertNotNil(retry.regions[.portraitMobile])
    XCTAssertEqual(retry.stableObservationCount, 2)
}
```

### Step 2: Run tests and verify RED

```bash
swift test --filter AutomationRuleTests
swift test --filter RuleLoaderTests
```

Expected: compilation fails because the models and loader do not exist.

### Step 3: Implement the minimal schema

Use explicit, `Sendable`, `Codable`, `Equatable` types:

```swift
public enum LayoutProfile: String, Codable, Sendable {
    case landscape
    case portraitMobile = "portrait-mobile"
    case unsupported
}

public struct NormalizedRegion: Codable, Equatable, Sendable {
    public let minX: Double
    public let minY: Double
    public let maxX: Double
    public let maxY: Double
}

public struct AutomationAction: Codable, Equatable, Sendable {
    public let targetText: String?
    public let safePointRegion: NormalizedRegion?
}
```

The JSON must describe semantic intent, not fixed click coordinates.

### Step 4: Run tests and verify GREEN

```bash
swift test --filter AutomationRuleTests
swift test --filter RuleLoaderTests
swift test
```

Expected: all tests pass.

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: define semantic automation rules"
```

## Task 2: Classify landscape and mobile portrait layouts

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/LayoutClassifier.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/LayoutClassifierTests.swift`

### Step 1: Write failing classification tests

Test representative content sizes:

```swift
func testClassifiesMobilePortrait() {
    XCTAssertEqual(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 626, height: 949)
        ),
        .portraitMobile
    )
}

func testClassifiesLandscape() {
    XCTAssertEqual(
        LayoutClassifier.classify(
            imageSize: CGSize(width: 1512, height: 949)
        ),
        .landscape
    )
}
```

Add minimum width/height and extreme-aspect rejection tests.

### Step 2: Run and verify RED

```bash
swift test --filter LayoutClassifierTests
```

Expected: `LayoutClassifier` is missing.

### Step 3: Implement ratio plus minimum-size classification

Keep thresholds in one configuration value. Classification only chooses OCR search regions; it never supplies a click coordinate.

### Step 4: Run and verify GREEN

```bash
swift test --filter LayoutClassifierTests
swift test
```

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: classify game window layouts"
```

## Task 3: Add Vision OCR with semantic bounding boxes

**Files:**

- Modify: `apps/background-automator/Package.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/SceneObserver.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/VisionTextRecognizer.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ObservationGeometry.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/SceneObserverTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/ObservationGeometryTests.swift`
- Create: `apps/background-automator/Tests/Fixtures/portrait-reward.png`
- Create: `apps/background-automator/Tests/Fixtures/landscape-clear-touch.png`

Add `Tests/Fixtures` as processed resources on
`BackgroundAutomatorRuntimeTests` before loading the fixture images.

### Step 1: Write failing geometry tests

Vision uses a bottom-left normalized origin while captured images use top-left pixel coordinates. Test the conversion explicitly:

```swift
func testConvertsVisionBoxToTopLeftPixelRect() {
    let rect = ObservationGeometry.pixelRect(
        visionNormalizedRect: CGRect(x: 0.25, y: 0.10, width: 0.50, height: 0.08),
        imageSize: CGSize(width: 600, height: 900)
    )

    XCTAssertEqual(rect.minX, 150, accuracy: 0.001)
    XCTAssertEqual(rect.minY, 738, accuracy: 0.001)
}
```

### Step 2: Write failing observer tests with a fake recognizer

Test:

- exact and whitespace-normalized Korean matching;
- `다시 하기` found in the current layout region;
- required text missing means no scene match;
- forbidden `장면 넘기기` never becomes an action;
- duplicate text candidates are rejected unless geometry/color disambiguates;
- the result contains the actual current bounding box.

Use an injectable protocol:

```swift
protocol TextRecognizing: Sendable {
    func recognize(in image: CGImage) async throws -> [RecognizedText]
}
```

### Step 3: Run and verify RED

```bash
swift test --filter ObservationGeometryTests
swift test --filter SceneObserverTests
```

### Step 4: Implement Vision recognition and scene observation

Configure `VNRecognizeTextRequest` with:

- `.accurate`;
- Korean and English recognition languages;
- language correction enabled;
- a minimum text height suitable for the supported minimum window size.

Return recognized text, confidence, and pixel bounding box. Do not click from an OCR string alone; the rule evaluator will require scene context.

### Step 5: Run fixture and full tests

```bash
swift test --filter ObservationGeometryTests
swift test --filter SceneObserverTests
swift test
```

### Step 6: Commit

```bash
git add apps/background-automator
git commit -m "feat: observe semantic game UI"
```

## Task 4: Monitor user inactivity and input generations

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/UserIdleMonitor.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/UserIdleMonitorTests.swift`

### Step 1: Write failing pure-state tests

Separate the event tap from the state logic:

```swift
func testBecomesIdleAfterThreeSecondsWithoutInput() {
    var state = UserIdleState(lastInputAt: .seconds(10), generation: 3)
    XCTAssertFalse(state.isIdle(at: .seconds(12.9), threshold: .seconds(3)))
    XCTAssertTrue(state.isIdle(at: .seconds(13), threshold: .seconds(3)))
}

func testUserInputIncrementsGeneration() {
    var state = UserIdleState(lastInputAt: .zero, generation: 3)
    state.recordUserInput(at: .seconds(1))
    XCTAssertEqual(state.generation, 4)
}
```

Also test that events tagged with the automator's synthetic source identifier do not increment the user generation.

### Step 2: Run and verify RED

```bash
swift test --filter UserIdleMonitorTests
```

### Step 3: Implement the passive event tap

Listen for keyboard, button, mouse-move, drag, and scroll events. The callback may observe and timestamp events but must return them unchanged.

Expose:

```swift
public struct UserInputSnapshot: Equatable, Sendable {
    public let generation: UInt64
    public let lastInputAt: ContinuousClock.Instant
}

public protocol UserIdleMonitoring: Sendable {
    func snapshot() async -> UserInputSnapshot
    func waitUntilIdle(for duration: Duration) async throws -> UserInputSnapshot
}
```

### Step 4: Run tests and warnings-as-errors

```bash
swift test --filter UserIdleMonitorTests
swift test -Xswiftc -warnings-as-errors
```

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: gate automation on user inactivity"
```

## Task 5: Implement foreground click and restoration

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ForegroundActionCoordinator.swift`
- Modify: `apps/background-automator/Sources/BackgroundAutomatorRuntime/ClickService.swift`
- Modify: `apps/background-automator/Sources/BackgroundAutomatorProbe/main.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/ForegroundActionCoordinatorTests.swift`

### Step 1: Write failing coordinator tests with fakes

Cover:

- saves original frontmost app and pointer;
- activates the game;
- checks the input generation again before clicking;
- moves to the current target-box center and emits exactly one down/up pair;
- waits the configured 0.5 seconds;
- restores pointer before restoring the original app;
- cancels before click when input generation changes;
- still restores after click or activation error;
- stops when the original app no longer exists.

Example:

```swift
func testInputDuringActivationCancelsClickAndRestores() async throws {
    let idle = FakeIdleMonitor(generations: [10, 11])
    let clicker = RecordingForegroundClicker()
    let coordinator = ForegroundActionCoordinator(
        workspace: workspace,
        pointer: pointer,
        idleMonitor: idle,
        clicker: clicker,
        clock: clock
    )

    await XCTAssertThrowsErrorAsync {
        try await coordinator.perform(request)
    }
    XCTAssertEqual(clicker.clickCount, 0)
    XCTAssertTrue(pointer.didRestore)
    XCTAssertTrue(workspace.didRestoreOriginalApp)
}
```

### Step 2: Run and verify RED

```bash
swift test --filter ForegroundActionCoordinatorTests
```

### Step 3: Implement foreground adapters

Use public APIs:

- `NSWorkspace.shared.frontmostApplication`;
- `NSRunningApplication.activate`;
- `CGEvent(source: nil)?.location`;
- `CGWarpMouseCursorPosition` or a tagged mouse-move event;
- a global left-down/left-up pair only after the game is frontmost.

Tag synthetic events so `UserIdleMonitor` ignores them. Restoration must be in a `defer`-equivalent async cleanup path.

### Step 4: Add guarded probe command

```text
BackgroundAutomatorProbe foreground-click \
  --bundle-id <id> \
  --title <text> \
  --x <0...1> \
  --y <0...1>
```

The probe must print:

- original and game bundle IDs;
- pointer before, target, and restored position;
- input generations;
- before/after captures;
- restoration result.

It must require exact `CLICK`.

### Step 5: Run tests and build

```bash
swift test --filter ForegroundActionCoordinatorTests
swift test
swift build -Xswiftc -warnings-as-errors
```

### Step 6: Commit

```bash
git add apps/background-automator
git commit -m "feat: restore focus after foreground clicks"
```

## Task 6: Evaluate stable rules and revalidate targets

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/RuleEvaluator.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/StableObservationTracker.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/RuleEvaluatorTests.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/StableObservationTrackerTests.swift`

### Step 1: Write failing rule tests

Test:

- one observation is insufficient;
- two identical observations produce an action candidate;
- a layout/frame change invalidates stability;
- a changed target bounding box invalidates a pending action;
- required and forbidden text;
- OCR confidence threshold;
- ambiguous targets produce no action;
- `장면 넘기기` always produces no action.

### Step 2: Run and verify RED

```bash
swift test --filter RuleEvaluatorTests
swift test --filter StableObservationTrackerTests
```

### Step 3: Implement immutable action candidates

```swift
public struct ActionCandidate: Equatable, Sendable {
    public let ruleID: String
    public let windowIdentity: WindowCandidate
    public let layout: LayoutProfile
    public let sceneFingerprint: SceneFingerprint
    public let targetPixelRect: CGRect
}
```

Final revalidation must compare rule ID, window identity, layout, scene fingerprint, and a target rectangle tolerance. It must use a fresh capture.

### Step 4: Run full tests

```bash
swift test --filter RuleEvaluatorTests
swift test --filter StableObservationTrackerTests
swift test
```

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: revalidate semantic action targets"
```

## Task 7: Build the screen-derived automation state machine

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorCore/AutomationState.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/AutomationCoordinator.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/AutomationCoordinatorTests.swift`

### Step 1: Write failing synchronization tests

Test these manual-progress cases:

- user advances `CLEAR_TOUCH` to reward screen;
- user presses `다시 하기`, so coordinator continues at `CONTINUE_DIALOG`;
- user presses `계속하기`, so coordinator continues at mission selection;
- user selects the challenge, so coordinator only considers `ENTER_READY`;
- user enters the dungeon, so coordinator adopts `RUNNING`;
- unknown transient screen produces no action and later recovers.

### Step 2: Write failing timing tests

Use a fake clock:

- `CLEAR_TOUCH` imposes at least a 2-second no-click delay;
- `ENTER_READY` success moves to a 2-minute running cooldown;
- user input cancels a pending action without advancing state;
- failed restoration pauses automation.

### Step 3: Run and verify RED

```bash
swift test --filter AutomationCoordinatorTests
```

### Step 4: Implement observation-driven transitions

Do not model transitions as “last click + 1”. Adopt the newest recognized scene every cycle. A click outcome can set a temporary cooldown but cannot force the next scene.

### Step 5: Run all tests

```bash
swift test --filter AutomationCoordinatorTests
swift test
```

### Step 6: Commit

```bash
git add apps/background-automator
git commit -m "feat: synchronize automation from the screen"
```

## Task 8: Add permissions and preflight diagnostics

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/PermissionService.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/PreflightService.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/PreflightServiceTests.swift`

### Step 1: Write failing preflight tests

Test missing:

- Screen Recording;
- Accessibility;
- Input Monitoring/event tap availability;
- running target app;
- visible non-minimized target window;
- supported layout/minimum size.

### Step 2: Run and verify RED

```bash
swift test --filter PreflightServiceTests
```

### Step 3: Implement typed preflight results

The app must show guidance, not repeatedly prompt or keep trying. Permission checks must not begin automation until all required capabilities are ready.

### Step 4: Run tests

```bash
swift test --filter PreflightServiceTests
swift test
```

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: validate automator prerequisites"
```

## Task 9: Build the menu-bar control surface

**Files:**

- Modify: `apps/background-automator/Sources/BackgroundAutomatorApp/BackgroundAutomatorApp.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorApp/AppModel.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorApp/MenuContentView.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/AutomationStatusTests.swift`

### Step 1: Write failing observable-state tests

Test menu-facing statuses:

- stopped;
- combat wait;
- button detected;
- waiting for user idle;
- clicking;
- needs attention;
- paused after restoration failure.

### Step 2: Implement the app model

The menu must provide:

- automation on/off toggle;
- current Korean status;
- last action and timestamp;
- open diagnostics folder;
- quit.

Stopping must cancel observation, idle waits, and pending actions. If an action has already moved the pointer/focus, stopping must finish restoration first.

### Step 3: Run tests and build the app

```bash
swift test
swift build --product BackgroundAutomatorApp -Xswiftc -warnings-as-errors
```

### Step 4: Launch manually

```bash
swift run BackgroundAutomatorApp
```

Expected: one menu-bar item, no Dock window, start/stop works.

### Step 5: Commit

```bash
git add apps/background-automator
git commit -m "feat: add menu bar automation controls"
```

## Task 10: Populate the initial Mabinogi workflow rules

**Files:**

- Modify: `apps/background-automator/Sources/BackgroundAutomatorRuntime/Resources/default-rules.json`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/DefaultWorkflowRulesTests.swift`

### Step 1: Write failing rule-coverage tests

Require these rule IDs:

- `clear_touch`;
- `reward_retry`;
- `continue_dialog`;
- `mission_selection`;
- `enter_ready`;
- `running`;

Assert `scene_skip` does not exist and `장면 넘기기` is forbidden.

### Step 2: Add landscape and portrait-mobile regions

For text buttons, regions only narrow OCR search. The click point always comes from the detected current button rectangle.

For `clear_touch`, use a safe region only after both `던전 클리어` and
`화면을 터치해 주세요` are present.

### Step 3: Run tests

```bash
swift test --filter DefaultWorkflowRulesTests
swift test
```

### Step 4: Commit

```bash
git add apps/background-automator
git commit -m "feat: add default dungeon workflow rules"
```

## Task 11: Add diagnostics and failure-safe logging

**Files:**

- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/DiagnosticLogger.swift`
- Create: `apps/background-automator/Sources/BackgroundAutomatorRuntime/DiagnosticCaptureStore.swift`
- Create: `apps/background-automator/Tests/BackgroundAutomatorRuntimeTests/DiagnosticLoggerTests.swift`

### Step 1: Write failing retention and redaction tests

Test:

- bounded log retention;
- bounded diagnostic image count;
- atomic writes;
- no unrelated window titles;
- no OCR text outside the target game window;
- failures include rule ID, confidence, layout, and reason.

### Step 2: Implement local diagnostics

Store under Application Support:

```text
~/Library/Application Support/BackgroundAutomator/
  logs/
  captures/
  rules/
```

Do not upload or transmit any content.

### Step 3: Run tests

```bash
swift test --filter DiagnosticLoggerTests
swift test
```

### Step 4: Commit

```bash
git add apps/background-automator
git commit -m "feat: add local automation diagnostics"
```

## Task 12: Run live foreground-action gates

**Files:**

- Modify: `docs/plans/2026-07-23-foreground-automator-design.md`

### Step 1: Verify foreground click restoration

Use a safe, reversible screen. Keep Codex or another app frontmost.

Record:

- pointer and frontmost app before;
- idle generation before;
- game activation;
- one click;
- pointer and frontmost app after restoration;
- before/after game captures.

Pass conditions:

- intended action happens once;
- action waits until three seconds idle;
- pointer returns within one pixel;
- original app is frontmost again;
- restoration finishes within one second after click.

If restoration fails, stop and fix before workflow testing.

### Step 2: Verify cancellation on user input

While `사용자 입력 대기` is visible, move the pointer or type.

Expected:

- pending click is discarded;
- no game activation;
- no click;
- coordinator returns to observation.

### Step 3: Verify manual progress synchronization

Manually complete one intermediate action in each screen and confirm the automator continues from the new screen without repeating it.

### Step 4: Verify both layouts

Run the same rule sequence once in:

- landscape;
- portrait-mobile.

Resize between them while an action is pending.

Expected: pending action is invalidated and detection restarts.

### Step 5: Document exact evidence and commit

```bash
git add docs/plans/2026-07-23-foreground-automator-design.md
git commit -m "docs: record foreground automation verification"
```

## Task 13: Package the app and write installation guidance

**Files:**

- Create: `apps/background-automator/scripts/build-app.sh`
- Create: `apps/background-automator/Resources/Info.plist`
- Create: `apps/background-automator/README.md`
- Create: `apps/background-automator/.gitignore`

### Step 1: Write a failing packaging smoke test

The script must create:

```text
dist/Background Automator.app/
  Contents/Info.plist
  Contents/MacOS/BackgroundAutomatorApp
  Contents/Resources/default-rules.json
```

### Step 2: Implement deterministic local packaging

Do not install into `/Applications` automatically. Build into `dist/` and explain manual installation.

### Step 3: Document permissions and operation

README must explain:

- Screen Recording;
- Accessibility;
- Input Monitoring;
- game must not be minimized;
- three-second idle behavior;
- temporary foreground switch and restoration;
- supported landscape and portrait-mobile layouts;
- start/stop and diagnostics.

### Step 4: Build and verify

```bash
bash apps/background-automator/scripts/build-app.sh
plutil -lint "apps/background-automator/dist/Background Automator.app/Contents/Info.plist"
open "apps/background-automator/dist/Background Automator.app"
```

Expected: valid bundle and working menu-bar item.

### Step 5: Run the final verification suite

```bash
cd apps/background-automator
swift test -Xswiftc -warnings-as-errors
swift build --product BackgroundAutomatorApp -Xswiftc -warnings-as-errors
git diff --check
```

Expected: all tests and builds pass, worktree contains no source changes.

### Step 6: Commit

```bash
git add apps/background-automator
git commit -m "build: package background automator app"
```

## Final review

Before calling the work complete:

1. run the full test and warnings-as-errors build;
2. inspect the complete diff from the design commit;
3. perform a spec-compliance review;
4. perform a code-quality review;
5. confirm foreground restoration in both layouts;
6. confirm user-input cancellation;
7. confirm manual intermediate progress resynchronizes;
8. confirm `장면 넘기기` is never an action.
