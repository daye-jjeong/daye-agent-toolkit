import AppKit
import CoreGraphics
import BackgroundAutomatorRuntime
import Darwin
import Foundation
import ImageIO
import UniformTypeIdentifiers

enum ProbeError: Error {
    case invalidArguments(String)
    case pngEncoderUnavailable
    case pngEncodingFailed
    case pngWriteFailed(path: String, reason: String)
}

extension ProbeError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case let .invalidArguments(message):
            "\(message)\n\n\(usage)"
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
    case capture(bundleIdentifier: String, title: String, outputPath: String)

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

        default:
            throw ProbeError.invalidArguments("Unknown command: \(command)")
        }
    }
}

let usage = """
Usage:
  BackgroundAutomatorProbe list
  BackgroundAutomatorProbe capture --bundle-id <id> --title <text> --output <path>
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

    case let .capture(bundleIdentifier, title, outputPath):
        let candidate = try await captureService.findWindow(
            bundleIdentifier: bundleIdentifier,
            titleContains: title
        )
        let image = try await captureService.capture(windowID: candidate.windowID)
        try writePNG(image, to: outputPath)

        print("windowID=\(candidate.windowID)")
        print("pid=\(candidate.processID)")
        print("frame=(\(frameDescription(candidate.frame)))")
        print("output=\(URL(fileURLWithPath: outputPath).path)")
    }
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    exit(EXIT_FAILURE)
}
