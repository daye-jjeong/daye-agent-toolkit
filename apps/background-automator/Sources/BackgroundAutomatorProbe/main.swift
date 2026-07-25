import AppKit
import CoreGraphics
import BackgroundAutomatorRuntime
import Darwin
import Foundation
import ImageIO
@preconcurrency import ScreenCaptureKit
import UniformTypeIdentifiers

enum ProbeError: Error {
    case invalidArguments(String)
    case clickNotConfirmed
    case clickTargetChanged
    case pngEncoderUnavailable
    case pngEncodingFailed
    case pngWriteFailed(path: String, reason: String)
}

extension ProbeError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case let .invalidArguments(message):
            "\(message)\n\n\(usage)"
        case .clickNotConfirmed:
            "Click cancelled because the confirmation was not exactly CLICK."
        case .clickTargetChanged:
            "Click cancelled because the target window changed after confirmation."
        case .pngEncoderUnavailable:
            "Could not create an in-memory PNG encoder."
        case .pngEncodingFailed:
            "Could not finish encoding the captured image as PNG."
        case let .pngWriteFailed(path, reason):
            "Could not atomically write the PNG at \(path): \(reason)"
        }
    }
}

enum ProbeCommand {
    case version
    case list
    case visibility(bundleIdentifier: String, title: String)
    case capture(bundleIdentifier: String, title: String, outputPath: String)
    case benchCapture(bundleIdentifier: String)
    case click(
        bundleIdentifier: String,
        title: String,
        normalizedX: Double,
        normalizedY: Double
    )
    case foregroundClick(
        bundleIdentifier: String,
        title: String,
        normalizedX: Double,
        normalizedY: Double
    )

