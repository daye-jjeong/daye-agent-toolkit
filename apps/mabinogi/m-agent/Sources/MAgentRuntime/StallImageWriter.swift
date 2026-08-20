@preconcurrency import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

/// 멈춘 순간의 화면을 PNG로 남긴다.
///
/// `stall-log.jsonl`은 인식된 글자만 담아, 정작 "그때 화면이 뭐였나"를
/// 되짚을 수 없었다(2026-07-26 던전 클리어 화면 멈춤). 사진이 있으면
/// 규칙을 새로 짤 때 그대로 픽스처로 쓸 수 있다.
public struct StallImageWriter: Sendable {
    public static let filePrefix = "stall-"

    private let directory: URL
    private let keepCount: Int

    public init(directory: URL, keepCount: Int = 20) {
        self.directory = directory
        self.keepCount = keepCount
    }

    /// 저장에 성공하면 파일 URL을 준다. 진단 기록 실패가 자동화를 막아서는
    /// 안 되므로 실패는 nil로만 알린다.
    @discardableResult
    public func write(_ image: CGImage, at timestamp: Date) -> URL? {
        let url = directory.appendingPathComponent(
            "\(Self.filePrefix)\(Self.stamp(timestamp)).png"
        )
        do {
            try FileManager.default.createDirectory(
                at: directory,
                withIntermediateDirectories: true
            )
        } catch {
            return nil
        }

        guard
            let destination = CGImageDestinationCreateWithURL(
                url as CFURL,
                UTType.png.identifier as CFString,
                1,
                nil
            )
        else {
            return nil
        }
        CGImageDestinationAddImage(destination, image, nil)
        guard CGImageDestinationFinalize(destination) else {
            return nil
        }

        prune()
        return url
    }

    /// 이름이 시각순이라 사전순 정렬이 곧 시간순이다.
    private func prune() {
        guard
            let names = try? FileManager.default.contentsOfDirectory(
                atPath: directory.path
            )
        else {
            return
        }
        let snapshots = names
            .filter {
                $0.hasPrefix(Self.filePrefix) && $0.hasSuffix(".png")
            }
            .sorted()
        for name in snapshots.dropLast(keepCount) {
            try? FileManager.default.removeItem(
                at: directory.appendingPathComponent(name)
            )
        }
    }

    private static func stamp(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter.string(from: date)
    }
}
