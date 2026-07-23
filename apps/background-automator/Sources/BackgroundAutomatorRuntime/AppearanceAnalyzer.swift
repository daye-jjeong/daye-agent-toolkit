@preconcurrency import CoreGraphics
import Foundation

public struct AppearanceStatistics: Equatable, Sendable {
    public let medianSaturation: Double
    public let medianLuminance: Double
    public let sampleCount: Int

    public init(
        medianSaturation: Double,
        medianLuminance: Double,
        sampleCount: Int
    ) {
        self.medianSaturation = medianSaturation
        self.medianLuminance = medianLuminance
        self.sampleCount = sampleCount
    }
}

public protocol AppearanceAnalyzing: Sendable {
    func statistics(
        in image: CGImage,
        around textBoundingBox: CGRect
    ) -> AppearanceStatistics?
}

public struct PixelAppearanceAnalyzer:
    AppearanceAnalyzing,
    Sendable
{
    private static let minimumSampleCount = 8

    public init() {}

    public func statistics(
        in image: CGImage,
        around textBoundingBox: CGRect
    ) -> AppearanceStatistics? {
        guard
            let cropRect = Self.expandedCropRect(
                around: textBoundingBox,
                image: image
            ),
            let cropped = image.cropping(to: cropRect),
            let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)
        else {
            return nil
        }

        let width = cropped.width
        let height = cropped.height
        guard width > 0, height > 0 else {
            return nil
        }
        var pixels = [UInt8](
            repeating: 0,
            count: width * height * 4
        )
        let rendered = pixels.withUnsafeMutableBytes { bytes -> Bool in
            guard
                let context = CGContext(
                    data: bytes.baseAddress,
                    width: width,
                    height: height,
                    bitsPerComponent: 8,
                    bytesPerRow: width * 4,
                    space: colorSpace,
                    bitmapInfo:
                        CGImageAlphaInfo.premultipliedLast.rawValue
                            | CGBitmapInfo.byteOrder32Big.rawValue
                )
            else {
                return false
            }
            context.interpolationQuality = .none
            context.draw(
                cropped,
                in: CGRect(x: 0, y: 0, width: width, height: height)
            )
            return true
        }
        guard rendered else {
            return nil
        }

        var saturations: [Double] = []
        var luminances: [Double] = []
        saturations.reserveCapacity(width * height)
        luminances.reserveCapacity(width * height)

        for offset in stride(from: 0, to: pixels.count, by: 4) {
            let alpha = Double(pixels[offset + 3]) / 255
            guard alpha >= 0.125 else {
                continue
            }
            let red = Double(pixels[offset]) / 255
            let green = Double(pixels[offset + 1]) / 255
            let blue = Double(pixels[offset + 2]) / 255
            let luminance =
                0.2126 * red + 0.7152 * green + 0.0722 * blue
            guard luminance > 0.02, luminance < 0.98 else {
                continue
            }
            let maximum = max(red, green, blue)
            let minimum = min(red, green, blue)
            let saturation = maximum == 0
                ? 0
                : (maximum - minimum) / maximum
            saturations.append(saturation)
            luminances.append(luminance)
        }

        guard saturations.count >= Self.minimumSampleCount else {
            return nil
        }
        saturations.sort()
        luminances.sort()
        return AppearanceStatistics(
            medianSaturation: Self.median(saturations),
            medianLuminance: Self.median(luminances),
            sampleCount: saturations.count
        )
    }

    private static func expandedCropRect(
        around box: CGRect,
        image: CGImage
    ) -> CGRect? {
        guard
            box.origin.x.isFinite,
            box.origin.y.isFinite,
            box.size.width.isFinite,
            box.size.height.isFinite,
            box.width > 0,
            box.height > 0
        else {
            return nil
        }
        let horizontalPadding = max(box.width * 0.75, 2)
        let verticalPadding = max(box.height * 0.75, 2)
        let expanded = box.insetBy(
            dx: -horizontalPadding,
            dy: -verticalPadding
        )
        let imageBounds = CGRect(
            x: 0,
            y: 0,
            width: image.width,
            height: image.height
        )
        let clipped = expanded.intersection(imageBounds).integral
        guard
            !clipped.isNull,
            clipped.width > 0,
            clipped.height > 0
        else {
            return nil
        }
        return clipped
    }

    private static func median(_ sorted: [Double]) -> Double {
        let middle = sorted.count / 2
        if sorted.count.isMultiple(of: 2) {
            return (sorted[middle - 1] + sorted[middle]) / 2
        }
        return sorted[middle]
    }
}