    static func parse(_ arguments: [String]) throws -> ProbeCommand {
        guard let command = arguments.first else {
            throw ProbeError.invalidArguments("Missing command.")
        }

        switch command {
        case "version":
            guard arguments.count == 1 else {
                throw ProbeError.invalidArguments(
                    "The version command does not accept arguments."
                )
            }
            return .version

        case "list":
            guard arguments.count == 1 else {
                throw ProbeError.invalidArguments(
                    "The list command does not accept arguments."
                )
            }
            return .list

        case "visibility":
            var values: [String: String] = [:]
            var index = 1

            while index < arguments.count {
                let option = arguments[index]
                guard ["--bundle-id", "--title"].contains(option) else {
                    throw ProbeError.invalidArguments("Unknown option: \(option)")
                }
                guard values[option] == nil else {
                    throw ProbeError.invalidArguments("Duplicate option: \(option)")
                }
                guard index + 1 < arguments.count else {
                    throw ProbeError.invalidArguments("Missing value for \(option).")
                }

                let value = arguments[index + 1]
                guard !value.isEmpty else {
                    throw ProbeError.invalidArguments("Empty value for \(option).")
                }
                values[option] = value
                index += 2
            }

            guard
                let bundleIdentifier = values["--bundle-id"],
                let title = values["--title"]
            else {
                throw ProbeError.invalidArguments(
                    "visibility requires --bundle-id and --title."
                )
            }
            return .visibility(
                bundleIdentifier: bundleIdentifier,
                title: title
            )

        case "bench-capture":
            guard arguments.count == 3, arguments[1] == "--bundle-id" else {
                throw ProbeError.invalidArguments(
                    "Usage: bench-capture --bundle-id <id>"
                )
            }
            return .benchCapture(bundleIdentifier: arguments[2])

        case "capture":
            var values: [String: String] = [:]
            var index = 1

            while index < arguments.count {
                let option = arguments[index]
                guard ["--bundle-id", "--title", "--output"].contains(option) else {
                    throw ProbeError.invalidArguments("Unknown option: \(option)")
                }
                guard values[option] == nil else {
                    throw ProbeError.invalidArguments("Duplicate option: \(option)")
                }
                guard index + 1 < arguments.count else {
                    throw ProbeError.invalidArguments("Missing value for \(option).")
                }

                let value = arguments[index + 1]
                guard !value.isEmpty else {
                    throw ProbeError.invalidArguments("Empty value for \(option).")
                }
                values[option] = value
                index += 2
            }

            guard
                let bundleIdentifier = values["--bundle-id"],
                let title = values["--title"],
                let outputPath = values["--output"]
            else {
                throw ProbeError.invalidArguments(
                    "capture requires --bundle-id, --title, and --output."
                )
            }

            return .capture(
                bundleIdentifier: bundleIdentifier,
                title: title,
                outputPath: outputPath
            )

        case "click":
            var values: [String: String] = [:]
            var index = 1

            while index < arguments.count {
                let option = arguments[index]
                guard
                    ["--bundle-id", "--title", "--x", "--y"].contains(option)
                else {
                    throw ProbeError.invalidArguments(
                        "Unknown option: \(option)"
                    )
                }
                guard values[option] == nil else {
                    throw ProbeError.invalidArguments(
                        "Duplicate option: \(option)"
                    )
                }
                guard index + 1 < arguments.count else {
                    throw ProbeError.invalidArguments(
                        "Missing value for \(option)."
                    )
                }

                let value = arguments[index + 1]
                guard !value.isEmpty else {
                    throw ProbeError.invalidArguments(
                        "Empty value for \(option)."
                    )
                }
                values[option] = value
                index += 2
            }

            guard
                let bundleIdentifier = values["--bundle-id"],
                let title = values["--title"],
                let rawX = values["--x"],
                let normalizedX = Double(rawX),
                let rawY = values["--y"],
                let normalizedY = Double(rawY)
            else {
                throw ProbeError.invalidArguments(
                    "click requires --bundle-id, --title, --x, and --y."
                )
            }

            return .click(
                bundleIdentifier: bundleIdentifier,
                title: title,
                normalizedX: normalizedX,
                normalizedY: normalizedY
            )

        case "foreground-click":
            var values: [String: String] = [:]
            var index = 1

            while index < arguments.count {
                let option = arguments[index]
                guard
                    ["--bundle-id", "--title", "--x", "--y"].contains(option)
                else {
                    throw ProbeError.invalidArguments(
                        "Unknown option: \(option)"
                    )
                }
                guard values[option] == nil else {
                    throw ProbeError.invalidArguments(
                        "Duplicate option: \(option)"
                    )
                }
                guard index + 1 < arguments.count else {
                    throw ProbeError.invalidArguments(
                        "Missing value for \(option)."
                    )
                }

                let value = arguments[index + 1]
                guard !value.isEmpty else {
                    throw ProbeError.invalidArguments(
                        "Empty value for \(option)."
                    )
                }
                values[option] = value
                index += 2
            }

            guard
                let bundleIdentifier = values["--bundle-id"],
                let title = values["--title"],
                let rawX = values["--x"],
                let normalizedX = Double(rawX),
                normalizedX.isFinite,
                (0 ... 1).contains(normalizedX),
                let rawY = values["--y"],
                let normalizedY = Double(rawY),
                normalizedY.isFinite,
                (0 ... 1).contains(normalizedY)
            else {
                throw ProbeError.invalidArguments(
                    "foreground-click requires --bundle-id, --title, "
                        + "--x, and --y with x/y in 0...1."
                )
            }

            return .foregroundClick(
                bundleIdentifier: bundleIdentifier,
                title: title,
                normalizedX: normalizedX,
                normalizedY: normalizedY
            )

        default:
            throw ProbeError.invalidArguments("Unknown command: \(command)")
        }
    }
}

let usage = """
Usage:
  BackgroundAutomatorProbe version
  BackgroundAutomatorProbe list
  BackgroundAutomatorProbe visibility --bundle-id <id> --title <text>
  BackgroundAutomatorProbe capture --bundle-id <id> --title <text> --output <path>
  BackgroundAutomatorProbe click --bundle-id <id> --title <text> --x <0...1> --y <0...1>
  BackgroundAutomatorProbe foreground-click --bundle-id <id> --title <text> --x <0...1> --y <0...1>
"""

func encodePNG(_ image: CGImage) throws -> Data {
    guard let encodedData = CFDataCreateMutable(kCFAllocatorDefault, 0) else {
        throw ProbeError.pngEncoderUnavailable
    }
    guard let destination = CGImageDestinationCreateWithData(
        encodedData,
        UTType.png.identifier as CFString,
        1,
        nil
    ) else {
        throw ProbeError.pngEncoderUnavailable
    }

    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw ProbeError.pngEncodingFailed
    }
    return encodedData as Data
}

func writePNG(_ image: CGImage, to outputPath: String) throws {
    let data = try encodePNG(image)
    let url = URL(fileURLWithPath: outputPath)

    do {
        try data.write(to: url, options: .atomic)
    } catch {
        throw ProbeError.pngWriteFailed(
            path: outputPath,
            reason: error.localizedDescription
        )
    }
}

func frameDescription(_ frame: CGRect) -> String {
    String(
        format: "x=%.0f y=%.0f width=%.0f height=%.0f",
        frame.origin.x,
        frame.origin.y,
        frame.size.width,
        frame.size.height
    )
}

