import CoreGraphics
import Foundation
import Testing

@testable import BackgroundAutomatorRuntime

@Test
func stallImageWriterSavesPNGNamedByTimestamp() throws {
    let directory = try makeTemporaryStallDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }

    let writer = StallImageWriter(directory: directory)
    let saved = try #require(
        writer.write(
            try makeSolidImage(),
            at: Date(timeIntervalSince1970: 1_785_000_000)
        )
    )

    #expect(saved.pathExtension == "png")
    #expect(saved.lastPathComponent.hasPrefix("stall-"))
    #expect(FileManager.default.fileExists(atPath: saved.path))
    let bytes = try Data(contentsOf: saved)
    // PNG 시그니처 — 실제로 이미지가 인코딩됐는지 본다.
    #expect(bytes.prefix(4) == Data([0x89, 0x50, 0x4E, 0x47]))
}

@Test
func stallImageWriterKeepsOnlyRecentSnapshots() throws {
    let directory = try makeTemporaryStallDirectory()
    defer { try? FileManager.default.removeItem(at: directory) }

    // 멈춤이 반복돼도 진단 폴더가 무한히 커지지 않아야 한다.
    let writer = StallImageWriter(directory: directory, keepCount: 3)
    let image = try makeSolidImage()
    for offset in 0 ..< 6 {
        _ = writer.write(
            image,
            at: Date(timeIntervalSince1970: 1_785_000_000 + Double(offset))
        )
    }

    let remaining = try FileManager.default
        .contentsOfDirectory(atPath: directory.path)
        .filter { $0.hasSuffix(".png") }
        .sorted()
    #expect(remaining.count == 3)
    // 오래된 게 아니라 최근 것이 남아야 한다.
    #expect(remaining.allSatisfy { !$0.contains("000000.png") })
}

private func makeTemporaryStallDirectory() throws -> URL {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent("stall-image-\(UUID().uuidString)")
    try FileManager.default.createDirectory(
        at: directory,
        withIntermediateDirectories: true
    )
    return directory
}

private func makeSolidImage() throws -> CGImage {
    let context = try #require(
        CGContext(
            data: nil,
            width: 8,
            height: 8,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )
    )
    context.setFillColor(CGColor(red: 1, green: 0, blue: 0, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: 8, height: 8))
    return try #require(context.makeImage())
}
