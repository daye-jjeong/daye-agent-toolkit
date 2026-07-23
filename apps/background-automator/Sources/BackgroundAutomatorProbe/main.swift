import AppKit
import CoreGraphics
import BackgroundAutomatorRuntime
import Darwin
import Foundation
import ImageIO
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
    case list
    case visibility(bundleIdentifier: String, title: String)
    case capture(bundleIdentifier: String, title: String, outputPath: String)
    case click(
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

        default:
            throw ProbeError.invalidArguments("Unknown command: \(command)")
        }
    }
}

let usage = """
Usage:
  BackgroundAutomatorProbe list
  BackgroundAutomatorProbe visibility --bundle-id <id> --title <text>
  BackgroundAutomatorProbe capture --bundle-id <id> --title <text> --output <path>
  BackgroundAutomatorProbe click --bundle-id <id> --title <text> --x <0...1> --y <0...1>
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
    }
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    exit(EXIT_FAILURE)
}