do {
    let command = try ProbeCommand.parse(Array(CommandLine.arguments.dropFirst()))
    _ = NSApplication.shared
    let captureService = WindowCaptureService()

    switch command {
    case let .benchCapture(bundleIdentifier):
        let report = try await CaptureBenchmark()
            .run(bundleIdentifier: bundleIdentifier)
        print(report)

    case .version:
        print(
            "BackgroundAutomatorProbe "
                + BackgroundAutomatorRuntime.version
        )

    case .list:
        let candidates = try await captureService.listWindows()
        let safeCandidates = candidates.filter {
            !$0.bundleIdentifier.isEmpty
                && $0.isOnScreen
                && $0.frame.size.width > 0
                && $0.frame.size.height > 0
        }

        print("Visible capturable windows: \(safeCandidates.count)")
        for candidate in safeCandidates {
            print(
                "windowID=\(candidate.windowID) "
                    + "pid=\(candidate.processID) "
                    + "bundleID=\(candidate.bundleIdentifier) "
                    + "frame=(\(frameDescription(candidate.frame)))"
            )
        }

    case let .visibility(bundleIdentifier, title):
        let diagnostic = try await captureService.visibilityDiagnostic(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        print("windowID=\(diagnostic.candidate.windowID)")
        print("pid=\(diagnostic.candidate.processID)")
        print(
            "screenAndCoreGraphicsOnScreen="
                + "\(diagnostic.candidate.isOnScreen)"
        )
        print(
            "screenFrame=(\(frameDescription(diagnostic.candidate.frame)))"
        )
        print(
            "accessibilityFrame=("
                + "\(frameDescription(diagnostic.accessibilityWindow.frame)))"
        )
        print(
            "accessibilityMinimized="
                + "\(diagnostic.accessibilityWindow.isMinimized)"
        )

    case let .capture(bundleIdentifier, title, outputPath):
        let result = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        try writePNG(result.image, to: outputPath)

        print("windowID=\(result.candidate.windowID)")
        print("pid=\(result.candidate.processID)")
        print("frame=(\(frameDescription(result.candidate.frame)))")
        print("output=\(URL(fileURLWithPath: outputPath).path)")

    case let .click(
        bundleIdentifier,
        title,
        normalizedX,
        normalizedY
    ):
        let beforePath = "/tmp/background-automator-click-before.png"
        let afterPath = "/tmp/background-automator-click-after.png"
        let before = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        let screenPoint = try CoordinateConverter.screenPoint(
            normalizedX: normalizedX,
            normalizedY: normalizedY,
            windowFrame: before.candidate.frame
        )
        try writePNG(before.image, to: beforePath)

        print("windowID=\(before.candidate.windowID)")
        print("pid=\(before.candidate.processID)")
        print("frame=(\(frameDescription(before.candidate.frame)))")
        print(
            String(
                format: "point=(x=%.3f y=%.3f)",
                screenPoint.x,
                screenPoint.y
            )
        )
        print("before=\(beforePath)")
        print("Type CLICK and press Return to send one process-targeted click:")
        fflush(stdout)

        guard readLine() == "CLICK" else {
            throw ProbeError.clickNotConfirmed
        }

        let revalidated = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        guard revalidated.candidate == before.candidate else {
            throw ProbeError.clickTargetChanged
        }

        let clickService = ProcessClickService()
        try clickService.click(
            processID: before.candidate.processID,
            screenPoint: screenPoint
        )

        try await Task.sleep(for: .milliseconds(500))
        let after = try await captureService.captureWindow(
            matching: before.candidate
        )
        try writePNG(after.image, to: afterPath)
        print("afterWindowID=\(after.candidate.windowID)")
        print("afterPID=\(after.candidate.processID)")
        print(
            "afterFrame=(\(frameDescription(after.candidate.frame)))"
        )
        print("after=\(afterPath)")

    case let .foregroundClick(
        bundleIdentifier,
        title,
        normalizedX,
        normalizedY
    ):
        let beforePath =
            "/tmp/background-automator-foreground-before.png"
        let afterPath =
            "/tmp/background-automator-foreground-after.png"
        let selected = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        let selectedPoint = try CoordinateConverter.screenPoint(
            normalizedX: normalizedX,
            normalizedY: normalizedY,
            windowFrame: selected.candidate.frame
        )

        print("A foreground click will temporarily activate the game.")
        print("Type CLICK and press Return to continue:")
        fflush(stdout)

        guard readLine() == "CLICK" else {
            throw ProbeError.clickNotConfirmed
        }

        let inputMonitor = UserIdleMonitor()
        try inputMonitor.start()
        defer {
            inputMonitor.stop()
        }
        let expectedInput = await inputMonitor.snapshot()

        let before = try await captureService.captureWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        guard before.candidate == selected.candidate else {
            throw ProbeError.clickTargetChanged
        }
        try writePNG(before.image, to: beforePath)

        let coordinator = ForegroundActionCoordinator(
            inputMonitor: inputMonitor
        )
        let result = try await coordinator.perform(
            targetApplication: ApplicationIdentity(
                processIdentifier: before.candidate.processID,
                bundleIdentifier: before.candidate.bundleIdentifier
            ),
            targetBox: CGRect(
                origin: selectedPoint,
                size: .zero
            ),
            expectedInputGeneration: expectedInput.generation
        )

        let after = try await captureService.captureWindow(
            matching: before.candidate
        )
        try writePNG(after.image, to: afterPath)

        print(
            "originalBundleID="
                + result.originalApplication.bundleIdentifier
        )
        print(
            "gameBundleID="
                + result.targetApplication.bundleIdentifier
        )
        print(
            String(
                format: "pointerBefore=(x=%.3f y=%.3f)",
                result.pointerBefore.x,
                result.pointerBefore.y
            )
        )
        print(
            String(
                format: "pointerTarget=(x=%.3f y=%.3f)",
                result.targetPoint.x,
                result.targetPoint.y
            )
        )
        print(
            String(
                format: "pointerRestored=(x=%.3f y=%.3f)",
                result.pointerRestored.x,
                result.pointerRestored.y
            )
        )
        print(
            "inputGenerationExpected="
                + "\(result.expectedInputGeneration)"
        )
        print(
            "inputGenerationBeforeClick="
                + "\(result.inputGenerationBeforeClick)"
        )
        print("beforeCapture=\(beforePath)")
        print(
            "beforeCaptureResult=windowID="
                + "\(before.candidate.windowID) pid="
                + "\(before.candidate.processID)"
        )
        print("afterCapture=\(afterPath)")
        print(
            "afterCaptureResult=windowID="
                + "\(after.candidate.windowID) pid="
                + "\(after.candidate.processID)"
        )
        print("restoration=\(result.restoration)")
    }

    fflush(stdout)
    fflush(stderr)
    exit(EXIT_SUCCESS)
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    fflush(stderr)
    exit(EXIT_FAILURE)
}


/// 화면 한 장을 얻는 데 드는 시간을 구간별로 나눠 잰다.
/// 어디를 줄여야 반응이 빨라지는지 추측하지 않기 위해서다.
private actor CaptureBenchmark {
    func run(bundleIdentifier: String) async throws -> String {
        var enumerate: [Double] = []
        var accessibility: [Double] = []
        var pixels: [Double] = []

        for round in 0 ..< 6 {
            var mark = Date()
            let content = try await SCShareableContent
                .excludingDesktopWindows(false, onScreenWindowsOnly: false)
            let enumerateMs = Self.elapsed(mark)

            guard let window = content.windows.first(where: {
                $0.owningApplication?.bundleIdentifier == bundleIdentifier
            }) else {
                throw ProbeError.invalidArguments("창을 찾지 못했습니다.")
            }

            mark = Date()
            let element = AXUIElementCreateApplication(
                window.owningApplication?.processID ?? 0
            )
            var value: CFTypeRef?
            _ = AXUIElementCopyAttributeValue(
                element,
                kAXWindowsAttribute as CFString,
                &value
            )
            let accessibilityMs = Self.elapsed(mark)

            let configuration = SCStreamConfiguration()
            configuration.showsCursor = false
            configuration.width = Int(window.frame.width)
            configuration.height = Int(window.frame.height)
            let filter = SCContentFilter(desktopIndependentWindow: window)
            mark = Date()
            _ = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: configuration
            )
            let pixelsMs = Self.elapsed(mark)

            if round > 0 {
                enumerate.append(enumerateMs)
                accessibility.append(accessibilityMs)
                pixels.append(pixelsMs)
            }
        }

        let e = Self.median(enumerate)
        let a = Self.median(accessibility)
        let p = Self.median(pixels)
        return [
            String(format: "창 열거      %6.0fms", e),
            String(format: "접근성 확인  %6.0fms", a),
            String(format: "화면 캡처    %6.0fms", p),
            String(format: "합계         %6.0fms", e + a + p),
        ].joined(separator: "\n")
    }

    private static func elapsed(_ start: Date) -> Double {
        Date().timeIntervalSince(start) * 1_000
    }

    private static func median(_ values: [Double]) -> Double {
        values.sorted()[values.count / 2]
    }
}
